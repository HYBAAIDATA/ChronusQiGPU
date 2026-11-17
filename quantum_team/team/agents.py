"""Specialists consume TaskMessage frames and emit PatchMessage frames.
The toy body is deterministic; swap for an LLM call — the wire layer,
fitness gate, and quantum tool cannot tell the difference and do not care.
This method is the ONLY plug point in the system."""

from __future__ import annotations

from .contracts import ContractRegistry
from .wire import PatchMessage, TaskMessage


class Specialist:
    def __init__(self, name: str, specialty: str, skill: float):
        self.name = name
        self.specialty = specialty
        self.skill = skill                  # 0..1, quality of output

    def execute(self, task: TaskMessage, registry: ContractRegistry,
                rng) -> PatchMessage:
        content = f"# {task.module} by {self.name} v{rng.random():.4f}"
        total = 10
        passed = max(0, min(total, round(total * self.skill + rng.normal(0, 1))))
        return PatchMessage(
            task_id=task.task_id, agent_id=self.name, parent_ids=(),
            files={f"{task.module}.py": content},
            declares=registry.live_digests(),
            tests_passed=passed, tests_total=total)


def breed(a: PatchMessage, b: PatchMessage) -> PatchMessage:
    """Crossover: union of files (a wins collisions), intersection of
    declarations. patch_id recomputes content-addressed automatically."""
    return PatchMessage(
        task_id=a.task_id, agent_id="breeder",
        parent_ids=(a.patch_id, b.patch_id),
        files={**b.files, **a.files},
        declares=a.declares & b.declares,   # both conform -> full set
        tests_passed=max(a.tests_passed, b.tests_passed),
        tests_total=max(a.tests_total, b.tests_total),
        files_changed_conflicts=a.files_changed_conflicts
        + b.files_changed_conflicts)
