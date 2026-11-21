"""Level 2, part 2: formal trust-boundary definitions and detection.

Per docs/THREAT_MODEL.md's "Trust boundaries considered" and
docs/GRAPH_MODEL.md's classification of CROSSES_BOUNDARY as "Derived,
computed against the formal boundary definition -- never asserted by
hand": this module is the one place that formal definition lives, as
fixed code (docs/ARCHITECTURE.md layer 5, rule evaluation) -- never as
data a scenario file can supply (enforced separately in
normalization.NON_INGESTIBLE_RELATIONSHIP_TYPES). Detection here is
read-only: it does not persist a CROSSES_BOUNDARY edge back into Relate.
Doing that is Level 3's evidence-layer concern (it would need an Evidence
record and a DERIVED_FROM link to be auditable, not just a bare edge), so
this level stops at surfacing the crossings to the investigator.
"""

from __future__ import annotations

from dataclasses import dataclass

from trust_fracture.query import PathEdge, StructuralPath
from trust_fracture.schema import NodeType


@dataclass(frozen=True)
class BoundaryDefinition:
    boundary_id: str
    description: str


# Each key is the unordered pair of NodeTypes whose adjacency crosses this
# boundary, independent of which relationship type connects them -- a
# structural/type-level rule, per docs/THREAT_MODEL.md's named boundaries.
_TYPE_PAIR_BOUNDARIES: dict[frozenset[NodeType], BoundaryDefinition] = {
    frozenset({NodeType.DATA_SOURCE, NodeType.AGENT}): BoundaryDefinition(
        "content-vs-execution-context",
        "External content crosses into the agent's execution context.",
    ),
    frozenset({NodeType.CONTENT_ARTIFACT, NodeType.AGENT}): BoundaryDefinition(
        "content-vs-execution-context",
        "External content crosses into the agent's execution context.",
    ),
    frozenset({NodeType.AGENT, NodeType.TOOL}): BoundaryDefinition(
        "agent-vs-tool",
        "An agent crosses into a tool's own authority.",
    ),
    frozenset({NodeType.OPERATION, NodeType.RESOURCE}): BoundaryDefinition(
        "tool-vs-protected-resource",
        "An operation crosses into a protected resource.",
    ),
}

AGENT_VS_AGENT = BoundaryDefinition(
    "agent-vs-agent",
    "One agent's authority crosses into a distinct agent's authority.",
)

# docs/THREAT_MODEL.md also names a "data vs. instruction, within a single
# piece of content" boundary. Detecting it needs the CONTAINS relationship
# resolved (docs/GRAPH_MODEL.md: "Derived -- requires content
# classification"), which no level up to and including this one
# implements. Deliberately absent here rather than approximated with a
# guess -- see docs/LIMITATIONS.md once that document exists.


def boundary_for_edge(
    source_type: NodeType,
    target_type: NodeType,
    source_id: str,
    target_id: str,
) -> BoundaryDefinition | None:
    if source_type is NodeType.AGENT and target_type is NodeType.AGENT:
        return AGENT_VS_AGENT if source_id != target_id else None
    return _TYPE_PAIR_BOUNDARIES.get(frozenset({source_type, target_type}))


def boundary_crossings(path: StructuralPath) -> tuple[tuple[PathEdge, BoundaryDefinition], ...]:
    """Every edge on `path` that crosses a formally defined trust
    boundary, in path order."""
    node_type_by_id = {node.node_id: node.node_type for node in path.nodes}
    crossings: list[tuple[PathEdge, BoundaryDefinition]] = []
    for edge in path.edges:
        boundary = boundary_for_edge(
            node_type_by_id[edge.source_id],
            node_type_by_id[edge.target_id],
            edge.source_id,
            edge.target_id,
        )
        if boundary is not None:
            crossings.append((edge, boundary))
    return tuple(crossings)
