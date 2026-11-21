"""Explicit observations back a relationship identity, including parallel edges."""

from pathlib import Path

from click.testing import CliRunner

from trust_fracture.cli import main
from trust_fracture.findings import EpistemicState, classify_path_observation
from trust_fracture.graph_store import GraphStore
from trust_fracture.query import find_bounded_paths
from trust_fracture.schema import EpistemicStatus, RelationshipType


def test_only_explicit_unambiguous_relationship_is_observed(tmp_path: Path) -> None:
    database = tmp_path / "catalog.rl"
    args = ["--database", str(database)]
    fixture = Path(__file__).with_name("fixtures") / "minimal_scenario.json"
    runner = CliRunner()
    loaded = runner.invoke(main, ["load", str(fixture), *args])
    assert loaded.exit_code == 0, loaded.output

    def add_parallel(store: GraphStore, edge_id: str) -> None:
        store.create_relationship(
            RelationshipType.INVOKES, "agent-1", "tool-1", relationship_id=edge_id,
            epistemic_status=EpistemicStatus.DERIVED, provenance="fixture",
        )

    def states(store: GraphStore) -> dict[str, EpistemicState]:
        paths = find_bounded_paths(store, "agent-1", "tool-1", max_hops=1).paths
        return {path.edges[0].relationship_id: classify_path_observation(store, path) for path in paths}

    with GraphStore(database) as store:
        add_parallel(store, "parallel")
    observe = [
        "observe", *args, "--node", "agent-1", "--node", "tool-1",
        "--observed-at", "2026-11-21T00:00:00Z", "--trace-event",
    ]
    coobserved = runner.invoke(main, [*observe, "nodes-only"])
    assert coobserved.exit_code == 0, coobserved.output
    with GraphStore(database, read_only=True) as store:
        assert states(store) == dict.fromkeys(("rel-1", "parallel"), EpistemicState.POTENTIAL_PATH)

    rejected = runner.invoke(main, [*observe, "unknown-edge", "--relationship", "missing"])
    assert rejected.exit_code == 1
    assert "must be a unique structural relationship" in rejected.output
    explicit = runner.invoke(main, [*observe, "linked", "--relationship", "rel-1"])
    assert explicit.exit_code == 0, (explicit.output, explicit.exception)

    with GraphStore(database) as store:
        assert store.get_node("unknown-edge") is None
        assert states(store) == {
            "rel-1": EpistemicState.OBSERVED_FLOW,
            "parallel": EpistemicState.POTENTIAL_PATH,
        }
        add_parallel(store, "rel-1")
        assert states(store) == dict.fromkeys(("rel-1", "parallel"), EpistemicState.POTENTIAL_PATH)
