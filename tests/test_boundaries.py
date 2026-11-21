"""Level 2 trust-boundary detection tests."""

from __future__ import annotations

from trust_fracture.boundaries import AGENT_VS_AGENT, boundary_crossings, boundary_for_edge
from trust_fracture.query import EpistemicStatus, PathEdge, PathNode, StructuralPath
from trust_fracture.schema import NodeType, RelationshipType


def test_data_source_to_agent_crosses_content_boundary() -> None:
    boundary = boundary_for_edge(NodeType.DATA_SOURCE, NodeType.AGENT, "doc-1", "agent-1")
    assert boundary is not None
    assert boundary.boundary_id == "content-vs-execution-context"


def test_agent_to_tool_crosses_agent_vs_tool_boundary() -> None:
    boundary = boundary_for_edge(NodeType.AGENT, NodeType.TOOL, "agent-1", "tool-1")
    assert boundary is not None
    assert boundary.boundary_id == "agent-vs-tool"


def test_operation_to_resource_crosses_protected_resource_boundary() -> None:
    boundary = boundary_for_edge(NodeType.OPERATION, NodeType.RESOURCE, "op-1", "res-1")
    assert boundary is not None
    assert boundary.boundary_id == "tool-vs-protected-resource"


def test_two_distinct_agents_cross_agent_vs_agent_boundary() -> None:
    boundary = boundary_for_edge(NodeType.AGENT, NodeType.AGENT, "agent-1", "agent-2")
    assert boundary is AGENT_VS_AGENT


def test_self_loop_agent_edge_is_not_a_boundary_crossing() -> None:
    boundary = boundary_for_edge(NodeType.AGENT, NodeType.AGENT, "agent-1", "agent-1")
    assert boundary is None


def test_unrelated_type_pair_has_no_boundary() -> None:
    boundary = boundary_for_edge(NodeType.POLICY, NodeType.CONTROL, "policy-1", "control-1")
    assert boundary is None


def test_boundary_crossings_walks_a_full_path() -> None:
    path = StructuralPath(
        nodes=(
            PathNode(NodeType.DATA_SOURCE, "doc-1"),
            PathNode(NodeType.AGENT, "agent-1"),
            PathNode(NodeType.TOOL, "tool-1"),
        ),
        edges=(
            PathEdge(
                RelationshipType.READS, "r1", "agent-1", "doc-1",
                EpistemicStatus.FACT, "t",
            ),
            PathEdge(
                RelationshipType.INVOKES, "r2", "agent-1", "tool-1",
                EpistemicStatus.DERIVED, "t",
            ),
        ),
    )
    crossings = boundary_crossings(path)
    assert [b.boundary_id for _, b in crossings] == [
        "content-vs-execution-context",
        "agent-vs-tool",
    ]
