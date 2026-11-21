# Trust Fracture — Graph Model

This is the schema design for the graph persisted in Relate
(`docs/decisions/ADR-001-language-selection.md`). It is a design document:
the queries below illustrate intended shape and have not yet been run
against a live Relate instance — that verification is Level 1's vertical
spike (`docs/LEVELS.md`), and this document will be corrected against real
results once it runs, not assumed correct in advance.

## Node types

Only types with a demonstrable use in the investigation engine are
included; nothing is added speculatively.

| Node | Represents |
|---|---|
| `Agent` | An AI agent participating in the modeled system. |
| `Tool` | A capability an agent can invoke. |
| `DataSource` | Where content originates (a document store, a search index, an API, a repo). |
| `ContentArtifact` | A specific piece of content read by an agent (a document, a tool response, a retrieved snippet). |
| `Instruction` | A directive identified within a `ContentArtifact` — distinct from the artifact itself, since not all content is instructional. |
| `Operation` | A specific action a tool or agent can perform. |
| `Permission` | A grant that an actor possesses. |
| `Resource` | A protected target of an operation (a file, a credential store, an internal API). |
| `Policy` | An explicit rule governing whether an operation is allowed in context. |
| `TrustBoundary` | A formally defined boundary between two domains of trust (see `docs/THREAT_MODEL.md`). |
| `Control` | A mechanism that can interrupt a path (validation, authorization check, isolation, human confirmation, privilege separation). |
| `TraceEvent` | A recorded event from an actual execution. |
| `Evidence` | A reference bundle tying together the facts/traces that support a specific conclusion. |

## Relationship types, classified by epistemic weight

Every relationship below is tagged, in its own stored metadata, with
whether it represents a stored fact, a derived/computed relationship, or
requires inference to interpret — this classification is what the
`EPISTEMIC_MODEL.md` promotion rules actually check against.

| Relationship | Meaning | Classification |
|---|---|---|
| `READS` | An agent or tool reads a `ContentArtifact` or `DataSource`. | Stored fact (from config/trace) or observed (from a trace event) — never inferred. |
| `PRODUCES` | A tool or data source produces a `ContentArtifact`. | Stored fact or observed. |
| `CONTAINS` | A `ContentArtifact` contains an `Instruction`. | Derived — requires content classification; never persisted as fact without the classification step that produced it recorded alongside it. |
| `INVOKES` | An agent invokes a `Tool` or `Operation`. | Observed (from a `TraceEvent`) when it reflects a real run; structural/possible when derived only from capability, and must be tagged as such. |
| `REQUIRES_PERMISSION` | An `Operation` requires a `Permission`. | Stored fact (from a manifest or policy). |
| `HAS_PERMISSION` | An actor holds a `Permission`. | Stored fact. Never conflated with authorization to use it in a given context — that judgment is a derived result of evaluating `GOVERNED_BY` policies, not this edge alone. |
| `TARGETS` | An `Operation` targets a `Resource`. | Stored fact. |
| `GOVERNED_BY` | An `Operation` or `TrustBoundary` is governed by a `Policy`. | Stored fact. |
| `OBSERVED_IN` | A relationship or event is backed by a `TraceEvent`. | This edge is itself the thing that turns "possible" into "observed" — it exists only when a real trace exists, never speculatively. |
| `SUPPORTED_BY` | A conclusion is supported by `Evidence`. | Derived — exists only once evidence has actually been assembled. |
| `DERIVED_FROM` | A computed value (e.g. a reconstructed path) is derived from specific underlying nodes/edges. | Derived, by construction — this edge is how the engine keeps a provenance trail for anything it computes rather than ingests. |
| `CROSSES_BOUNDARY` | A path segment crosses a `TrustBoundary`. | Derived, computed against the formal boundary definition — never asserted by hand. |

A relationship is persisted as `OBSERVED_IN`-backed only when a concrete
`TraceEvent` exists for it. A relationship with no such backing is a
structural/possible edge and is never upgraded in storage — the engine
upgrades the *investigation result*, built on top of the graph, never the
underlying fact it was given.

## Metadata on every relevant relationship

- `id` — unique identifier.
- `type` — the relationship type.
- `source`, `target` — endpoint node ids.
- `evidence_source` — what established this (a config file, a manifest, a
  trace event id, a derivation rule).
- `epistemic_status` — `fact` | `derived` | `requires_inference`.
- `run_id` — present when tied to a specific scenario execution.
- `observed_at` — timestamp, present only when backed by a real trace.
- `provenance` — how this entered the graph (ingestion step, derivation
  rule name and version).
- `schema_version` — the version of this document's schema the entry
  conforms to, so a future schema change never silently reinterprets old
  data.

No arbitrary confidence percentage is stored. If a later level introduces
a scoped uncertainty measure, it is documented at the point it is added,
per `docs/EPISTEMIC_MODEL.md`.

## Illustrative queries (unverified against a live Relate instance)

Bounded reachability between a source and a target, capped in hop count to
avoid combinatorial explosion (the actual cap is a Level 2 design decision,
recorded there once real graph sizes from the scenario corpus are known):

```cypher
MATCH p = (src:DataSource)-[*1..6]->(op:Operation)
WHERE src.id = $source_id AND op.id = $operation_id
RETURN p
```

Permissions required by an operation, and who holds them:

```cypher
MATCH (op:Operation {id: $operation_id})-[:REQUIRES_PERMISSION]->(perm:Permission)
OPTIONAL MATCH (actor)-[:HAS_PERMISSION]->(perm)
RETURN op, perm, actor
```

Trust-boundary crossings along a specific path's nodes (post-processing a
path already retrieved, since boundary evaluation is a derived judgment,
not a stored edge to pattern-match on blindly):

```cypher
MATCH (n)-[r:CROSSES_BOUNDARY]->(b:TrustBoundary)
WHERE n.id IN $path_node_ids
RETURN n, r, b
```

These will be corrected, replaced, or dropped based on what Relate's
actual Cypher dialect and query planner support once Level 1's vertical
spike runs them for real — this document is not a claim that they have
already been executed successfully.

## What Relate does not provide, and how this project compensates

Relate's README documents Cypher pattern matching only — no dedicated
path-finding, dominator, or min-cut algorithm (verified against the live
`relatedb/relate` repository, see `ADR-001`). Where Level 5's control
analysis needs dominator- or cut-style reasoning, that algorithm runs in
this project's own Python code, fed by data retrieved from the persisted
graph via Cypher, with results tagged back to the originating Relate node
ids via `DERIVED_FROM` edges — never a parallel, competing source of
truth. This is documented at the point that algorithm is actually built
(Level 5), per the project's rule against describing a capability before
it exists.
