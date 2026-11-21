"""Level 2 authority-analysis tests, against a real Relate store."""

from __future__ import annotations

from pathlib import Path

from trust_fracture.authority import analyze_authority
from trust_fracture.graph_store import GraphStore
from trust_fracture.schema import EpistemicStatus, NodeType, RelationshipType


def _create(store: GraphStore, node_type: NodeType, node_id: str) -> None:
    store.create_node(node_type, node_id, provenance="t")


def _link(store: GraphStore, rel: RelationshipType, src: str, dst: str, rid: str) -> None:
    store.create_relationship(
        rel, src, dst, relationship_id=rid, epistemic_status=EpistemicStatus.FACT, provenance="t"
    )


def test_actor_missing_a_required_permission(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level2.rl") as store:
        _create(store, NodeType.AGENT, "agent-1")
        _create(store, NodeType.OPERATION, "op-1")
        _create(store, NodeType.PERMISSION, "perm-write")
        _link(store, RelationshipType.REQUIRES_PERMISSION, "op-1", "perm-write", "r1")

        assessment = analyze_authority(store, "agent-1", "op-1")

    assert not assessment.possesses_all_required_permissions
    assert assessment.missing_permission_ids == ("perm-write",)
    assert "missing" in assessment.note


def test_actor_holds_permission_with_no_governing_policy(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level2.rl") as store:
        _create(store, NodeType.AGENT, "agent-1")
        _create(store, NodeType.OPERATION, "op-1")
        _create(store, NodeType.PERMISSION, "perm-write")
        _link(store, RelationshipType.REQUIRES_PERMISSION, "op-1", "perm-write", "r1")
        _link(store, RelationshipType.HAS_PERMISSION, "agent-1", "perm-write", "r2")

        assessment = analyze_authority(store, "agent-1", "op-1")

    assert assessment.possesses_all_required_permissions
    assert not assessment.is_governed
    assert "not, by itself, evidence" in assessment.note


def test_actor_holds_permission_and_operation_is_governed(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level2.rl") as store:
        _create(store, NodeType.AGENT, "agent-1")
        _create(store, NodeType.OPERATION, "op-1")
        _create(store, NodeType.PERMISSION, "perm-write")
        _create(store, NodeType.POLICY, "policy-1")
        _link(store, RelationshipType.REQUIRES_PERMISSION, "op-1", "perm-write", "r1")
        _link(store, RelationshipType.HAS_PERMISSION, "agent-1", "perm-write", "r2")
        _link(store, RelationshipType.GOVERNED_BY, "op-1", "policy-1", "r3")

        assessment = analyze_authority(store, "agent-1", "op-1")

    assert assessment.possesses_all_required_permissions
    assert assessment.is_governed
    assert "not evaluated here" in assessment.note
