"""Level 2, part 3: authority analysis.

Per docs/LEVELS.md Level 2 and docs/EPISTEMIC_MODEL.md: this module
answers two separate structural-fact questions and refuses to collapse
them into one judgment --

  1. Does an actor possess the permissions an operation requires?
  2. Is there a policy governing that operation at all?

Neither question, nor their combination, answers "is this actor
authorized to perform this operation in this context": that requires
evaluating whatever conditions a governing policy actually states, which
is Level 3's rule-evaluation scope, not implemented here. The distinction
this module exists to enforce -- possession is not context-authorization
-- is stated explicitly in AuthorityAssessment.note so a caller cannot
read only the booleans and miss it.
"""

from __future__ import annotations

from dataclasses import dataclass

from trust_fracture.graph_store import GraphStore
from trust_fracture.schema import RelationshipType


@dataclass(frozen=True)
class AuthorityAssessment:
    actor_id: str
    operation_id: str
    required_permission_ids: tuple[str, ...]
    held_permission_ids: tuple[str, ...]
    missing_permission_ids: tuple[str, ...]
    governing_policy_ids: tuple[str, ...]

    @property
    def possesses_all_required_permissions(self) -> bool:
        return len(self.missing_permission_ids) == 0

    @property
    def is_governed(self) -> bool:
        return len(self.governing_policy_ids) > 0

    @property
    def note(self) -> str:
        if not self.possesses_all_required_permissions:
            return (
                f"{self.actor_id} is missing {len(self.missing_permission_ids)} "
                f"permission(s) that {self.operation_id} requires: "
                f"{', '.join(self.missing_permission_ids)}."
            )
        if self.is_governed:
            plural = "y" if len(self.governing_policy_ids) == 1 else "ies"
            return (
                f"{self.actor_id} holds every permission {self.operation_id} "
                f"requires, and {len(self.governing_policy_ids)} polic{plural} "
                "govern this operation. Whether that policy's conditions are "
                "actually satisfied in this context is not evaluated here "
                "(docs/EPISTEMIC_MODEL.md, Level 3 scope)."
            )
        return (
            f"{self.actor_id} holds every permission {self.operation_id} "
            "requires, and no policy governs this operation. Holding a "
            "permission is a structural fact; it is not, by itself, "
            "evidence that using it here is authorized (docs/EPISTEMIC_MODEL.md)."
        )


def analyze_authority(
    store: GraphStore, actor_id: str, operation_id: str
) -> AuthorityAssessment:
    required = store.outgoing_related_ids(operation_id, RelationshipType.REQUIRES_PERMISSION)
    held = store.outgoing_related_ids(actor_id, RelationshipType.HAS_PERMISSION)
    held_set = set(held)
    missing = tuple(permission_id for permission_id in required if permission_id not in held_set)
    governing = store.outgoing_related_ids(operation_id, RelationshipType.GOVERNED_BY)
    return AuthorityAssessment(
        actor_id=actor_id,
        operation_id=operation_id,
        required_permission_ids=required,
        held_permission_ids=held,
        missing_permission_ids=missing,
        governing_policy_ids=governing,
    )
