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
