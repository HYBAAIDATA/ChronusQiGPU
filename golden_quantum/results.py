"""
Result types for the Golden Quantum Framework.

Each check is classified as:
    - theorem:      a proven mathematical identity verified computationally
    - invariant:    a structural property that must always hold
    - demonstration: an empirical demonstration (not a proof)
"""

from dataclasses import dataclass, field
from typing import Literal
from collections import defaultdict


CheckKind = Literal["theorem", "invariant", "demonstration"]


@dataclass(frozen=True)
class CheckResult:
    """Result of a single check within a family."""
    family: str
    purpose: str
    name: str
    passed: bool
    kind: CheckKind
    detail: str = ""


@dataclass
class CheckRegistry:
    """Collects all check results across families."""
    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def add_check(
        self,
        family: str,
        purpose: str,
        name: str,
        passed: bool,
        kind: CheckKind = "theorem",
        detail: str = "",
    ) -> None:
        self.results.append(CheckResult(
            family=family, purpose=purpose, name=name,
            passed=passed, kind=kind, detail=detail,
        ))

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def theorem_count(self) -> int:
        return sum(1 for r in self.results if r.kind == "theorem")

    @property
    def invariant_count(self) -> int:
        return sum(1 for r in self.results if r.kind == "invariant")

    @property
    def demonstration_count(self) -> int:
        return sum(1 for r in self.results if r.kind == "demonstration")

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results if r.kind in ("theorem", "invariant"))

    def by_family(self) -> dict[str, list[CheckResult]]:
        groups: dict[str, list[CheckResult]] = defaultdict(list)
        for r in self.results:
            groups[r.family].append(r)
        return dict(groups)

    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]
