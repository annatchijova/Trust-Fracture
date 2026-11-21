"""Graph schema types for Trust Fracture, as designed in docs/GRAPH_MODEL.md.

Level 1 scope: node and relationship *types*, and the metadata every
relevant relationship must carry at creation time (epistemic_status,
provenance, schema_version). Promotion rules between epistemic states
(docs/EPISTEMIC_MODEL.md) are Level 2/3 scope and are not implemented here.
"""

from __future__ import annotations

from enum import Enum

SCHEMA_VERSION = "1"


class NodeType(str, Enum):
    AGENT = "Agent"
    TOOL = "Tool"
    DATA_SOURCE = "DataSource"
    CONTENT_ARTIFACT = "ContentArtifact"
    INSTRUCTION = "Instruction"
    OPERATION = "Operation"
    PERMISSION = "Permission"
    RESOURCE = "Resource"
    POLICY = "Policy"
    TRUST_BOUNDARY = "TrustBoundary"
    CONTROL = "Control"
    TRACE_EVENT = "TraceEvent"
    EVIDENCE = "Evidence"


class RelationshipType(str, Enum):
    READS = "READS"
    PRODUCES = "PRODUCES"
    CONTAINS = "CONTAINS"
    INVOKES = "INVOKES"
    REQUIRES_PERMISSION = "REQUIRES_PERMISSION"
    HAS_PERMISSION = "HAS_PERMISSION"
    TARGETS = "TARGETS"
    GOVERNED_BY = "GOVERNED_BY"
    OBSERVED_IN = "OBSERVED_IN"
    SUPPORTED_BY = "SUPPORTED_BY"
    DERIVED_FROM = "DERIVED_FROM"
    CROSSES_BOUNDARY = "CROSSES_BOUNDARY"


class EpistemicStatus(str, Enum):
    """Per docs/GRAPH_MODEL.md: what kind of claim a relationship is.

    This is a classification of the *relationship entry itself*, not the
    five-state investigation verdict in docs/EPISTEMIC_MODEL.md (that state
    machine applies to findings built on top of the graph, starting at
    Level 2/3).
    """

    FACT = "fact"
    DERIVED = "derived"
    REQUIRES_INFERENCE = "requires_inference"


# Relationship types that must never be persisted as FACT without a backing
# TraceEvent, per docs/GRAPH_MODEL.md's classification table. Enforced by
# GraphStore.create_relationship, not left as a convention.
OBSERVATION_ONLY_TYPES = frozenset(
    {
        RelationshipType.OBSERVED_IN,
    }
)

# Relationship types docs/GRAPH_MODEL.md classifies as "Derived, ... never
# asserted by hand": they exist only once the engine has actually computed
# them (boundary evaluation, path derivation, evidence assembly), none of
# which is built before Level 2/3. A scenario file -- the untrusted-content
# channel in docs/THREAT_MODEL.md -- must never be able to declare one of
# these directly as a hand-entered fact; confirmed reachable in the Level 1
# red-team review before this set existed. Enforced by
# normalization.normalize_scenario, not by GraphStore, since this is a
# restriction on what scenario *ingestion* may claim, not on what the
# engine itself may later write once it has actually derived the edge.
NON_INGESTIBLE_RELATIONSHIP_TYPES = frozenset(
    {
        RelationshipType.OBSERVED_IN,
        RelationshipType.CROSSES_BOUNDARY,
        RelationshipType.DERIVED_FROM,
        RelationshipType.SUPPORTED_BY,
    }
)

# Relationship types a bounded-reachability investigation (Level 2,
# query.find_bounded_paths) treats as capable of carrying influence from
# one node to another. Deliberately excludes authority/epistemic-
# management edges -- REQUIRES_PERMISSION, HAS_PERMISSION, GOVERNED_BY,
# CROSSES_BOUNDARY, OBSERVED_IN, SUPPORTED_BY, DERIVED_FROM -- which
# describe facts *about* the graph's entities, not a channel influence
# could travel through; including them would let the reachability query
# report a "path" that walks through permission/policy bookkeeping nodes
# instead of a real investigative chain.
#
# These edges are also traversed without regard to their stored direction
# (see graph_store.GraphStore.paths_between): stored direction encodes who
# performed the action (e.g. READS is stored agent->datasource, "the
# agent reads the source"), not which way adversarial influence could
# propagate (content -> agent). Treating direction as significant here
# was tried first and produced a false negative on exactly the scenario
# shape this project exists to investigate (an agent reading untrusted
# content) -- see the Level 2 build history. This is a deliberate
# simplification, not a claim that propagation direction never matters;
# a more direction-aware model is deferred, not silently assumed correct.
PROPAGATION_RELATIONSHIP_TYPES = frozenset(
    {
        RelationshipType.READS,
        RelationshipType.PRODUCES,
        RelationshipType.CONTAINS,
        RelationshipType.INVOKES,
        RelationshipType.TARGETS,
    }
)
