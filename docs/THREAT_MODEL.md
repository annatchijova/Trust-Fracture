# Trust Fracture — Threat Model

This threat model is scoped exclusively to AI agent systems, per the
project's stated scope: it does not cover generic network security, host
compromise, or attacks against third-party services. All scenarios built
against this model use synthetic data, synthetic credentials, and
locally-run components only.

## Assets protected

- Files (synthetic, local to a scenario's sandbox).
- Credentials (always synthetic; never a real secret).
- Synthetic secrets used as scenario markers (e.g. a canary value a
  scenario checks for, to prove a flow occurred, not a real credential).
- Internal resources a scenario models (a modeled database, a modeled
  internal API).
- Privileged tools available to an agent.
- Sensitive operations an agent or tool can perform.

## Actors

- **Authorized user** — the human or upstream system whose authority an
  agent is meant to act under.
- **Agent** — the AI system that receives inputs from multiple sources and
  can invoke tools.
- **Tool** — a capability the agent can invoke, with its own permissions.
- **External content provider** — a document, API, search result, or other
  data source the agent reads but does not report to.
- **Attacker** — controls one or more lower-trust sources. The attacker
  never has direct access to the agent's configuration, policies, or
  credentials; their only lever is the content that flows through a
  lower-trust channel.

## Attacker capabilities — scoped per scenario, never global

What the attacker *can* modify, and only this, stated explicitly per
scenario at the point each scenario is built:

- The text of a document the agent retrieves.
- The content of a tool's response.
- Metadata or content of a retrieved artifact.
- The content of a file in a modeled repository.
- A message passed from one modeled agent to another.

What the attacker can *never* modify, in any scenario:

- System policies.
- Real permission grants (a scenario may model an agent *behaving as if* a
  permission check passed, but the underlying policy record is never
  attacker-writable).
- Privileged configuration.
- Evidence already sealed by the investigation engine (Level 3 onward).

## Attacker goals — modeled, never executed for real

- Induce an unauthorized tool invocation.
- Alter the parameters of a privileged operation.
- Reach a resource outside the agent's intended scope.
- Cause an information transfer that contradicts a stated policy.

No scenario uses a real credential, a real third-party system, or an
attack that could cause actual damage. Every "attack" in this project is a
synthetic input crafted to test whether the modeled agent system's
boundaries hold — the thing being evaluated is the boundary, not a real
target.

## Trust boundaries considered

- External content vs. the agent's execution context.
- Data vs. instruction, within a single piece of content.
- Agent vs. tool.
- Tool vs. protected resource.
- Agent vs. agent, where authority differs between them.

Each boundary gets a formal definition or an explicit evaluation rule in
`docs/GRAPH_MODEL.md` and `docs/EPISTEMIC_MODEL.md` — a boundary is never
left as an implicit assumption in the engine's code.

## Explicit non-goals

- Not a general network or host security scanner.
- Not a SIEM, EDR, or DFIR platform.
- Not a universal code analyzer or CVE scanner.
- Not a framework for attacking services the project does not control.
- The project does not claim an agent is vulnerable by default — it
  provides a method for investigating whether, and under what evidence, a
  specific authority boundary was crossed.
