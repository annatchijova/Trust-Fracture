"""Level 2 bounded-reachability tests, against a real Relate store."""

from __future__ import annotations

from pathlib import Path

from trust_fracture.graph_store import GraphStore
from trust_fracture.query import PathFindingResult, find_bounded_paths
from trust_fracture.schema import EpistemicStatus, NodeType, RelationshipType


def _build_three_hop_chain(store: GraphStore) -> None:
    store.create_node(NodeType.DATA_SOURCE, "doc-1", provenance="t")
    store.create_node(NodeType.AGENT, "agent-1", provenance="t")
    store.create_node(NodeType.TOOL, "tool-1", provenance="t")
    store.create_node(NodeType.OPERATION, "op-1", provenance="t")
    store.create_node(NodeType.RESOURCE, "res-1", provenance="t")

    store.create_relationship(
        RelationshipType.READS, "agent-1", "doc-1",
        relationship_id="r1", epistemic_status=EpistemicStatus.FACT, provenance="t",
    )
    store.create_relationship(
        RelationshipType.INVOKES, "agent-1", "tool-1",
        relationship_id="r2", epistemic_status=EpistemicStatus.DERIVED, provenance="t",
    )
    store.create_relationship(
        RelationshipType.INVOKES, "tool-1", "op-1",
        relationship_id="r3", epistemic_status=EpistemicStatus.DERIVED, provenance="t",
    )
    store.create_relationship(
        RelationshipType.TARGETS, "op-1", "res-1",
        relationship_id="r4", epistemic_status=EpistemicStatus.FACT, provenance="t",
    )


def test_find_bounded_paths_returns_structural_possibility_label(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level2.rl") as store:
        _build_three_hop_chain(store)
        result = find_bounded_paths(store, "agent-1", "res-1", max_hops=6)

    assert result.EPISTEMIC_LABEL == "structural_possibility"
    assert PathFindingResult.EPISTEMIC_LABEL == "structural_possibility"
    assert result.found
    assert len(result.paths) == 1
    path = result.paths[0]
    assert [n.node_id for n in path.nodes] == ["agent-1", "tool-1", "op-1", "res-1"]
    assert path.all_facts is False  # the two INVOKES edges are DERIVED


def test_find_bounded_paths_respects_hop_bound(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level2.rl") as store:
        _build_three_hop_chain(store)
        # agent-1 -> tool-1 -> op-1 -> res-1 is 3 hops; cap it at 2.
        result = find_bounded_paths(store, "agent-1", "res-1", max_hops=2)

    assert not result.found


def test_find_bounded_paths_traverses_reads_against_its_stored_direction(
    tmp_path: Path,
) -> None:
    """Regression: READS is stored (Agent)-[:READS]->(DataSource) --
    "the agent reads the source" -- but influence from the untrusted
    source flows the other way. A query starting FROM the DataSource
    must still find the agent, tool, and operation beyond it; this failed
    (0 paths) before paths_between traversed propagation edges without
    regard to stored direction."""
    with GraphStore(tmp_path / "level2.rl") as store:
        _build_three_hop_chain(store)
        result = find_bounded_paths(store, "doc-1", "res-1", max_hops=6)

    assert result.found
    path = result.paths[0]
    assert [n.node_id for n in path.nodes] == ["doc-1", "agent-1", "tool-1", "op-1", "res-1"]
    # The READS edge's reported direction matches the walk, not storage.
    reads_edge = path.edges[0]
    assert reads_edge.rel_type is RelationshipType.READS
    assert reads_edge.source_id == "doc-1"
    assert reads_edge.target_id == "agent-1"


def test_find_bounded_paths_does_not_traverse_authority_edges(tmp_path: Path) -> None:
    """REQUIRES_PERMISSION/HAS_PERMISSION are authority bookkeeping, not a
    propagation channel -- a path must never be reported through them."""
    with GraphStore(tmp_path / "level2.rl") as store:
        store.create_node(NodeType.AGENT, "agent-1", provenance="t")
        store.create_node(NodeType.OPERATION, "op-1", provenance="t")
        store.create_node(NodeType.PERMISSION, "perm-1", provenance="t")
        store.create_relationship(
            RelationshipType.REQUIRES_PERMISSION, "op-1", "perm-1",
            relationship_id="r1", epistemic_status=EpistemicStatus.FACT, provenance="t",
        )
        store.create_relationship(
            RelationshipType.HAS_PERMISSION, "agent-1", "perm-1",
            relationship_id="r2", epistemic_status=EpistemicStatus.FACT, provenance="t",
        )
        result = find_bounded_paths(store, "agent-1", "op-1", max_hops=6)

    assert not result.found


def test_find_bounded_paths_no_path_is_a_valid_empty_result(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level2.rl") as store:
        store.create_node(NodeType.AGENT, "lonely-agent", provenance="t")
        store.create_node(NodeType.RESOURCE, "unreachable-res", provenance="t")
        result = find_bounded_paths(store, "lonely-agent", "unreachable-res")

    assert result.paths == ()
    assert not result.found
