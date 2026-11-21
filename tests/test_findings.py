"""Level 3 promotion-rule and finding-assembly tests, against a real
Relate store."""

from __future__ import annotations

from pathlib import Path

from trust_fracture.findings import EpistemicState, build_finding, classify_path_observation
from trust_fracture.graph_store import GraphStore
from trust_fracture.query import find_bounded_paths
from trust_fracture.schema import EpistemicStatus, NodeType, RelationshipType


def _build_scenario(store: GraphStore) -> None:
    store.create_node(NodeType.DATA_SOURCE, "doc-1", provenance="t")
    store.create_node(NodeType.AGENT, "agent-1", provenance="t")
    store.create_node(NodeType.TOOL, "tool-1", provenance="t")
    store.create_node(NodeType.OPERATION, "op-1", provenance="t")
    store.create_node(NodeType.RESOURCE, "res-1", provenance="t")
    store.create_node(NodeType.PERMISSION, "perm-1", provenance="t")
    store.create_node(NodeType.POLICY, "policy-1", provenance="t")

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
    store.create_relationship(
        RelationshipType.REQUIRES_PERMISSION, "op-1", "perm-1",
        relationship_id="r5", epistemic_status=EpistemicStatus.FACT, provenance="t",
    )
    store.create_relationship(
        RelationshipType.GOVERNED_BY, "op-1", "policy-1",
        relationship_id="r6", epistemic_status=EpistemicStatus.FACT, provenance="t",
    )


def _observe(store: GraphStore, trace_event_id: str, *node_ids: str, observed_at: str) -> None:
    store.create_node(NodeType.TRACE_EVENT, trace_event_id, provenance="t")
    for index, node_id in enumerate(node_ids):
        store.create_relationship(
            RelationshipType.OBSERVED_IN, node_id, trace_event_id,
            relationship_id=f"{trace_event_id}-{index}",
            epistemic_status=EpistemicStatus.FACT, provenance="t", observed_at=observed_at,
        )


def test_no_path_found_is_insufficient_evidence(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level3.rl") as store:
        store.create_node(NodeType.AGENT, "lonely", provenance="t")
        store.create_node(NodeType.RESOURCE, "isolated", provenance="t")
        result = find_bounded_paths(store, "lonely", "isolated")
        finding = build_finding(
            store, result, actor_id="lonely", operation_id="isolated", finding_id="f1"
        )

    assert finding.epistemic_state is EpistemicState.INSUFFICIENT_EVIDENCE
    assert "no path found" in finding.reasons[0]


def test_unobserved_path_stays_potential(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level3.rl") as store:
        _build_scenario(store)
        result = find_bounded_paths(store, "doc-1", "res-1", max_hops=6)
        finding = build_finding(
            store, result, actor_id="agent-1", operation_id="op-1", finding_id="f1"
        )

    assert finding.epistemic_state is EpistemicState.POTENTIAL_PATH
    # Regression: the found path's node ids must be reported even when
    # its state ties the loop's (removed) hardcoded starting state.
    assert finding.path_node_ids == ("doc-1", "agent-1", "tool-1", "op-1", "res-1")


def test_fully_observed_path_without_authority_gap_is_observed_flow(tmp_path: Path) -> None:
    with GraphStore(tmp_path / "level3.rl") as store:
        _build_scenario(store)
        # Actor holds the required permission -- no authority gap, so the
        # strongest honest claim is OBSERVED_FLOW, not a violation.
        store.create_relationship(
            RelationshipType.HAS_PERMISSION, "agent-1", "perm-1",
            relationship_id="r7", epistemic_status=EpistemicStatus.FACT, provenance="t",
        )
        _observe(store, "trace-1", "doc-1", "agent-1", observed_at="2026-11-21T00:00:00Z")
        _observe(store, "trace-2", "agent-1", "tool-1", observed_at="2026-11-21T00:00:01Z")
        _observe(store, "trace-3", "tool-1", "op-1", observed_at="2026-11-21T00:00:02Z")
        _observe(store, "trace-4", "op-1", "res-1", observed_at="2026-11-21T00:00:03Z")

        result = find_bounded_paths(store, "doc-1", "res-1", max_hops=6)
        path = result.paths[0]
        assert classify_path_observation(store, path) is EpistemicState.OBSERVED_FLOW

        finding = build_finding(
            store, result, actor_id="agent-1", operation_id="op-1", finding_id="f1"
        )

    assert finding.epistemic_state is EpistemicState.OBSERVED_FLOW


def test_observed_path_with_authority_gap_needs_explicit_breach_evidence(
    tmp_path: Path,
) -> None:
    with GraphStore(tmp_path / "level3.rl") as store:
        _build_scenario(store)
        # Deliberately do NOT grant agent-1 perm-1: an authority gap.
        _observe(store, "trace-1", "doc-1", "agent-1", observed_at="2026-11-21T00:00:00Z")
        _observe(store, "trace-2", "agent-1", "tool-1", observed_at="2026-11-21T00:00:01Z")
        _observe(store, "trace-3", "tool-1", "op-1", observed_at="2026-11-21T00:00:02Z")
        _observe(store, "trace-4", "op-1", "res-1", observed_at="2026-11-21T00:00:03Z")

        result = find_bounded_paths(store, "doc-1", "res-1", max_hops=6)
        finding = build_finding(
            store, result, actor_id="agent-1", operation_id="op-1", finding_id="f1"
        )

    assert finding.epistemic_state is EpistemicState.OBSERVED_FLOW
    assert "perm-1" in finding.reasons[0]
    assert "policy-1" in finding.reasons[1]
    assert "explicit execution and applicable policy breach evidence" in finding.reasons[2]
    assert set(finding.trace_event_ids) == {"trace-1", "trace-2", "trace-3", "trace-4"}


def test_finding_payload_is_canonicalizable_and_seals_reproducibly(tmp_path: Path) -> None:
    from trust_fracture.evidence import seal, verify_seal

    with GraphStore(tmp_path / "level3.rl") as store:
        _build_scenario(store)
        result = find_bounded_paths(store, "doc-1", "res-1", max_hops=6)
        finding = build_finding(
            store, result, actor_id="agent-1", operation_id="op-1", finding_id="f1"
        )

    sealed_once = seal(finding.to_payload(), sealed_at="2026-11-21T00:00:00Z")
    sealed_twice = seal(finding.to_payload(), sealed_at="2026-11-21T00:00:00Z")
    assert sealed_once.digest == sealed_twice.digest
    assert verify_seal(sealed_once)
