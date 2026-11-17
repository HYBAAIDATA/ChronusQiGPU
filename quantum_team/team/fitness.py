"""Scoring with a mechanical conformance gate. Contract drift is a hard
zero, not a penalty — a patch that passes its own tests but drifts from
the frozen contracts is worth nothing. Emits a wire-ready, audit-bearing
FitnessReportMessage instead of a bare float, so a 0.0 always explains
itself (missing/extra digests are in the report)."""

from __future__ import annotations

import math

from .contracts import ContractRegistry
from .wire import FitnessReportMessage, PatchMessage


class FitnessEvaluator:
    def __init__(self, registry: ContractRegistry) -> None:
        self.registry = registry

    def evaluate(self, patch: PatchMessage) -> FitnessReportMessage:
        conforms = self.registry.conforms(patch.declares)
        missing, extra = self.registry.diff_digests(patch.declares)

        pass_ratio = (patch.tests_passed / patch.tests_total
                      if patch.tests_total > 0 else 0.0)
        penalty = 0.1 * len(patch.files_changed_conflicts)

        if not conforms or patch.tests_total == 0:
            raw = 0.0
        else:
            raw = max(0.0, min(1.0, pass_ratio - penalty))

        return FitnessReportMessage(
            patch_id=patch.patch_id, task_id=patch.task_id,
            conforms=conforms, missing_digests=missing, extra_digests=extra,
            pass_ratio=pass_ratio, conflict_penalty=penalty,
            raw_score=raw, normalized_phase_angle=math.pi * raw)

    def score(self, patch: PatchMessage) -> float:
        return self.evaluate(patch).raw_score
