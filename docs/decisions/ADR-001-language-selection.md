# ADR-001: Implementation Language Selection

## Status

Accepted (subject to the reopen condition in this document).

## Skill used

This decision was produced by executing the `language-selection` skill
(`~/.claude/skills/language-selection/SKILL.md`), followed by its 10-step
procedure: problem-shape classification, concrete force extraction, candidate
expansion beyond the three languages the mega-prompt named, the
contract-based explanation for unfamiliar-cost candidates, rival naming with
falsification attempts, and an explicit reopen condition. No step was
skipped or simulated.

## 1. Is the language actually open?

Not imposed by the hackathon rules. Relate itself imposes a floor: whichever
language we pick must have a working path to Relate's embedded engine. This
floor is satisfied by Rust, Python, Node.js/TypeScript, Java, Go, Swift, and
.NET (verified below), so the choice among the three candidates the
mega-prompt named remains genuinely open.

## 2. Problem shape, per component

- **Relate persistence layer**: already solved — Relate's own engine is a
  Rust-core embedded Cypher database (verified against the live repo, see
  Evidence). We are a *client* of this engine, not an implementer of a graph
  store.
- **Investigation engine** (path reconstruction, authority analysis, boundary
  detection, min-cut/dominator evaluation, epistemic classification): a
  graph-algorithms-over-retrieved-data problem, orchestration-heavy, not
  hostile-binary-parsing-heavy. The "untrusted input" in this domain (per the
  mandatory threat model, §7 of the mega-prompt) is synthetic scenario
  text/JSON content, not attacker-controlled memory-unsafe binary input. This
  matters: it removes the single strongest force that would normally pull a
  security tool toward Rust (memory safety under hostile parsing).
- **Deterministic/sealed core** (no floats, canonical serialization,
  SHA-256 seal): an exact-arithmetic, non-throughput-bound problem — the
  `deterministic-core` skill names this shape explicitly as a case where
  Python's standard library (`fractions.Fraction`, `hashlib`) is already a
  correct fit, not a compromise.
- **CLI/presentation**: argument parsing and structured text/JSON output, not
  a rendering-heavy problem (mega-prompt explicitly rejects a heavy frontend).

No component's shape requires GPU, distributed/actor concurrency, or formal
proof — those candidate families were considered and dropped at this step for
lack of a matching force.

## 3. Decisive forces (concrete)

1. **Relate SDK maturity**: verified against relatedb.ai docs and the live
   `relatedb/relate` GitHub repo (416 stars, 36 forks, 535 commits on main —
   not a toy project). First-class, same-repo-maintained SDKs: **Rust**
   (native crate, explicit transactions, cancellation tokens) and **Python**
   (PyO3-based native extension, Arrow IPC). JavaScript/Node is also
   first-class (native bindings, Node 18+); TypeScript gets this only as a
   typed wrapper around untyped native bindings, not a first-class SDK of its
   own. Java/Go/.NET/Swift are community clients on top of the C ABI —
   explicitly second-tier.
2. **No built-in graph algorithms in Relate**: the README documents Cypher
   pattern matching only — no dedicated path-finding, dominator, or min-cut
   primitives. Per the mega-prompt's own rule (§9), any algorithm run outside
   Relate must be justified, fed from the persisted graph, and
   result-verified. This is true regardless of which candidate language wins;
   it is not a force that discriminates between them, but it does mean "pick
   the language with the best primitives/tests for hand-rolled graph
   algorithms over retrieved data" is a real force.
3. **Deterministic, sealed decision path** (CLAUDE.md §5.2, mandatory for
   this repo): no float may enter a sealed value; ratios/weights must use
   exact arithmetic; canonical typed+versioned serialization; SHA-256 sealing
   with an independent, stdlib-only verifier.
4. **Falsifiable/adversarial/property-based/metamorphic testing is mandated**
   as the primary quality gate (mega-prompt §12), not incidental — the spec
   explicitly wants tests designed to refute conclusions, not just confirm
   the happy path.
