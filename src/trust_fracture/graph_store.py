"""Level 1 persistence layer: the only module that talks to Relate directly.

Per docs/ARCHITECTURE.md layer 3 ("Graph persistence"): no other layer in
this project opens a Relate connection directly, and this module does not
interpret scenario input itself (that is layers 1-2, ingestion/
normalization) or evaluate rules (layer 5).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any

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

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit related statements together on this store's connection."""
        if not self._db.autocommit:
            raise GraphStoreError("nested graph transactions are unsupported")
        self._db.autocommit = False
        try:
            yield
            self._db.commit()
        except BaseException:
            self._db.rollback()
            # Enabling autocommit can commit an open transaction.
            self._db.autocommit = True
            raise
        else:
            self._db.autocommit = True

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

    def _require_exactly_one_node(self, node_id: str) -> None:
        count = self._db.execute(
            "MATCH (n {id: $id}) RETURN count(n) AS n", {"id": node_id}
        ).single()["n"]
        if count == 0:
            raise GraphStoreError(f"no node with id {node_id!r} exists")
        if count > 1:
            raise GraphStoreError(
                f"id {node_id!r} matches {count} nodes -- ids must be "
                "globally unique (docs/GRAPH_MODEL.md); refusing to create "
                "a relationship that would silently fan out across all of them"
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

        # Confirmed by the Level 2 red-team review: without this check,
        # MATCH (a {id: $sid}), (b {id: $tid}) resolves ambiguously when
        # ids collide across node types (nothing in GraphStore itself
        # enforces global id uniqueness -- only normalization.py's
        # scenario-ingestion path does, which Level 2+ engine code calling
        # this method directly does not go through), and the subsequent
        # CREATE then runs once per matched (a, b) pair -- silently
        # writing one relationship per collision instead of the single
        # edge the caller asked for.
        self._require_exactly_one_node(source_id)
        self._require_exactly_one_node(target_id)

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

    # Hard ceiling on bounded-reachability hop counts, independent of
    # whatever max_hops a Level 2 caller requests. Relate itself allows up
    # to 2000 (--max-traversal-depth); this project's own cap is far
    # tighter because the explicit design decision deferred in
    # docs/GRAPH_MODEL.md is now made here: the scenario corpus (Level 4)
    # is tens of nodes, not a production-scale graph, and an investigator
    # asking "is X reachable from Y" has no use for a path the Cypher
    # planner had to search 500 hops to find in a graph this small --
    # that signals a malformed query, not a deep investigation.
    MAX_ALLOWED_HOPS = 20

    def paths_between(
        self,
        source_id: str,
        target_id: str,
        *,
        max_hops: int,
        relationship_types: frozenset[RelationshipType],
    ) -> list[dict[str, Any]]:
        """Bounded-reachability raw path fetch, restricted to
        `relationship_types` and traversed without regard to each edge's
        stored direction (see schema.PROPAGATION_RELATIONSHIP_TYPES for
        why: stored direction encodes who acted, not which way influence
        could propagate). Returns each path in relate's lossless
        `Path.to_dict()` shape -- callers (query.py) turn this into a
        typed, epistemically-labeled result; this method does not
        interpret or label anything, per docs/ARCHITECTURE.md's layer
        split between persistence (3) and query (4).
        """
        if not isinstance(max_hops, int) or not (1 <= max_hops <= self.MAX_ALLOWED_HOPS):
            raise GraphStoreError(
                f"max_hops must be an integer between 1 and {self.MAX_ALLOWED_HOPS}, "
                f"got {max_hops!r}"
            )
        if not relationship_types:
            raise GraphStoreError("relationship_types must be non-empty")
        # relationship_types comes from a closed enum (schema.RelationshipType)
        # and max_hops is validated as a bounded int above -- both safe to
        # interpolate. Cypher's variable-length pattern bound is not
        # parameterizable (confirmed empirically: relate, like standard
        # Cypher, requires a literal integer range here).
        type_pattern = "|".join(rel_type.value for rel_type in relationship_types)
        cursor = self._db.execute(
            "MATCH p = (src {id: $source_id})-[:%s*1..%d]-(dst {id: $target_id}) RETURN p"
            % (type_pattern, max_hops),
            {"source_id": source_id, "target_id": target_id},
        )
        return [row["p"].to_dict() for row in cursor]

    def outgoing_related_ids(
        self, node_id: str, rel_type: RelationshipType
    ) -> tuple[str, ...]:
        """The `id` of every node reachable from `node_id` by one outgoing
        `rel_type` edge. Used by authority.py for REQUIRES_PERMISSION,
        HAS_PERMISSION, and GOVERNED_BY -- a single generic query rather
        than three near-identical ones, since all three are "one hop,
        fixed relationship type, return the neighbor's id"."""
        cursor = self._db.execute(
            f"MATCH (a {{id: $id}})-[:{rel_type.value}]->(b) RETURN b.id AS id",
            {"id": node_id},
        )
        return tuple(row["id"] for row in cursor)

    def common_trace_events(self, node_a_id: str, node_b_id: str) -> tuple[str, ...]:
        """Every TraceEvent id that both `node_a_id` and `node_b_id` are
        OBSERVED_IN -- the structural backing Level 3's promotion rule
        (docs/EPISTEMIC_MODEL.md, B -> C) checks for: an edge between two
        nodes counts as observed only if a real trace recorded both
        endpoints together, never from temporal order alone.
        """
        cursor = self._db.execute(
            "MATCH (a {id: $a})-[:OBSERVED_IN]->(t:TraceEvent)<-[:OBSERVED_IN]-(b {id: $b}) "
            "RETURN DISTINCT t.id AS id",
            {"a": node_a_id, "b": node_b_id},
        )
        return tuple(row["id"] for row in cursor)

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
