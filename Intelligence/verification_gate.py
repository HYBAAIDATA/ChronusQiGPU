"""Hard verification gate.

No claim without verification. No completion without tests.
Unknown equals unavailable. Owner decision overrides interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str


def check_completion(
    *,
    context_loaded: bool,
    evidence_retrieved: bool,
    verification_executed: bool,
    tests_passed: Optional[bool],
    owner_approval_recorded: bool = False,
    touches_canonical: bool = False,
) -> GateResult:
    if not context_loaded:
        return GateResult(False, "context not loaded")
    if not evidence_retrieved:
        return GateResult(False, "evidence not retrieved")
    if not verification_executed:
        return GateResult(False, "verification not executed")
    if tests_passed is not True:
        return GateResult(False, "tests did not pass")
    if touches_canonical and not owner_approval_recorded:
        return GateResult(False, "owner approval required for canonical change")
    return GateResult(True, "complete")