5. **Solo build, ~3 calendar weeks** (2026-11-20 start referenced against the
   hackathon's 2026-11-11 opening, 2026-12-11 18:00 PST deadline), with
   several other competitions running in parallel (per project memory). Build
   velocity and debuggability under time pressure are real, not soft,
   constraints.
6. **Judge reproducibility**: a judge with general technical skill but not
   necessarily deep security-research background must clone, install, and
   run this without personal assistance (mega-prompt §22). Relate's own
   installer (`curl | bash`) is required in every scenario regardless of our
   language choice, which caps how much "zero-dependency" advantage a static
   binary can actually buy us here.
7. **Memory-constrained Linux dev machine**: real but not decisive for
   *our* code — the graphs here are synthetic demonstration scenarios (tens
   to low hundreds of nodes per the three required scenarios), not
   production-scale graphs. The memory-hungry component, if any, is Relate's
   own engine, which is Rust regardless of which language calls it.

## 4. Candidates surfaced

```
Candidate: Rust
Why it entered the search: named by the mega-prompt; is Relate's own
  native-SDK language; "security tool" corpus-prior pull.
What it buys: compile-time enforcement of the numeric/ownership discipline
  §5.2 needs anyway (hard to accidentally let a float slip into a typed
  struct); single static binary; lowest runtime memory footprint for our
  own process.
What it costs: borrow-checker friction on graph-traversal code with shared,
  mutable, cyclic structure (arenas/Rc<RefCell> patterns) under a 3-week
  solo deadline; less mature property-based testing ergonomics than
  Python's `hypothesis` for the adversarial/metamorphic suite §12 demands
  as the primary gate, not a nice-to-have.
Where the guarantee ends: memory safety says nothing about *logical*
  authority-boundary correctness, which is the actual subject matter here.
Why not the obvious alternative (Python): Python can enforce the same
  numeric discipline at the type/runtime-check level (Fraction, explicit
  dataclasses) rather than at compile time — a real but survivable
  downgrade, traded for materially faster iteration on the actual hard part
  (the investigation logic, not the persistence layer, which Relate already
  gives us in Rust for free).
How we'd verify the implementation: `cargo test`, `proptest`, `clippy -D
  warnings`, `cargo audit`.
```

```
Candidate: TypeScript / Node.js
Why it entered the search: named by the mega-prompt; Relate's JS bindings
  are first-class (same tier as Rust/Python, ahead of Java/Go/.NET/Swift).
What it buys: a future lightweight visualization layer (§14 WASM/graph-view
  option) would share a language and type definitions with the backend.
What it costs: no first-party exact-rational type (bignum/Fraction is a
  dependency, not stdlib) for the §5.2 deterministic core — this has to be
  built and trusted by hand; the numeric model defaults to IEEE-754 doubles
  everywhere unless deliberately routed around; weaker fit for the stated
  CLI-first/local-first priority (§14 explicitly tells us not to build a
  frontend before the engine works, which removes TypeScript's main
  distinguishing advantage).
Where the guarantee ends: type soundness is erased at runtime and does not
  extend to the npm dependency surface, which is wide for a hackathon
  timeline to audit.
Why not Python: Python's `fractions.Fraction` and `hashlib` solve the
  deterministic-core numeric force out of the standard library; TypeScript
  would need an added dependency (e.g. a bignum/rational library) to reach
  the same guarantee, and the visualization use case that would justify
  TypeScript is explicitly deprioritized until the engine is done.
How we'd verify the implementation: `vitest`/`fast-check` (its
  property-based library), `tsc --strict`, `eslint`.
```

```
Candidate: Python
Why it entered the search: named by the mega-prompt; first-class Relate
  SDK (PyO3, same repo, same tier as Rust); stdlib already contains the two
  primitives the deterministic core needs (Fraction, hashlib).
What it buys: fastest realistic solo-build velocity for an
  orchestration/logic-heavy engine; `hypothesis` is the most mature
  property-based + stateful + metamorphic testing library available in any
  of the three candidates, directly matching §12's requirement that tests
  be designed to refute conclusions; exact arithmetic (Fraction) and
  canonical serialization (stdlib json with sort_keys, or a small explicit
  type-tagged encoder) without adding a dependency.
What it costs: no compile-time enforcement that a float never reaches a
  sealed value — this becomes a runtime-checked invariant (a boundary
  assertion plus a dedicated determinism test that hashes the same result
  twice and across process restarts), not a type-system guarantee.
  Distribution to judges needs a Python interpreter + `pip install`
  (mitigated: a pinned `requirements.txt` plus a `venv` bootstrap script is
  a two-command judge experience, and they already need Relate's own
  installer regardless).
Where the guarantee ends: Python gives us nothing by itself for the actual
  security conclusions — authority modeling, boundary definitions, and
  evidence linkage still have to be designed correctly; the language only
  affects how fast and how testably we can build and refute that design.
How we'd verify the implementation: `pytest`, `hypothesis` (property +
  stateful testing), `mypy --strict` (static typing where it helps,
  without pretending it validates untrusted input), a standalone
  stdlib-only seal verifier script per CLAUDE.md §5.2.
```

## 5. Language vs. environment

The determinism guarantee we actually need does not come from any of these
three languages as such — it comes from: (a) never putting a `float` in a
value that gets hashed, (b) one canonical, versioned, type-tagged encoder,
and (c) `sha256` over those canonical bytes. All three languages can provide
(a)-(c); Rust enforces (a) partially at compile time via its type system,
Python and TypeScript enforce it via an explicit boundary check plus a
repeated-run determinism test. Relate's own persistence durability (WAL,
snapshot/WAL architecture, `full` fsync mode) is a property of the Relate
engine, not of whichever client language calls it, and holds identically no
matter which SDK we use.

