"""Golden Unified Theory provider for TOE.

The provider unifies existing TOE lenses under one evidence-bearing contract.
It does not claim to solve Yang-Mills, Poincare, Ricci, Hodge, or any other
open mathematical problem. "Collapse" means compiling observations and
claims into a shared representation, then resolving only where declared
authority and evidence permit it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .arbitration import arbitrate
from .foundation import UNIFIED_THEORY
from .operator_compilers import OperatorSpec, compile_operator
from .representation import choose

GOLDEN_UNIFIED_VERSION = "toe.golden_unified/v1"

THEORY_LENSES = {
    "yang_mills": {
        "operators": ("finite_gauge_gap", "spectral_gap"),
        "claim_boundary": "finite gauge-group computation; no continuum mass-gap proof",
    },
    "poincare": {
        "operators": ("poincare_fold", "geodesic_distance", "manifold_projection"),
        "claim_boundary": "computational geometry; no Poincare-conjecture proof claim",
    },
    "ricci": {
        "operators": ("ricci_curvature", "curvature_flow"),
        "claim_boundary": "computed curvature on declared structures",
    },
    "hodge": {
        "operators": ("harmonic_projection", "cohomology_signature"),
        "claim_boundary": "finite/discrete operators; no Hodge-conjecture proof claim",
    },
    "golden_quantum": {
        "operators": ("golden_schedule", "t_phi_fold", "prime_gap_address"),
        "claim_boundary": "exact transforms plus experimental ordering; no advantage assumed",
    },
    "causal": {
        "operators": ("do_operator", "counterfactual", "identifiability"),
        "claim_boundary": "answers remain bound to the declared causal graph",
    },
    "data_ml_bi": {
        "operators": ("compile_operator", "select_views", "plan", "measure"),
        "claim_boundary": "shared data representation, not universal semantic truth",
    },
}


@dataclass(frozen=True)
class UnifiedObservation:
    operator: Mapping[str, Any]
    representation: Mapping[str, Any]
    admitted_theories: tuple[str, ...]
    rejected_theories: Mapping[str, str]
    foundation_digest: str
    theory_digest: str
    truth_class: str = "compiled_cross_theory_observation"


@dataclass(frozen=True)
class CollapseResult:
    status: str
    answer: Any
    arbitration: Mapping[str, Any]
    foundation_digest: str
    theory_digest: str
    collapsed: bool
    reason: str


class GoldenUnifiedTheory:
    """Compile and arbitrate cross-domain TOE observations."""

    version = GOLDEN_UNIFIED_VERSION

    def __init__(self) -> None:
        self.foundation = UNIFIED_THEORY
        if not self.foundation.verify():
            raise RuntimeError("unified theory foundation failed self-verification")
        self.theory_digest = self._digest(
            {
                "version": self.version,
                "foundation_digest": self.foundation.digest,
                "lenses": THEORY_LENSES,
            }
        )

    @staticmethod
    def _digest(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()

    @staticmethod
    def _admit_theories(operator: OperatorSpec, selection: Mapping[str, Any]):
        selected = {name for name, _reason in selection.get("selected", [])}
        admitted = {"golden_quantum", "data_ml_bi"}
        rejected: dict[str, str] = {}
        if "geometric" in selected:
            admitted.update(("poincare", "ricci"))
        else:
            rejected["poincare"] = rejected["ricci"] = "geometric lens not admitted"
        if "topological" in selected:
            admitted.add("hodge")
        else:
            rejected["hodge"] = "topological lens not admitted"
        if "causal_graph" in selected:
            admitted.add("causal")
        else:
            rejected["causal"] = "no declared causal graph"
        if operator.kind in {"graph", "time_series"} and operator.dimensions >= 4:
            admitted.add("yang_mills")
        else:
            rejected["yang_mills"] = "finite spectral structure not established"
        return tuple(sorted(admitted)), rejected

    def compile(
        self, data: Any, *, graph: Any = None, goal: str | None = None
    ) -> UnifiedObservation:
        operator = compile_operator(data)
        representation = choose(data, graph=graph, goal=goal)
        admitted, rejected = self._admit_theories(operator, representation["selection"])
        return UnifiedObservation(
            operator=operator.as_dict(),
            representation=representation,
            admitted_theories=admitted,
            rejected_theories=rejected,
            foundation_digest=self.foundation.digest,
            theory_digest=self.theory_digest,
        )

    def collapse(
        self,
        claims: Sequence[Mapping[str, Any]],
        *,
        problem_type: str = "interventional",
    ) -> CollapseResult:
        result = arbitrate(claims, problem_type=problem_type)
        status = str(result.get("status", "UNAVAILABLE"))
        resolution = result.get("resolution")
        if status == "AGREEMENT":
            answer = claims[0]["answer"] if claims else None
            return CollapseResult(
                status=status,
                answer=answer,
                arbitration=result,
                foundation_digest=self.foundation.digest,
                theory_digest=self.theory_digest,
                collapsed=True,
                reason="independent surfaces agree",
            )
        if resolution is not None:
            return CollapseResult(
                status=status,
                answer=resolution["answer"],
                arbitration=result,
                foundation_digest=self.foundation.digest,
                theory_digest=self.theory_digest,
                collapsed=True,
                reason=f"resolved by {resolution['rule']}",
            )
        return CollapseResult(
            status=status,
            answer=None,
            arbitration=result,
            foundation_digest=self.foundation.digest,
            theory_digest=self.theory_digest,
            collapsed=False,
            reason=result.get("reason", "no justified cross-theory collapse"),
        )

    def report(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "foundation": self.foundation.report(),
            "theory_digest": self.theory_digest,
            "lenses": THEORY_LENSES,
            "collapse_semantics": "shared representation plus evidence-governed arbitration",
            "open_problem_solution_claimed": False,
            "physical_theory_of_everything_claimed": False,
            "verified": bool(self.foundation.verify() and len(THEORY_LENSES) == 7),
        }


GOLDEN_UNIFIED_THEORY = GoldenUnifiedTheory()

__all__ = [
    "CollapseResult",
    "GOLDEN_UNIFIED_THEORY",
    "GOLDEN_UNIFIED_VERSION",
    "GoldenUnifiedTheory",
    "THEORY_LENSES",
    "UnifiedObservation",
]
