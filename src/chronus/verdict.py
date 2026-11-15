"""Gate verdicts do not imply production qualification without attested CI evidence."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class Status(str,Enum):
    PASS="PASS"
    FAIL="FAIL"
    UNQUALIFIED="UNQUALIFIED"

@dataclass(frozen=True)
class GateResult:
    gate: str
    status: Status
    detail: str=""

@dataclass(frozen=True)
class Verdict:
    gates: tuple[GateResult,...]
    @property
    def status(self)->Status:
        if not self.gates:
            return Status.UNQUALIFIED
        if any(x.status is Status.FAIL for x in self.gates):
            return Status.FAIL
        if any(x.status is not Status.PASS for x in self.gates):
            return Status.UNQUALIFIED
        return Status.PASS
    def by_gate(self)->dict[str,Status]:
        return {g.gate:g.status for g in self.gates}
