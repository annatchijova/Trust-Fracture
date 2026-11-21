"""Level 1 persistence layer: the only module that talks to Relate directly.

Per docs/ARCHITECTURE.md layer 3 ("Graph persistence"): no other layer in
this project opens a Relate connection directly, and this module does not
interpret scenario input itself (that is layers 1-2, ingestion/
normalization) or evaluate rules (layer 5).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType

import relate

from trust_fracture.schema import (
    SCHEMA_VERSION,
    EpistemicStatus,
    NodeType,
    OBSERVATION_ONLY_TYPES,
    RelationshipType,
)

Scalar = str | int | float | bool | None
Properties = Mapping[str, Scalar]

# Property keys are spliced into Cypher statement text (see create_node) --
# Relate's parameter binding covers values, never map keys. A key outside
# this shape is rejected before it reaches the query string, closing the
# Cypher-injection path confirmed in the Level 1 red-team review (a crafted
# key such as "a:1}) MATCH (v) DETACH DELETE v //" otherwise breaks out of
# the property map).
_SAFE_PROPERTY_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Reserved node metadata fields the trusted layers attach at creation time
# (docs/GRAPH_MODEL.md "Metadata on every relevant relationship" /
# docs/ARCHITECTURE.md layer 2). A scenario-supplied property under one of
# these names must never be allowed to silently win a dict-merge against
# the caller-supplied, trusted value -- confirmed reachable in the Level 1
# red-team review.
_RESERVED_NODE_FIELDS = frozenset({"id", "provenance", "schema_version"})


class GraphStoreError(ValueError):
    """Raised when a caller tries to persist a node or relationship that
    violates the epistemic classification rules in docs/GRAPH_MODEL.md, or
    supplies a property key that is unsafe or reserved, before any write
    reaches Relate."""


class GraphStore:
    """Thin, schema-aware wrapper around a single Relate connection.

    One GraphStore wraps one Relate database (one writer process, per the
    relate-db SDK's own constraint) and is responsible for attaching the
    mandatory metadata (epistemic_status, provenance, schema_version) at
    node/relationship creation time, never after the fact.
    """

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self._db = relate.connect(str(path), read_only=read_only)

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    def create_node(
        self,
        node_type: NodeType,
        node_id: str,
        properties: Properties = {},
        *,
        provenance: str,
    ) -> None:
        for key in properties:
            if key in _RESERVED_NODE_FIELDS:
                raise GraphStoreError(
                    f"property key {key!r} is reserved for trusted metadata "
                    "attached at creation time and cannot be supplied as a "
                    "scenario property (docs/GRAPH_MODEL.md)"
                )
            if not _SAFE_PROPERTY_KEY.match(key):
                raise GraphStoreError(
                    f"property key {key!r} is not a safe identifier "
                    f"(must match {_SAFE_PROPERTY_KEY.pattern})"
                )

        params: dict[str, Scalar] = {
            "id": node_id,
            "provenance": provenance,
            "schema_version": SCHEMA_VERSION,
            **properties,
        }
        assignments = ", ".join(f"{key}: ${key}" for key in params)
        self._db.execute(
            f"CREATE (n:{node_type.value} {{{assignments}}})",
            params,
        )

    def create_relationship(
        self,
        rel_type: RelationshipType,
        source_id: str,
        target_id: str,
        *,
        relationship_id: str,
        epistemic_status: EpistemicStatus,
        provenance: str,
        run_id: str | None = None,
        observed_at: str | None = None,
    ) -> None:
        if rel_type in OBSERVATION_ONLY_TYPES:
            if epistemic_status is not EpistemicStatus.FACT or observed_at is None:
                raise GraphStoreError(
                    f"{rel_type.value} exists only when a real trace backs it "
                    "(docs/GRAPH_MODEL.md): requires epistemic_status=FACT "
                    "and a concrete observed_at timestamp, got "
                    f"epistemic_status={epistemic_status.value!r}, "
                    f"observed_at={observed_at!r}"
                )

        params: dict[str, Scalar] = {
            "sid": source_id,
            "tid": target_id,
            "id": relationship_id,
            "epistemic_status": epistemic_status.value,
            "provenance": provenance,
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "observed_at": observed_at,
        }
        self._db.execute(
            """
            MATCH (a {id: $sid}), (b {id: $tid})
            CREATE (a)-[r:%s {
                id: $id,
                epistemic_status: $epistemic_status,
                provenance: $provenance,
                schema_version: $schema_version,
                run_id: $run_id,
                observed_at: $observed_at
            }]->(b)
            """
            % rel_type.value,
            params,
        )

    def count_nodes(self, node_type: NodeType) -> int:
        row = self._db.execute(
            f"MATCH (n:{node_type.value}) RETURN count(n) AS n"
        ).single()
        count = row["n"]
        assert isinstance(count, int)
        return count

    def get_node(self, node_id: str) -> dict[str, Scalar] | None:
        # relate's Cursor.single() raises ResultNotSingleError on zero rows
        # (verified empirically against relate-db 1.2.0, not assumed from
        # the skill doc's prose alone) -- fetch(2) and check the count
        # ourselves instead of relying on single()'s exception as control
        # flow for the ordinary "not found" case.
        rows = self._db.execute(
            "MATCH (n {id: $id}) RETURN n AS n", {"id": node_id}
        ).fetch(2)
        if not rows:
            return None
        node = rows[0]["n"]
        return dict(node.properties)
