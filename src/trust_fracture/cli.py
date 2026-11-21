"""Level 1 CLI: load a scenario description and inspect the persisted graph.

Per docs/ARCHITECTURE.md layer 7: this layer renders what lower layers
already computed or persisted; it does not compute a verdict itself (there
is no verdict yet at Level 1 -- that is Level 3).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import click

from trust_fracture.authority import analyze_authority
from trust_fracture.boundaries import boundary_crossings
from trust_fracture.evidence import seal
from trust_fracture.findings import build_finding
from trust_fracture.graph_store import GraphStore, GraphStoreError
from trust_fracture.ingestion import IngestionError
from trust_fracture.loader import load_scenario_into_store
from trust_fracture.normalization import NormalizationError
from trust_fracture.query import DEFAULT_MAX_HOPS, find_bounded_paths
from trust_fracture.schema import EpistemicStatus, NodeType, RelationshipType


@click.group()
def main() -> None:
    """Trust Fracture: graph-based investigation of trust-boundary
    violations in AI agent systems."""


@main.command("load")
@click.argument("scenario_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--database",
    "database_path",
    required=True,
    type=click.Path(dir_okay=False),
    help="Relate database path to load the scenario into (created if absent).",
)
def load_command(scenario_file: str, database_path: str) -> None:
    """Ingest and persist a scenario description file."""
    try:
        with GraphStore(database_path) as store:
            graph = load_scenario_into_store(scenario_file, store)
    except (IngestionError, NormalizationError, GraphStoreError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    click.echo(
        f"Loaded {len(graph.nodes)} node(s) and {len(graph.relationships)} "
        f"relationship(s) from {scenario_file} into {database_path}"
    )


@main.command("inspect")
@click.option(
    "--database",
    "database_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Relate database path to inspect.",
)
def inspect_command(database_path: str) -> None:
    """Print node counts per type for an existing database, read-only."""
    with GraphStore(database_path, read_only=True) as store:
        for node_type in NodeType:
            count = store.count_nodes(node_type)
            if count:
                click.echo(f"{node_type.value}: {count}")


@main.command("investigate")
@click.option(
    "--database",
    "database_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Relate database path to investigate, read-only.",
)
@click.option("--source", "source_id", required=True, help="Untrusted source node id.")
@click.option("--target", "target_id", required=True, help="Privileged operation node id.")
@click.option(
    "--max-hops",
    default=DEFAULT_MAX_HOPS,
    show_default=True,
    help="Upper bound on path length (bounded reachability, not shortest path).",
)
def investigate_command(
    database_path: str, source_id: str, target_id: str, max_hops: int
) -> None:
    """Bounded reachability + trust-boundary crossings between a source
    and an operation. Never claims more than structural possibility."""
    with GraphStore(database_path, read_only=True) as store:
        result = find_bounded_paths(store, source_id, target_id, max_hops=max_hops)

        click.echo(f"epistemic_label: {result.EPISTEMIC_LABEL}")
        click.echo(f"paths found: {len(result.paths)} (max_hops={max_hops})")

        for index, path in enumerate(result.paths):
            node_chain = " -> ".join(f"{n.node_type.value}:{n.node_id}" for n in path.nodes)
            click.echo(f"\npath {index}: {node_chain}")
            click.echo(f"  all edges stored as fact: {path.all_facts}")
            for edge, boundary in boundary_crossings(path):
                click.echo(
                    f"  crosses boundary [{boundary.boundary_id}] at "
                    f"{edge.source_id} -> {edge.target_id} ({boundary.description})"
                )


@main.command("authority")
@click.option(
    "--database",
    "database_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Relate database path to investigate, read-only.",
)
@click.option("--actor", "actor_id", required=True, help="Agent or tool node id.")
@click.option("--operation", "operation_id", required=True, help="Operation node id.")
def authority_command(database_path: str, actor_id: str, operation_id: str) -> None:
    """Permission possession vs. policy governance for one actor/operation
    pair. Never collapses either into 'authorized'."""
    with GraphStore(database_path, read_only=True) as store:
        assessment = analyze_authority(store, actor_id, operation_id)
        click.echo(assessment.note)


@main.command("observe")
@click.option(
    "--database",
    "database_path",
    required=True,
    type=click.Path(dir_okay=False),
    help="Relate database path to record the observation into.",
)
@click.option("--trace-event", "trace_event_id", required=True, help="TraceEvent node id.")
@click.option(
    "--observed-at",
    required=True,
    help="ISO 8601 timestamp this interaction was actually observed at.",
)
@click.option(
    "--node",
    "node_ids",
    required=True,
    multiple=True,
    help="A node id observed in this trace event (repeatable, at least 2).",
)
def observe_command(database_path: str, trace_event_id: str, observed_at: str, node_ids: tuple[str, ...]) -> None:
    """Record a real TraceEvent and link the nodes observed together in
    it (docs/EPISTEMIC_MODEL.md, B -> C evidence). This is the only
    command that lets a path be promoted past structural possibility."""
    if len(node_ids) < 2:
        click.echo("error: --node must be supplied at least twice", err=True)
        sys.exit(1)

    try:
        with GraphStore(database_path) as store, store.transaction():
            if store.get_node(trace_event_id) is None:
                store.create_node(NodeType.TRACE_EVENT, trace_event_id, provenance="cli-observe")
            for index, node_id in enumerate(node_ids):
                store.create_relationship(
                    RelationshipType.OBSERVED_IN,
                    node_id,
                    trace_event_id,
                    relationship_id=f"{trace_event_id}-observed-{index}",
                    epistemic_status=EpistemicStatus.FACT,
                    provenance="cli-observe",
                    observed_at=observed_at,
                )
    except GraphStoreError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Recorded {trace_event_id} observing {len(node_ids)} node(s)")


@main.command("seal-finding")
@click.option(
    "--database",
    "database_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Relate database path to investigate, read-only.",
)
@click.option("--source", "source_id", required=True, help="Untrusted source node id.")
@click.option("--target", "target_id", required=True, help="Node id to investigate reachability toward.")
@click.option("--actor", "actor_id", required=True, help="The actor invoking the operation.")
@click.option("--operation", "operation_id", required=True, help="Operation node id.")
@click.option("--finding-id", required=True, help="Unique id for this finding.")
@click.option("--max-hops", default=DEFAULT_MAX_HOPS, show_default=True)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    help="Write the sealed finding as JSON to this path (default: stdout).",
)
def seal_finding_command(
    database_path: str,
    source_id: str,
    target_id: str,
    actor_id: str,
    operation_id: str,
    finding_id: str,
    max_hops: int,
    out_path: str | None,
) -> None:
    """Classify a source/target investigation into its strongest
    justified epistemic state and seal the result (CLAUDE.md 5.2):
    canonical serialization + SHA-256, verifiable independently with
    scripts/verify_finding.py."""
    with GraphStore(database_path, read_only=True) as store:
        path_result = find_bounded_paths(store, source_id, target_id, max_hops=max_hops)
        finding = build_finding(
            store, path_result, actor_id=actor_id, operation_id=operation_id, finding_id=finding_id
        )

    sealed_at = datetime.now(timezone.utc).isoformat()
    sealed = seal(finding.to_payload(), sealed_at=sealed_at)
    output = json.dumps(sealed.to_json_dict(), indent=2, sort_keys=True)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        click.echo(f"Sealed finding ({finding.epistemic_state.value}) written to {out_path}")
    else:
        click.echo(output)


if __name__ == "__main__":
    main()