## 6. Decomposition considered

A Rust-core-under-Python-CLI split was considered (write algorithms in Rust,
orchestrate from Python) and rejected for this project: it would add a
second toolchain, an FFI boundary to review, and duplicated domain models,
to solve a performance force that was never established (synthetic,
small-scale demonstration graphs; no measured bottleneck). The mega-prompt's
own constraint (§14, §20) is to avoid infrastructure that does not resolve a
concrete problem — this split does not resolve one here. No split is
adopted. If a genuine Rust-shaped need appears later (see reopen condition),
it is re-evaluated then, not pre-built now.

## 7. Rivals and falsification attempt on the winner

**Rejected: TypeScript/Node.** Lost on the deterministic-core force (no
stdlib exact-rational type) and on the explicit mega-prompt instruction to
not prioritize a frontend before the engine exists, which was TypeScript's
only distinguishing advantage over Python here. Strongest argument for it:
if the visualization layer in §14 turns out to be "decisive for the
demonstration" after all, sharing one language end-to-end would avoid a
second toolchain at that point.

**Rejected: Rust.** Lost on build-velocity and testing-ergonomics forces
under a 3-week solo deadline where the mandated primary quality gate is
adversarial/property-based/metamorphic testing, not raw performance or
memory-safety-under-hostile-binary-input (which this domain's threat model
does not actually present). Strongest argument for it: compile-time
enforcement of the no-float invariant is a strictly stronger guarantee than
a runtime-checked one, and a single static binary is marginally easier for
a judge to run than a Python environment.

**Attempt to falsify the winner (Python):** Is the velocity advantage
measured or assumed? It is assumed, based on the author's documented prior
delivery pattern on multi-level, test-heavy, solo-built hackathon projects
in both Python and Rust (project memory shows both used successfully under
deadline pressure) — not a Python-specific claim, an honest "unmeasured for
this project" plus a reopen trigger (below) if the assumption breaks during
the Phase 3 vertical spike. Is this chosen for prestige or because it is
easy to generate? No — Rust is at least as easy for the model to generate;
the choice is driven by the testing-ergonomics and stdlib-exact-arithmetic
forces, which are concrete, not generation convenience. Does Python's
first-class Relate SDK actually exist and work, or is this claim stale? It
is corroborated by the live `relatedb/relate` repository (PyO3-based,
maintained in the same repo as the Rust SDK, not a bolted-on
community client) — not asserted from memory alone.

## 8. Tie-break

The forces discriminate (testing ergonomics + stdlib exact arithmetic +
build velocity vs. compile-time float enforcement + static binary); this is
not a genuine tie, so no tie-breaker is invoked.

## 9. Depth

Full derivation applied: this is a security-relevant, hackathon-judged,
three-week architectural commitment with a mandated deterministic/sealed
core — exactly the stakes level this skill reserves full depth for.

## Decision

**Chosen: Python (3.12+), calling Relate's first-class `relate-db` PyO3
SDK, with a CLI built on `click` or `argparse`.**

