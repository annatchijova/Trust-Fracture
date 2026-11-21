"""Level 1 persistence layer: the only module that talks to Relate directly.

Per docs/ARCHITECTURE.md layer 3 ("Graph persistence"): no other layer in
this project opens a Relate connection directly, and this module does not
interpret scenario input itself (that is layers 1-2, ingestion/
normalization) or evaluate rules (layer 5).
"""

from __future__ import annotations

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


class GraphStoreError(ValueError):
    """Raised when a caller tries to persist a relationship that violates
    the epistemic classification rules in docs/GRAPH_MODEL.md, before any
    write reaches Relate."""


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
