# Trust Fracture — Epistemic Model

This model governs every conclusion the engine is allowed to state. It is
not a presentation detail — it is enforced in the graph schema
(`docs/GRAPH_MODEL.md`) and in the evidence layer (Level 3 of
`docs/LEVELS.md`), and no code path may bypass it to produce a more
confident-sounding result.

## The central invariant

**Graph reachability is not proof of exploitability.**

Reachability is a property of the persisted graph model. Exploitability is
a security conclusion that requires evidence beyond the graph: an observed
execution, or a controlled test demonstrating an actual policy violation.
The engine never equates the two, silently or otherwise.

## The five states

### A. Structural fact

A relationship verified from configuration, a policy document, a tool
manifest, or another concrete artifact.

> Example: a tool's manifest grants it write access to a file. This is a
> fact about permission. It does not demonstrate the tool ever wrote the
> file, or that it did so under attacker influence.

### B. Structural possibility

A path the graph shows *could* allow information or influence to
propagate, given the facts entered so far.

> Example: an agent reads external content and also has access to a
> privileged tool. This shows a possible path. It does not show the agent
> obeyed anything the external content said.

### C. Observed behavior

An event backed by a real trace or log entry — something that was recorded
as having actually happened.

> Example: the agent invoked a tool after processing a document. Temporal
> sequence alone is observed behavior, not proof of causation.

### D. Verified policy violation

A controlled execution demonstrates that an operation contradicted an
explicit, applicable policy. This requires evidence that links, together,
all of: source, content, behavior, operation, the authority the operation
required, and the specific policy it violated. Any one of these missing
means the state is not D — it is, at most, C, with the gap stated.

### E. Insufficient evidence

If relationships, traces, permissions, or policies needed for a
conclusion are missing: `ABSTAIN` / `INSUFFICIENT_EVIDENCE`. This is a
valid, first-class result — not a failure of the investigation, and never
silently replaced with a guess.

## Promotion rules (the only way a state may change)

- **B does not become C** without a trace event that actually records the
  behavior, tied by its own stored reference (not inferred from timing
  alone) to the entities on the path.
- **C does not become D** without a policy explicitly identified as
  applicable, and evidence that the observed behavior actually breached
  it — temporal order is never sufficient by itself.
- **Anything may collapse to E** when a required piece of evidence is
  missing. Nothing may be promoted past E by assumption, convenience, or a
  model's confidence in its own narrative.
- No LLM output may perform a promotion. A language model, if used at all,
  narrates an already-reached state; it never reaches one (see
  `docs/ARCHITECTURE.md`, "LLM out of the decision path").

## Confidence and uncertainty

No arbitrary confidence percentages. If an uncertainty metric is
introduced for a specific, scoped purpose, its calibration and
interpretation must be documented at the point it is introduced — a bare
number with no stated meaning is treated as equivalent to not having it.

## What this model forbids outright

- Labeling a structural possibility as an incident.
- Treating the absence of a discovered path as proof of security.
- Letting untrusted data modify the rules that evaluate it — the
  evaluation rules are part of the trusted engine, never data the engine
  ingests.
- Presenting a result without the references needed to trace it back to
  its source evidence.
- Assigning severity (e.g. a CVSS-style score) without a concrete,
  verified violation and sufficient evidence to support it.