Guarantees we're relying on:
- Exact rational/count arithmetic for anything sealed — provided by
  Python's `fractions.Fraction` (stdlib), enforced by a boundary check plus
  a dedicated same-input-twice / fresh-process determinism test, not by the
  type system.
- Canonical, type-tagged, versioned serialization — provided by a small
  hand-written encoder in our code (not delegated to any third-party
  serializer), per CLAUDE.md §5.2.
- SHA-256 sealing and an independent stdlib-only verifier — provided by
  `hashlib`.
- Graph persistence, WAL durability, snapshot/WAL recovery — provided by
  Relate's engine (Rust), not by our client language.
- Property-based and metamorphic adversarial testing as the primary gate —
  provided by `hypothesis`.

Guarantees we're NOT getting:
- Compile-time rejection of a stray float reaching a sealed value (Rust
  would give us this; we substitute a runtime boundary assertion and a
  determinism test instead, and treat any future violation as a test
  failure, not a silent bug).
- A dependency-free single-binary judge experience (Python needs an
  interpreter and `pip install`; mitigated with a pinned `requirements.txt`
  and a one-command bootstrap script, and judges already need Relate's own
  installer regardless of our language).

Rejected:
- **TypeScript/Node** — lost on the deterministic-core numeric force and
  the explicit "no frontend before the engine" instruction. Strongest
  argument for it: a shared language if a browser/WASM visualization
  becomes decisive later.
- **Rust** — lost on build-velocity and testing-ergonomics forces under the
  3-week solo deadline with adversarial/property testing as the mandated
  primary gate. Strongest argument for it: compile-time float-safety and a
  single static binary.

Accepted cost: the no-float invariant is enforced by a test and a boundary
assertion, not by the compiler; this is written down explicitly so it is
never silently assumed to be a stronger guarantee than it is.

Verification plan: `pytest` for unit/integration/e2e tests per the
mega-prompt's test pyramid (§12); `hypothesis` for property-based and
metamorphic tests on path-finding, boundary classification, and
authority-rule invariants; `mypy --strict` for the static-typing layer it
can usefully provide; a standalone stdlib-only seal-verification script
independent of the producing code (CLAUDE.md §5.2); a repeated-run /
fresh-process determinism check asserting identical seals.

Boundaries: none introduced — single-language implementation. Relate's own
process boundary (our Python process calling into the PyO3 native
extension) is Relate's existing, already-shipped boundary, not one we are
adding.

**Reopen if:** the Phase 3 vertical integration spike (persist nodes,
persist relationships, close/reopen, query, retrieve a path, verify the
result — mega-prompt §19 Fase 3) finds the `relate-db` Python SDK missing a
capability the Rust or Node SDK has (e.g., envelope-mode JSON only reachable
by shelling out to the CLI rather than through native bindings, or Arrow IPC
overhead materially slowing interactive CLI use at our scale). The documented
fallback in that case is NOT an automatic switch to Rust — it is first to
shell out to the `relate` CLI binary itself (`--mode envelope` JSON, or
`relate serve --mcp stdio`) from Python via `subprocess`, since the CLI is
Relate's most stable, documented interface regardless of SDK maturity; only
if that fallback also fails to meet a verified need does this ADR get
revisited with Rust as the concrete alternative.

## Evidence

- `relatedb.ai/docs/get-started/install/` (fetched 2026-11-20): confirms
  Relate is an embedded Cypher graph database; CLI + SDKs for Python
  (`relate-db`), Node.js, Rust, Java, Go, Swift, .NET; MCP via
  `relate serve --mcp stdio`; `.rl` file persistence; WAL durability modes.
- `github.com/relatedb/relate` (fetched 2026-11-20): Rust core, 416
  stars / 36 forks / 535 commits on main; first-class same-repo SDKs are
  Rust and Python (PyO3, Arrow IPC); JS/WASM also native; Java/Go/.NET/Swift
  are C-ABI community clients; README documents Cypher pattern matching only
  — no dedicated path-finding/graph-algorithm primitives; snapshot+WAL
  architecture with configurable durability.

## Confirmation

Decision produced by executing `~/.claude/skills/language-selection/SKILL.md`
in full (all 10 steps), not simulated or asserted from memory.
