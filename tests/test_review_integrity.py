"""Regression tests for observation identity and evidence output isolation."""

from pathlib import Path

from click.testing import CliRunner
import pytest

from trust_fracture.cli import main
from trust_fracture.graph_store import GraphStore
from trust_fracture.schema import EpistemicStatus, NodeType, RelationshipType

FIXTURE = Path(__file__).with_name("fixtures") / "minimal_scenario.json"
OBSERVED_AT = "2026-11-21T00:00:00Z"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.rl"
    result = CliRunner().invoke(main, ["load", str(FIXTURE), "--database", str(path)])
    assert result.exit_code == 0, result.output
    return path


def test_observe_refuses_to_append_to_recorded_event(database: Path) -> None:
    runner = CliRunner()
    args = [
        "observe", "--database", str(database), "--trace-event", "catalog-trace",
        "--observed-at", OBSERVED_AT, "--node", "agent-1", "--node", "tool-1",
    ]
    initial = runner.invoke(main, args)
    assert initial.exit_code == 0, (initial.output, initial.exception)
    repeated = runner.invoke(main, args)
    assert repeated.exit_code == 1
    assert "already has observation members" in repeated.output
    with GraphStore(database, read_only=True) as store:
        assert store.common_trace_events("agent-1", "tool-1") == ("catalog-trace",)


def test_legacy_event_with_repeated_membership_ids_cannot_back_a_path(database: Path) -> None:
    with GraphStore(database) as store:
        store.create_node(NodeType.TRACE_EVENT, "legacy-event", provenance="legacy-fixture")
        for node_id in ("agent-1", "tool-1"):
            store.create_relationship(
                RelationshipType.OBSERVED_IN, node_id, "legacy-event",
                relationship_id="legacy-membership", epistemic_status=EpistemicStatus.FACT,
                provenance="legacy-fixture", observed_at=OBSERVED_AT,
            )
        assert store.common_trace_events("agent-1", "tool-1") == ()


@pytest.mark.parametrize("alias", ["same-path", "hard-link", "symlink"])
def test_seal_finding_preserves_evidence_database(database: Path, alias: str) -> None:
    destination = database
    if alias == "hard-link":
        destination = database.with_name("evidence-alias.json")
        destination.hardlink_to(database)
    elif alias == "symlink":
        destination = database.with_name("evidence-alias.json")
        destination.symlink_to(database)
    original = database.read_bytes()

    result = CliRunner().invoke(main, [
        "seal-finding", "--database", str(database), "--source", "agent-1",
        "--target", "tool-1", "--actor", "agent-1", "--operation", "tool-1",
        "--finding-id", "catalog-finding", "--out", str(destination),
    ])
    assert result.exit_code == 1
    assert "output must differ from the evidence database" in result.output
    assert database.read_bytes() == original


def test_equal_rank_findings_have_the_same_digest_in_reversed_path_order(database: Path) -> None:
    from dataclasses import replace

    from trust_fracture.evidence import seal
    from trust_fracture.findings import build_finding
    from trust_fracture.query import find_bounded_paths

    with GraphStore(database) as store:
        store.create_node(NodeType.OPERATION, "publish", provenance="fixture")
        store.create_node(NodeType.RESOURCE, "catalog", provenance="fixture")
        store.create_node(NodeType.TOOL, "tool-2", provenance="fixture")
        for index, (kind, source, target) in enumerate((
            (RelationshipType.INVOKES, "agent-1", "tool-2"),
            (RelationshipType.INVOKES, "tool-1", "publish"),
            (RelationshipType.INVOKES, "tool-2", "publish"),
            (RelationshipType.TARGETS, "publish", "catalog"),
        )):
            store.create_relationship(
                kind, source, target, relationship_id=f"fixture-{index}",
                epistemic_status=EpistemicStatus.DERIVED, provenance="fixture",
            )
        result = find_bounded_paths(store, "agent-1", "catalog", max_hops=3)
        assert len(result.paths) == 2
        reversed_result = replace(result, paths=result.paths[::-1])
        digests = {
            seal(
                build_finding(
                    store, paths, actor_id="agent-1", operation_id="publish", finding_id="catalog",
                ).to_payload(),
                sealed_at=OBSERVED_AT,
            ).digest
            for paths in (result, reversed_result)
        }
    assert len(digests) == 1
