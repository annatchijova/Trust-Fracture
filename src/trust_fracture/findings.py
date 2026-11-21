"""Level 3, part 2: the epistemic state machine and sealed findings.

Trace observations can promote a route from structural possibility to
observed flow. Policy violations require explicit execution and breach
evidence beyond the current graph model. The assessment uses fixed
rules over records persisted in Relate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from trust_fracture.authority import analyze_authority
from trust_fracture.graph_store import GraphStore
from trust_fracture.query import PathFindingResult, StructuralPath
from trust_fracture.schema import SCHEMA_VERSION


class EpistemicState(str, Enum):
    POTENTIAL_PATH = "POTENTIAL_PATH"
    OBSERVED_FLOW = "OBSERVED_FLOW"
    VERIFIED_POLICY_VIOLATION = "VERIFIED_POLICY_VIOLATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# States ordered by how much evidence each one requires -- used only to
# pick the strongest justified state across multiple candidate paths, not
# to imply any state is automatically "better news."
_STATE_ORDER = {
    EpistemicState.INSUFFICIENT_EVIDENCE: 0,
    EpistemicState.POTENTIAL_PATH: 1,
    EpistemicState.OBSERVED_FLOW: 2,
    EpistemicState.VERIFIED_POLICY_VIOLATION: 3,
}


def classify_path_observation(store: GraphStore, path: StructuralPath) -> EpistemicState:
    """B -> C: a path is OBSERVED_FLOW only if every edge on it has a real
    TraceEvent backing both its endpoints together. One unbacked edge
    caps the whole path at POTENTIAL_PATH -- a path is a chain, and an
    investigator cannot claim the chain was observed end to end from a
    partial trace."""
    for edge in path.edges:
        if not store.common_trace_events(edge.source_id, edge.target_id):
            return EpistemicState.POTENTIAL_PATH
    return EpistemicState.OBSERVED_FLOW


@dataclass(frozen=True)
class PathAssessment:
    state: EpistemicState
    reasons: tuple[str, ...]
    trace_event_ids: tuple[str, ...]


def assess_policy_violation(
    store: GraphStore,
    path: StructuralPath,
    *,
    actor_id: str,
    operation_id: str,
) -> PathAssessment:
    """Collect authority context and explain gaps in policy breach evidence.

    Co-observation and a structural authority gap identify a route to
    investigate. Verifying a violation also requires evidence of execution
    and a breach of an applicable policy.
    """
    reasons: list[str] = []
    trace_event_ids: set[str] = set()

    path_node_ids = {node.node_id for node in path.nodes}
    if actor_id not in path_node_ids:
        reasons.append(f"{actor_id} is not on this path")
    if operation_id not in path_node_ids:
        reasons.append(f"{operation_id} is not on this path")

    for edge in path.edges:
        observed_here = store.common_trace_events(edge.source_id, edge.target_id)
        trace_event_ids.update(observed_here)
        if not observed_here:
            reasons.append(
                f"no TraceEvent backs {edge.source_id} -> {edge.target_id} "
                "(path is not fully OBSERVED_FLOW)"
            )

    authority = analyze_authority(store, actor_id, operation_id)
    if not authority.actor_exists or not authority.operation_exists:
        reasons.append(authority.note)
    elif authority.possesses_all_required_permissions:
        reasons.append(
            f"{actor_id} holds every permission {operation_id} requires -- "
            "no authority gap to report"
        )
    elif not authority.is_governed:
        reasons.append(f"{operation_id} is not GOVERNED_BY any policy on record")

    if not reasons:
        reasons.extend((
            f"{actor_id} lacks permission(s) {operation_id} requires: "
            f"{', '.join(sorted(authority.missing_permission_ids))}",
            f"{operation_id} is GOVERNED_BY: {', '.join(sorted(authority.governing_policy_ids))}",
            "explicit execution and applicable policy breach evidence is required to verify a violation",
        ))

    return PathAssessment(
        state=EpistemicState.INSUFFICIENT_EVIDENCE,
        reasons=tuple(reasons),
        trace_event_ids=tuple(sorted(trace_event_ids)),
    )


@dataclass(frozen=True)
class Finding:
    finding_id: str
    schema_version: str
    source_id: str
    target_id: str
    actor_id: str
    operation_id: str
    max_hops: int
    epistemic_state: EpistemicState
    reasons: tuple[str, ...]
    path_node_ids: tuple[str, ...]
    trace_event_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "actor_id": self.actor_id,
            "operation_id": self.operation_id,
            "max_hops": self.max_hops,
            "epistemic_state": self.epistemic_state.value,
            "reasons": list(self.reasons),
            "path_node_ids": list(self.path_node_ids),
            "trace_event_ids": list(self.trace_event_ids),
            "limitations": list(self.limitations),
        }


def build_finding(
    store: GraphStore,
    path_result: PathFindingResult,
    *,
    actor_id: str,
    operation_id: str,
    finding_id: str,
) -> Finding:
    """Evaluates every path Level 2 found and reports the single
    strongest, justified epistemic state among them -- never the state of
    an arbitrary or first path, and never stronger than what the worst
    gap in its own evidence allows."""
    if not path_result.paths:
        return Finding(
            finding_id=finding_id,
            schema_version=SCHEMA_VERSION,
            source_id=path_result.source_id,
            target_id=path_result.target_id,
            actor_id=actor_id,
            operation_id=operation_id,
            max_hops=path_result.max_hops,
            epistemic_state=EpistemicState.INSUFFICIENT_EVIDENCE,
            reasons=(f"no path found within max_hops={path_result.max_hops}",),
            path_node_ids=(),
            trace_event_ids=(),
            limitations=(
                "a bounded search finding no path is not proof no path exists "
                "(docs/EPISTEMIC_MODEL.md): it is only evidence within max_hops",
            ),
        )

    # best is None until the first path is scored -- deliberately not
    # seeded with a POTENTIAL_PATH default: a strict "better than best"
    # comparison against a hardcoded starting state silently dropped the
    # first (and often only) path's node/trace ids whenever that path's
    # own state tied the default, confirmed via the CLI smoke test before
    # this fix (a found path reported its correct POTENTIAL_PATH state
    # with an empty path_node_ids, hiding the very path that justified it).
    best: tuple[EpistemicState, tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None = None

    for path in path_result.paths:
        assessment = assess_policy_violation(
            store, path, actor_id=actor_id, operation_id=operation_id
        )
        candidate_state = assessment.state
        # INSUFFICIENT_EVIDENCE from assess_policy_violation means "could
        # not reach D for this path", not "this path is worse than B" --
        # fall back to the observation-only check so a path that is a
        # clean OBSERVED_FLOW (just not a violation) is not under-reported
        # as INSUFFICIENT_EVIDENCE.
        if candidate_state is EpistemicState.INSUFFICIENT_EVIDENCE:
            candidate_state = classify_path_observation(store, path)
        candidate_reasons = assessment.reasons
        candidate_path_node_ids = tuple(node.node_id for node in path.nodes)
        candidate_trace_event_ids = assessment.trace_event_ids

        candidate = (candidate_state, candidate_reasons, candidate_path_node_ids, candidate_trace_event_ids)
        if best is None:
            best = candidate
        elif (-_STATE_ORDER[candidate_state], *candidate[1:]) < (-_STATE_ORDER[best[0]], *best[1:]):
            best = candidate

    assert best is not None  # path_result.paths is non-empty here
    best_state, best_reasons, best_path_node_ids, best_trace_event_ids = best

    limitations: tuple[str, ...] = (
        "graph reachability is not proof of exploitability "
        "(docs/EPISTEMIC_MODEL.md): a path existing, even an observed one, "
        "is not the same as a confirmed attack",
    )
    if best_state is EpistemicState.POTENTIAL_PATH:
        limitations = limitations + (
            "no TraceEvent evidence was found backing this path end to end",
        )

    return Finding(
        finding_id=finding_id,
        schema_version=SCHEMA_VERSION,
        source_id=path_result.source_id,
        target_id=path_result.target_id,
        actor_id=actor_id,
        operation_id=operation_id,
        max_hops=path_result.max_hops,
        epistemic_state=best_state,
        reasons=best_reasons,
        path_node_ids=best_path_node_ids,
        trace_event_ids=best_trace_event_ids,
        limitations=limitations,
    )
