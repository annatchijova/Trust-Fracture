# Trust Fracture — Architecture

This document describes components, boundaries, dependencies, and data
flow as designed, prior to implementation. No component described here is
claimed to exist in code yet — see `docs/LEVELS.md` for what has actually
been built.

## Layering

The engine is separated into seven layers so that untrusted data ingested
by the system never acquires authority over how it is evaluated:

1. **Ingestion** — reads a scenario description (agents, tools, data
   sources, content, permissions, policies) from local, synthetic input
   files. This is the only layer that touches raw scenario input.
2. **Normalization** — converts ingested data into the typed node/edge
   shapes defined in `docs/GRAPH_MODEL.md`, attaching `epistemic_status`
   and `provenance` at creation time, never after the fact.
3. **Graph persistence** — writes to, and reads from, Relate. This layer
   owns the only connection to the `.rl` store; no other layer talks to
   Relate directly.
4. **Query** — the bounded reachability, authority, and
   boundary-crossing queries described in `docs/GRAPH_MODEL.md`, executed
   against the persistence layer. Any graph algorithm Relate does not
   provide natively runs here, in Python, fed from data retrieved through
   this same layer, with results tagged back to Relate node ids.
5. **Rule evaluation** — the epistemic promotion rules in
   `docs/EPISTEMIC_MODEL.md` (B→C, C→D, anything→E) live here, as fixed
   logic in this project's own code. Ingested data is never allowed to
   modify this layer's rules; it is only ever an input to them.
6. **Evidence management** — assembles `Evidence` and seals findings per
   `CLAUDE.md` §5.2 (canonical, type-tagged, versioned serialization;
   SHA-256 digest; an independent, stdlib-only verifier). This is where a
   finding becomes immutable.
7. **Presentation** — the CLI. Renders findings, exports reports,
   provides the before/after comparison view. Never computes a verdict
   itself; it only displays what Layer 6 has already sealed.

Data flows strictly downward from 1→7 for ingestion and strictly upward
from 3→7 for a query/investigation — no layer skips another to shortcut a
result.

## LLM out of the decision path

A language model is optional, and used only for: formulating a query in
natural language for the investigator, explaining a relationship in
plain language, summarizing an already-sealed finding, proposing a
hypothesis for the investigator to pursue, or suggesting further
investigation steps.

A language model may never: invent evidence, declare a verdict, modify a
policy, replace an authorization rule, promote a hypothesis to a fact, or
hide uncertainty that the sealed result already states. Concretely: any
LLM call in this project receives a read-only, already-sealed summary as
input, and its output is stored beside the seal, never inside it — a
verifier checks the seal without ever having to trust the model's prose.
Swapping the model backend must change only wording, never a verdict,
seal, or chain of custody; this is a property this project will test
directly once an LLM-backed narration component exists, not assumed.

The core engine (layers 1-6, and the CLI's non-narration features in
layer 7) must function with no LLM available at all.

## Component boundaries and dependencies

- The **ingestion** and **normalization** layers depend on nothing but the
  Python standard library and the project's own schema types.
- The **persistence** layer depends on Relate's Python SDK (`relate-db`,
  per `ADR-001`), with a documented fallback to shelling out to the
  `relate` CLI (`--mode envelope`) if the SDK proves insufficient for a
  verified, concrete need.
- The **query** layer depends on the persistence layer only — it never
  bypasses it to read a `.rl` file directly.
- The **evidence** layer depends on the standard library only
  (`hashlib`, `fractions.Fraction`, a hand-written canonical encoder) —
  no third-party serialization library is trusted with the sealed path.
- The **presentation** (CLI) layer depends on `click` or `argparse` and,
  optionally, the LLM narration component described above — the CLI's
  core investigative commands must not require that optional component.

Every dependency added beyond these must be justified against a concrete
force at the point it is introduced, per the discipline already applied
in `ADR-001`.

## What this architecture defers, and why

- A web or graphical frontend is deferred entirely (Level 6, stretch
  only) — the mega-scope instruction behind this project is explicit
  that the engine must work before any visualization is considered, and
  no visualization has yet been shown to add real investigative value.
- A hosted/paid LLM API is not required for the core product to function;
  if used at all, it is an optional narration layer per the section
  above, not a dependency of the investigation engine itself.
