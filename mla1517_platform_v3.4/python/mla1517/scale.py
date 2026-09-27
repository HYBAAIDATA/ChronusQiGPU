"""Evidence-gated scale control for mathematical and physical execution.

The controller separates three quantities that must not be conflated:

* mathematical scale: an exact recurrence index or explicit power descriptor;
* logical state size: the bits required by the selected exact representation;
* physical commitment: logical state plus proof/metadata overhead and policy.

It never claims infinite physical memory or throughput. It authorizes a request
only when the declared resource budgets can accommodate the representation.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
import importlib.util
import math
from pathlib import Path
from typing import Any, Iterable
from .core import fib, lucas

PHI = (1.0 + math.sqrt(5.0)) / 2.0
SUPPORTED_FAMILIES = (
    "fibonacci_lucas",
    "golden",
    "silver",
    "plastic",
    "supergolden",
    "tribonacci",
)


def _algebraic_turing_core():
    """Select the algebraic substrate, not the mining schedule helper."""
    try:
        import turing_core

        if hasattr(turing_core, "FAMILY_COORDINATE_LIMBS"):
            return turing_core
    except ImportError:
        pass
    root_file = Path(__file__).parents[3] / "turing_core.py"
    if root_file.exists():
        spec = importlib.util.spec_from_file_location(
            "_pythia_algebraic_turing_core", root_file
        )
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "FAMILY_COORDINATE_LIMBS"):
                return module
    raise ImportError("algebraic turing_core substrate is unavailable")


@dataclass(frozen=True)
class ScaleBudget:
    """Hard limits applied before exact execution is admitted."""

    max_index: int = 10000
    max_bit_length: int = 1_000_000
    max_physical_bytes: int = 128 * 1024 * 1024
    max_work_units: int = 100_000_000
    max_steps: int = 1024
    metadata_bytes: int = 256
    proof_bytes: int = 32
    replication_factor: int = 1


@dataclass(frozen=True)
class ScalePoint:
    """One recurrence scale or explicit base/exponent workload descriptor."""

    index: int
    family: str = "fibonacci_lucas"
    label: str = ""
    base: int | None = None
    exponent: int | None = None


@dataclass(frozen=True)
class ScaleEstimate:
    """Conservative preflight estimate for one scale request."""

    math_scale_index: int
    math_magnitude_log10: float
    logical_state_bits: int
    physical_bytes: int
    proof_bytes: int
    work_units: int


@dataclass(frozen=True)
class ScaleDecision:
    """Authorization result; rejected decisions never enter execution."""

    accepted: bool
    point: ScalePoint
    estimate: ScaleEstimate
    reason: str


class ScaleController:
    """Authorize extensible scale programs under explicit physical budgets."""

    def __init__(
        self,
        budget: ScaleBudget | None = None,
        allow_families: Iterable[str] = SUPPORTED_FAMILIES,
    ):
        self.budget = budget or ScaleBudget()
        self.allow_families = frozenset(allow_families)
        if self.budget.replication_factor < 1:
            raise ValueError("replication_factor must be >= 1")

    @staticmethod
    def estimate_bits(index: int) -> int:
        """Return a conservative bit bound for one exact Fibonacci pair."""
        if index < 1:
            raise ValueError("index must be >= 1")
        # F_n and F_{n+1} are both bounded by phi^(n+1); add one safety bit.
        return max(1, math.ceil((index + 1) * math.log2(PHI)) + 1)

    def estimate(self, point: ScalePoint) -> ScaleEstimate:
        """Estimate math magnitude, exact-state bits, physical bytes, and work."""
        if point.index < 1:
            raise ValueError("index must be >= 1")
        bits = self.estimate_bits(point.index)
        state_bytes = (2 * bits + 7) // 8  # exact (F_n, F_{n+1}) pair bound
        physical = (
            state_bytes + self.budget.metadata_bytes + self.budget.proof_bytes
        ) * self.budget.replication_factor
        # Fast doubling has logarithmic recursion depth; integer arithmetic scales with bit length.
        work = max(1, math.ceil(math.log2(point.index + 1)) * bits)
        if point.base is not None:
            magnitude = (
                point.exponent * math.log10(point.base)
                if point.exponent is not None
                else point.index * math.log10(point.base)
            )
        else:
            magnitude = point.index * math.log10(PHI)
        return ScaleEstimate(
            point.index, magnitude, 2 * bits, physical, self.budget.proof_bytes, work
        )

    def authorize(self, point: ScalePoint) -> ScaleDecision:
        """Reject a scale before execution if family or resource policy fails."""
        if point.family not in self.allow_families:
            return ScaleDecision(False, point, self.estimate(point), "family_not_allowed")
        estimate = self.estimate(point)
        b = self.budget
        if point.index > b.max_index:
            return ScaleDecision(False, point, estimate, "index_out_of_bounds")
        if estimate.logical_state_bits > b.max_bit_length:
            return ScaleDecision(False, point, estimate, "bit_budget_exceeded")
        if estimate.physical_bytes > b.max_physical_bytes:
            return ScaleDecision(False, point, estimate, "physical_budget_exceeded")
        if estimate.work_units > b.max_work_units:
            return ScaleDecision(False, point, estimate, "work_budget_exceeded")
        return ScaleDecision(True, point, estimate, "accepted")

    def plan(self, points: Iterable[ScalePoint]) -> list[ScaleDecision]:
        """Authorize a finite ordered scale program without executing it."""
        points = list(points)
        if len(points) > self.budget.max_steps:
            raise ValueError("scale program exceeds max_steps")
        return [self.authorize(point) for point in points]

    def execute_exact(self, point: ScalePoint) -> dict[str, Any]:
        """Execute one authorized family point with exact integer limbs."""
        decision = self.authorize(point)
        if not decision.accepted:
            raise RuntimeError(decision.reason)
        family = "golden" if point.family == "fibonacci_lucas" else point.family
        if family == "golden":
            coordinate, trace = fib(point.index), lucas(point.index)
        else:
            try:
                core = _algebraic_turing_core()
                coordinate = core.FAMILY_COORDINATE_LIMBS[family](point.index)
                trace = core.family_trace(family, point.index)
            except (ImportError, AttributeError, KeyError) as exc:
                raise RuntimeError("exact family substrate unavailable") from exc
        return {
            "scale": asdict(point),
            "decision": asdict(decision),
            "family": family,
            "coordinate": coordinate,
            "trace": trace,
            # Backward-compatible golden names.
            "fibonacci": coordinate if family == "golden" else None,
            "lucas": trace if family == "golden" else None,
            "exact": True,
            "capacity_mode": "bounded_by_scale_budget",
            "performance_claim": "measured_only",
        }


def parse_scale_token(token: str) -> ScalePoint:
    """Parse an index or one explicit ``base^exponent`` token.

    Chained notation such as ``10^12^15`` is rejected because exponentiation is
    ambiguous without parentheses and a recurrence index must be explicit.
    """
    token = token.strip()
    if "^" in token:
        if token.count("^") != 1:
            raise ValueError("ambiguous nested power; use explicit base/exponent fields")
        base, exponent = token.split("^")
        if not base.isdigit() or not exponent.isdigit() or int(base) < 1 or int(exponent) < 1:
            raise ValueError("power token must be positive base^exponent")
        return ScalePoint(
            index=int(exponent),
            family="fibonacci_lucas",
            label=token,
            base=int(base),
            exponent=int(exponent),
        )
    if not token.isdigit() or int(token) < 1:
        raise ValueError("scale token must be a positive integer")
    return ScalePoint(index=int(token))
