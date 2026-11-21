"""Level 2, part 1: bounded reachability between an untrusted source and a
privileged operation.

Per docs/ARCHITECTURE.md layer 4 ("Query"): this module calls into the
persistence layer (graph_store.GraphStore) only; it never opens a Relate
connection itself. Per docs/EPISTEMIC_MODEL.md's central invariant --
"graph reachability is not proof of exploitability" -- every result this
module returns is fixed at state B (structural possibility): the
EPISTEMIC_LABEL class attribute on PathFindingResult cannot be overridden
by a caller, so nothing downstream can mistake a reachability result for a
stronger claim without going through the actual promotion rules the
epistemic model requires (Level 3 scope, not built yet).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from trust_fracture.graph_store import GraphStore
from trust_fracture.schema import (
    PROPAGATION_RELATIONSHIP_TYPES,
    EpistemicStatus,
    NodeType,
    RelationshipType,
)

DEFAULT_MAX_HOPS = 6


@dataclass(frozen=True)
class PathNode:
    node_type: NodeType
    node_id: str


@dataclass(frozen=True)
class PathEdge:
    rel_type: RelationshipType
    relationship_id: str
    # source_id/target_id reflect this edge's position *along this path's
    # walk order*, not necessarily its stored direction in the graph --
    # propagation-relevant edges are traversed undirected (see
    # schema.PROPAGATION_RELATIONSHIP_TYPES), so an edge stored as
    # (Agent)-[:READS]->(DataSource) walked from the DataSource side
    # reports source_id as the DataSource, matching how the path reads.
    source_id: str
    target_id: str
    epistemic_status: EpistemicStatus
    provenance: str


@dataclass(frozen=True)
class StructuralPath:
    nodes: tuple[PathNode, ...]
    edges: tuple[PathEdge, ...]

    @property
    def all_facts(self) -> bool:
        """True only if every edge on this path is a stored fact. A path
        with any DERIVED or REQUIRES_INFERENCE edge is weaker evidence of
        anything than one built entirely from facts -- this flag lets a
        caller see that distinction without collapsing it into a single
        boolean "reachable"."""
        return all(edge.epistemic_status is EpistemicStatus.FACT for edge in self.edges)


@dataclass(frozen=True)
class PathFindingResult:
    source_id: str
    target_id: str
    max_hops: int
    paths: tuple[StructuralPath, ...]

    # Fixed, not a constructor parameter: no caller of this module can
    # construct a PathFindingResult claiming anything other than
    # structural possibility. Promoting past this requires the Level 3
    # evidence/promotion machinery docs/EPISTEMIC_MODEL.md describes, not
    # a different value passed in here.
    EPISTEMIC_LABEL: ClassVar[str] = "structural_possibility"

    @property
    def found(self) -> bool:
        return len(self.paths) > 0


def _node_from_raw(raw_node: dict[str, Any]) -> PathNode:
    labels = raw_node["labels"]
    if len(labels) != 1:
        raise ValueError(
            f"expected exactly one label per node, got {labels!r} for "
            f"node {raw_node!r}"
        )
    return PathNode(
        node_type=NodeType(labels[0]),
        node_id=raw_node["properties"]["id"],
    )


def _edge_from_raw(raw_rel: dict[str, Any], walk_source_id: str, walk_target_id: str) -> PathEdge:
    # Deliberately NOT using raw_rel["start_node"]/["end_node"] here: those
    # are the edge's *stored* direction (relate's internal node ids), which
    # can run opposite to this path's walk order once traversal is
    # undirected (schema.PROPAGATION_RELATIONSHIP_TYPES) -- confirmed
    # empirically while building this: a READS edge stored
    # Agent->DataSource, walked from the DataSource side, must report the
    # DataSource as source_id or the printed path reads backwards. Using
    # the two path-adjacent nodes' ids (walk_source_id/walk_target_id,
    # supplied by the caller from the path's own node sequence) sidesteps
    # stored direction entirely and is correct regardless of it.
    props = raw_rel["properties"]
    return PathEdge(
        rel_type=RelationshipType(raw_rel["type"]),
        relationship_id=props["id"],
        source_id=walk_source_id,
        target_id=walk_target_id,
        epistemic_status=EpistemicStatus(props["epistemic_status"]),
        provenance=props["provenance"],
    )


def find_bounded_paths(
    store: GraphStore,
    source_id: str,
    target_id: str,
    *,
    max_hops: int = DEFAULT_MAX_HOPS,
) -> PathFindingResult:
    """Every path of at most `max_hops` propagation-relevant relationships
    (schema.PROPAGATION_RELATIONSHIP_TYPES) connecting `source_id` and
    `target_id`, each tagged with the epistemic status its edges already
    carry from Level 1. This never claims more than reachability -- see
    PathFindingResult.EPISTEMIC_LABEL."""
    raw_paths = store.paths_between(
        source_id,
        target_id,
        max_hops=max_hops,
        relationship_types=PROPAGATION_RELATIONSHIP_TYPES,
    )

    structural_paths: list[StructuralPath] = []
    for raw_path in raw_paths:
        # relate's Path.to_dict() interleaves nodes/relationships in walk
        # order (confirmed empirically), so the i-th relationship always
        # sits between nodes[i] and nodes[i+1] along this specific path --
        # regardless of that relationship's stored direction.
        nodes = tuple(_node_from_raw(n) for n in raw_path["nodes"])
        edges = tuple(
            _edge_from_raw(r, nodes[i].node_id, nodes[i + 1].node_id)
            for i, r in enumerate(raw_path["relationships"])
        )
        structural_paths.append(StructuralPath(nodes=nodes, edges=edges))

    return PathFindingResult(
        source_id=source_id,
        target_id=target_id,
        max_hops=max_hops,
        paths=tuple(structural_paths),
    )
