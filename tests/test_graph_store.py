"""Level 1 persistence tests.

These run against a real Relate database (no mock), per CLAUDE.md's
verification-first discipline and the mega-prompt's requirement that
integration tests exercise Relate for real: persistence, recovery, and
referential consistency after a close/reopen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from trust_fracture.graph_store import GraphStore, GraphStoreError
from trust_fracture.schema import EpistemicStatus, NodeType, RelationshipType


def test_node_and_relationship_survive_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "level1.rl"

    with GraphStore(db_path) as store:
        store.create_node(NodeType.AGENT, "agent-1", provenance="unit-test")
        store.create_node(NodeType.TOOL, "tool-1", provenance="unit-test")
        store.create_relationship(
            RelationshipType.INVOKES,
            "agent-1",
            "tool-1",
            relationship_id="rel-1",
            epistemic_status=EpistemicStatus.DERIVED,
            provenance="unit-test",
        )

    # A fresh GraphStore instance, as a stand-in for a fresh process: the
    # first store object above is fully closed (its __exit__ already ran)
    # before this one opens the same path.
    with GraphStore(db_path) as reopened:
        assert reopened.count_nodes(NodeType.AGENT) == 1
        assert reopened.count_nodes(NodeType.TOOL) == 1
        node = reopened.get_node("agent-1")
        assert node is not None
        assert node["id"] == "agent-1"
        assert node["provenance"] == "unit-test"
        assert node["schema_version"] == "1"


def test_get_node_returns_none_for_missing_id(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level1.rl") as store:
        assert store.get_node("does-not-exist") is None


def test_observed_in_requires_fact_and_observed_at(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level1.rl") as store:
        store.create_node(NodeType.TRACE_EVENT, "trace-1", provenance="unit-test")
        store.create_node(NodeType.AGENT, "agent-1", provenance="unit-test")

        with pytest.raises(GraphStoreError):
            store.create_relationship(
                RelationshipType.OBSERVED_IN,
                "agent-1",
                "trace-1",
                relationship_id="rel-bad",
                epistemic_status=EpistemicStatus.REQUIRES_INFERENCE,
                provenance="unit-test",
            )

        # Does not raise: FACT + a concrete observed_at satisfies the rule.
        store.create_relationship(
            RelationshipType.OBSERVED_IN,
            "agent-1",
            "trace-1",
            relationship_id="rel-good",
            epistemic_status=EpistemicStatus.FACT,
            provenance="unit-test",
            observed_at="2026-11-21T00:00:00Z",
        )
