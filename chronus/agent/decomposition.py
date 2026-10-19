"""Executable DAG/interface/coverage checks, not automatic semantic decomposition."""

from dataclasses import dataclass
from ._contracts import ContractError


@dataclass(frozen=True)
class Subgoal:
    id: str
    covers: tuple[str, ...]
    dependencies: tuple[str, ...]
    interface: str
    acceptance_test: str


@dataclass(frozen=True)
class Decomposition:
    parent_id: str
    subgoals: tuple[Subgoal, ...]
    verification_plan: str
    rollback_plan: str


def decompose(objective, candidates):
    if type(candidates) is not tuple or not 1 <= len(candidates) <= 64:
        raise ContractError("bounded decomposition candidates required")
    valid = []
    for d in candidates:
        if d.parent_id != objective.id or not d.verification_plan or not d.rollback_plan:
            continue
        if type(d.subgoals) is not tuple or not 1 <= len(d.subgoals) <= 256:
            continue
        ids = {g.id for g in d.subgoals}
        if len(ids) != len(d.subgoals) or any(
            not g.interface or not g.acceptance_test or not set(g.dependencies) <= ids
            for g in d.subgoals
        ):
            continue
        if set(c for g in d.subgoals for c in g.covers) != set(objective.success_criteria):
            continue
        done = set()
        for _ in d.subgoals:
            done.update(g.id for g in d.subgoals if set(g.dependencies) <= done)
        if done == ids:
            valid.append(d)
    if not valid:
        raise ContractError("no acyclic, covered, verifiable, reversible decomposition")
    return min(valid, key=lambda d: len(d.subgoals))
