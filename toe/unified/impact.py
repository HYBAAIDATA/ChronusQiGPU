"""Scholarship ledger.

Recognized value is allocated at the configured rate to the institutions
named in the program: Oxford, Imperial College London, and Cambridge.
The ledger records entries. It does not invent them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


INSTITUTIONS = (
    "University of Oxford",
    "Imperial College London",
    "University of Cambridge",
)

PURPOSE = "STEM scholarships for women from Caribbean and African countries"
REGIONS = ("Caribbean", "Africa")
UNIT_COST = 50_000.0


@dataclass(frozen=True)
class Recognition:
    source: str
    amount: float
    allocated: float
    retained: float


@dataclass
class ScholarshipLedger:
    allocation_rate: float = 0.0
    institutions: tuple[str, ...] = INSTITUTIONS
    purpose: str = PURPOSE
    unit_cost: float = UNIT_COST
    regions: tuple[str, ...] = REGIONS
    _entries: list[Recognition] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.allocation_rate <= 1.0:
            raise ValueError("allocation_rate must be between 0 and 1")

    def configure(self, allocation_rate: float, institutions: tuple[str, ...] | None = None) -> None:
        if not 0.0 <= allocation_rate <= 1.0:
            raise ValueError("allocation_rate must be between 0 and 1")
        self.allocation_rate = allocation_rate
        if institutions is not None:
            if not institutions:
                raise ValueError("institutions cannot be empty")
            self.institutions = tuple(institutions)

    def recognize(self, amount: float, source: str) -> Recognition:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        if not source:
            raise ValueError("source is required")
        allocated = amount * self.allocation_rate
        entry = Recognition(source, amount, allocated, amount - allocated)
        self._entries.append(entry)
        return entry

    def committed(self) -> float:
        return sum(entry.allocated for entry in self._entries)

    def by_institution(self) -> dict[str, float]:
        if not self.institutions:
            return {}
        share = self.committed() / len(self.institutions)
        return {name: share for name in self.institutions}

    def entries(self) -> tuple[Recognition, ...]:
        return tuple(self._entries)

    def outcomes(self) -> dict:
        allocated = self.committed()
        scholarships = int(allocated // self.unit_cost) if self.unit_cost else 0
        return {
            "scholarships": scholarships,
            "partnerships": len(self.institutions) if allocated else 0,
            "regions": self.regions,
            "allocated": allocated,
        }
