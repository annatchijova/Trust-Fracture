# Trust Fracture — Build Levels

This document names the destination and the coherent levels toward it. It
follows a destination-driven build: each level is a real, usable state of
the final product, not a throwaway prototype and not a phase defined by a
technical concern ("get it working, then add security"). Every level
inherits the invariants the destination needs — epistemic honesty,
determinism/sealing, no LLM in the decision path — from the first level that
needs them, not as a later hardening pass.

Status tracking for each level lives at the top of its section
(`Not started` / `In progress` / `Done`) and must reflect the real state of
the code, not the plan.

## The destination

A CLI-first investigation tool, backed by a graph persisted in Relate
(see `docs/decisions/ADR-001-language-selection.md`), that lets an
investigator determine whether and how an untrusted input in an AI agent
system could gain influence over a privileged operation — and state,
honestly, what the evidence does and does not support.

The destination always distinguishes five epistemic states for any claim it
makes, never collapsing them into a single pass/fail:

- **Structural fact** — verified from configuration, policy, manifests, or
  tool definitions.
- **Structural possibility** — a path the graph shows could exist.
- **Observed behavior** — an event backed by a real execution trace.
- **Verified policy violation** — evidence links source, content,
  behavior, operation, authority, and the specific policy violated.
- **Insufficient evidence** — a valid result, not a failure to conclude.

Graph reachability is never silently treated as proof of exploitability.
The destination supports: path reconstruction between a source and an
operation, authority analysis, trust-boundary detection, control analysis
(what would interrupt a path), and before/after comparison between a
vulnerable and a corrected configuration — each backed by evidence the
system can show its work for, and each capable of answering "insufficient
evidence" instead of guessing.

## Cross-cutting invariants (every level, from the level that first needs them)

- **Epistemic honesty**: no code path may promote a structural possibility
  to observed behavior, or observed behavior to a verified violation,
  without the evidence that distinguishes them. This is load-bearing from
  Level 1, not added when "real" verdicts arrive in Level 3.
- **No float in a sealed value; canonical, type-tagged, versioned
  serialization; SHA-256 sealing with an independent verifier** — reserved
  in the schema from Level 1 even though sealing itself lands in Level 3,
  so no later migration has to retrofit it onto already-persisted data.
- **LLM out of the decision path** — if a language model is used at all, it
  only narrates an already-sealed result; it never produces, promotes, or
  silently influences an epistemic state or a verdict.
- **Real persistence, not a transient copy** — every level operates on data
  actually persisted in Relate and recoverable after the process exits; no
  level builds its own competing in-memory source of truth.

---

## Level 1 — Persisted, epistemically-typed graph core

**Status: Not started**

Ingest a minimal description of an AI agent system (agents, tools, data
sources, permissions, operations) into Relate as typed nodes and
relationships. Every relationship carries, from this level on, the
metadata fields the whole project needs later: epistemic status (fact vs.
inference), provenance, schema version — even though nothing above this
level consumes them yet.

Standalone usefulness: an investigator can load a system description, close
the process, reopen it, and inspect the persisted graph through the CLI —
with facts and inferences already visibly distinct, not lumped together.

Carries forward: the schema and metadata shape every later level builds on.

## Level 2 — Path and boundary investigation

**Status: Not started**

Bounded reachability queries between a chosen untrusted source and a chosen
privileged operation. Explicit, formally defined trust boundaries (content
vs. instruction, agent vs. tool, tool vs. protected resource, agent vs.
agent) with a rule for when a path crosses one. Authority analysis that
distinguishes *possessing* a permission from being *authorized to use it in
this context*.

Standalone usefulness: an investigator can ask "is there a path from this
source to this operation" and get an answer that keeps structural
possibility clearly separate from anything stronger — the
reachability-is-not-exploitability invariant is enforced here from day one,
not patched in once verdicts exist.

Carries forward: every path element returned here retains Level 1's
epistemic tagging; nothing here speaks more confidently than its evidence.

## Level 3 — Evidence and verdict layer

**Status: Not started**

TraceEvent and Evidence nodes; the full epistemic state machine
(`POTENTIAL_PATH` / `OBSERVED_FLOW` / `VERIFIED_POLICY_VIOLATION` /
`INSUFFICIENT_EVIDENCE`); canonical serialization and SHA-256 sealing of any
finding; a standalone, stdlib-only verifier independent of the code that
produced the seal.

Standalone usefulness: an investigator gets a structured, sealed finding —
not a raw query result — with its epistemic state, its supporting evidence,
and its limitations stated in the same object.

Carries forward: the metadata reserved in Level 1 is now actually populated
and sealed; no retrofit onto existing data was needed.

## Level 4 — Scenario corpus

**Status: Not started**

The three investigation scenarios (tool-output injection, retrieved-document
injection, confused deputy), each with a vulnerable and a protected variant,
plus the mandatory negative controls: benign external content, an
instruction quoted as data rather than executed, an authorized operation, a
structural path with no observed execution, a case with genuinely
insufficient evidence, and an operation blocked by a valid control.

Standalone usefulness: a full, reproducible corpus an investigator can run
the Level 2/3 engine against, immediately showing that the system does not
label every case as a violation.

Carries forward: built entirely on Levels 1-3's real machinery — no mocked
graph, no scripted verdicts.

## Level 5 — Control analysis and before/after comparison

**Status: Not started**

Control nodes and the analysis of which controls interrupt which paths;
dominator- or cut-based analysis where the investigation actually calls for
it (never added merely to be mentioned). The vulnerable-to-corrected
comparison: which paths disappear, which persist, and an independent
re-verification step — a path disappearing from the graph is never by
itself treated as proof the underlying issue is fixed.

Standalone usefulness: an investigator can take a vulnerable configuration,
apply a candidate control, and get an honest comparison of what changed and
what the comparison does and does not prove.

Carries forward: uses Level 3's sealed evidence format for both the "before"
and "after" states, so the comparison itself is auditable.

## Level 6 — CLI ergonomics and export polish (stretch)

**Status: Not started**

Richer report formatting, a documented query cookbook for direct Cypher
investigation, and a lightweight visualization only if it is shown to add
real investigative value rather than decoration.

This is explicitly the first level dropped if time runs out. If reached,
it still inherits every invariant above; if not reached, Level 5 already
stands as a complete, usable product on its own.

---

## Validation cadence

Each new level gets an adversarial review against its own correctness and
against whether it preserved the invariants of the levels before it, as it
is built — not a full regression pass after every level. An integrated
adversarial review and an integrated test run happen once the levels
actually attempted are reached, confirming the construction rather than
discovering for the first time whether the pieces fit.
