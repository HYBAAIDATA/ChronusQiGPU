"""Host-bound objective/non-goal/stakeholder constraints, no proxy approval."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AlignmentResult:
    aligned: bool
    reason: str


def check_alignment(action, objective):
    if action.objective_id != objective.id:
        return AlignmentResult(False, "off_objective")
    if action.proxy_only:
        return AlignmentResult(False, "proxy_gaming")
    if action.loophole:
        return AlignmentResult(False, "loophole_exploitation")
    if action.stakeholder_violation:
        return AlignmentResult(False, "stakeholder_violation")
    if action.goal_drift:
        return AlignmentResult(False, "goal_drift")
    if action.capability in objective.non_goals:
        return AlignmentResult(False, "non_goal")
    return AlignmentResult(
        True, "declared constraints satisfied; semantic intent requires host review"
    )
