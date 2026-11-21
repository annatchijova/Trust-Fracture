"""Level 1 CLI: load a scenario description and inspect the persisted graph.

Per docs/ARCHITECTURE.md layer 7: this layer renders what lower layers
already computed or persisted; it does not compute a verdict itself (there
is no verdict yet at Level 1 -- that is Level 3).
"""

from __future__ import annotations

import sys

import click

from trust_fracture.graph_store import GraphStore
from trust_fracture.ingestion import IngestionError
from trust_fracture.loader import load_scenario_into_store
from trust_fracture.normalization import NormalizationError
from trust_fracture.schema import NodeType


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
    except (IngestionError, NormalizationError) as exc:
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


if __name__ == "__main__":
    main()
