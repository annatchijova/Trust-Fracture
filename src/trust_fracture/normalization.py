"""Level 1 normalization layer: raw ingested dicts -> typed schema records.

Per docs/ARCHITECTURE.md layer 2: epistemic_status and provenance are
attached here, at record-creation time, never patched onto a node or
relationship after it already exists. Dangling references and unknown
types are rejected here, as a structural property of the ingested
description itself -- not as an enforcement of the epistemic promotion
rules in docs/EPISTEMIC_MODEL.md, which belong to Level 2/3 and to the
narrower check already done in graph_store.GraphStore.create_relationship.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from trust_fracture.schema import (
    NON_INGESTIBLE_RELATIONSHIP_TYPES,
    EpistemicStatus,
    NodeType,
    RelationshipType,
)

EnumT = TypeVar("EnumT", bound=Enum)

Scalar = str | int | float | bool | None


class NormalizationError(ValueError):
    """Raised when a raw scenario dict does not conform to the graph
    schema in docs/GRAPH_MODEL.md."""


@dataclass(frozen=True)
class NodeRecord:
    node_type: NodeType
    node_id: str
    properties: dict[str, Scalar]
    provenance: str


@dataclass(frozen=True)
class RelationshipRecord:
    rel_type: RelationshipType
    relationship_id: str
    source_id: str
    target_id: str
    epistemic_status: EpistemicStatus
    provenance: str
    run_id: str | None
    observed_at: str | None


@dataclass(frozen=True)
class ScenarioGraph:
    nodes: tuple[NodeRecord, ...]
    relationships: tuple[RelationshipRecord, ...]


def _require_str(value: Any, field: str, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise NormalizationError(f"{context}: {field!r} must be a non-empty string, got {value!r}")
    return value


def _require_enum(value: Any, enum_cls: type[EnumT], field: str, context: str) -> EnumT:
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid = ", ".join(member.value for member in enum_cls)
        raise NormalizationError(
            f"{context}: {field!r}={value!r} is not one of: {valid}"
        ) from exc


def normalize_scenario(raw: dict[str, Any], *, source: str) -> ScenarioGraph:
    raw_nodes = raw.get("nodes")
    raw_relationships = raw.get("relationships")
    if not isinstance(raw_nodes, list):
        raise NormalizationError(f"{source}: 'nodes' must be a list")
    if not isinstance(raw_relationships, list):
        raise NormalizationError(f"{source}: 'relationships' must be a list")

    nodes: list[NodeRecord] = []
    seen_ids: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        context = f"{source}: nodes[{index}]"
        if not isinstance(raw_node, dict):
            raise NormalizationError(f"{context}: must be an object")
        node_id = _require_str(raw_node.get("id"), "id", context)
        if node_id in seen_ids:
            raise NormalizationError(f"{context}: duplicate node id {node_id!r}")
        seen_ids.add(node_id)
        node_type = _require_enum(raw_node.get("type"), NodeType, "type", context)
        provenance = _require_str(raw_node.get("provenance"), "provenance", context)
        properties = raw_node.get("properties", {})
        if not isinstance(properties, dict):
            raise NormalizationError(f"{context}: 'properties' must be an object")
        nodes.append(
            NodeRecord(
                node_type=node_type,
                node_id=node_id,
                properties=dict(properties),
                provenance=provenance,
            )
        )

    relationships: list[RelationshipRecord] = []
    seen_rel_ids: set[str] = set()
    for index, raw_rel in enumerate(raw_relationships):
        context = f"{source}: relationships[{index}]"
        if not isinstance(raw_rel, dict):
            raise NormalizationError(f"{context}: must be an object")
        rel_id = _require_str(raw_rel.get("id"), "id", context)
        if rel_id in seen_rel_ids:
            raise NormalizationError(f"{context}: duplicate relationship id {rel_id!r}")
        seen_rel_ids.add(rel_id)
        rel_type = _require_enum(raw_rel.get("type"), RelationshipType, "type", context)
        if rel_type in NON_INGESTIBLE_RELATIONSHIP_TYPES:
            raise NormalizationError(
                f"{context}: {rel_type.value} cannot be declared by a scenario "
                "file -- it exists only once the engine has actually derived "
                "or observed it (docs/GRAPH_MODEL.md), not as a hand-asserted "
                "fact in ingested input"
            )
        source_id = _require_str(raw_rel.get("source"), "source", context)
        target_id = _require_str(raw_rel.get("target"), "target", context)
        if source_id not in seen_ids:
            raise NormalizationError(f"{context}: source {source_id!r} is not a declared node")
        if target_id not in seen_ids:
            raise NormalizationError(f"{context}: target {target_id!r} is not a declared node")
        epistemic_status = _require_enum(
            raw_rel.get("epistemic_status"), EpistemicStatus, "epistemic_status", context
        )
        provenance = _require_str(raw_rel.get("provenance"), "provenance", context)
        run_id = raw_rel.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            raise NormalizationError(f"{context}: 'run_id' must be a string or null")
        observed_at = raw_rel.get("observed_at")
        if observed_at is not None and not isinstance(observed_at, str):
            raise NormalizationError(f"{context}: 'observed_at' must be a string or null")
        relationships.append(
            RelationshipRecord(
                rel_type=rel_type,
                relationship_id=rel_id,
                source_id=source_id,
                target_id=target_id,
                epistemic_status=epistemic_status,
                provenance=provenance,
                run_id=run_id,
                observed_at=observed_at,
            )
        )

    return ScenarioGraph(nodes=tuple(nodes), relationships=tuple(relationships))
