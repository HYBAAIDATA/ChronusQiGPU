"""The legacy HR adapter — the surface TOE was discovered through.

TOE first appeared as an employee-churn engine (``toe.engine.PredictiveEngine``,
HR-shaped columns over the quantum-tensor substrate). That lineage is kept
here, as an adapter: HR words map onto the domain-neutral problem, and the
original engine remains callable through :meth:`legacy_engine_predict`
(it needs pandas — the ``legacy-hr`` extra).

Declared semantic model (an assumption of this adapter, not a finding)::

    compensation_ratio → engagement → churn_risk
    promotion          → engagement
    performance_score  → churn_risk

The strengths are estimated by the backend from the supplied records.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..planning import OperatorSpec
from ..policy import Objective
from ..problem import Problem, Structure
from .base import OptionalDependencyUnavailable, ProblemAdapter

_RELATIONS = (
    ("compensation_ratio", "engagement"),
    ("promotion", "engagement"),
    ("engagement", "churn_risk"),
    ("performance_score", "churn_risk"),
)


class LegacyHRAdapter(ProblemAdapter):
    """``employees``: records with the columns above; ``current``: the
    employee/state to act on; ``levers``: {"compensation_ratio": [...],
    "promotion": [...]}."""

    name = "legacy_hr"
    vocabulary = {
        "compensation_ratio": "compensation ratio",
        "promotion": "promotion",
        "engagement": "engagement",
        "churn_risk": "churn risk",
        "performance_score": "performance score",
    }

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        rows: List[Mapping[str, float]] = list(raw["employees"])
        cols = sorted({c for e in _RELATIONS for c in e})
        samples = {c: [float(r[c]) for r in rows] for c in cols}
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation={c: v[:64] for c, v in samples.items()},
            state={c: float(raw["current"][c]) for c in cols},
            structure=Structure.of(_RELATIONS),
            samples=samples,
            operators=tuple(
                OperatorSpec(f"set_{k}", k, tuple(float(x) for x in v))
                for k, v in sorted((raw.get("levers") or {}).items())
            ),
            objective=Objective("churn_risk", "minimize"),
            query=("compensation_ratio", "churn_risk"),
            metadata={"adapter": self.name},
        )

    def legacy_engine_predict(self, records: List[Mapping[str, Any]]) -> Dict[str, Any]:
        """The original discovery surface: ``PredictiveEngine.predict_churn_risk``."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise OptionalDependencyUnavailable(
                "the legacy HR engine needs pandas: install the 'legacy-hr' extra"
            ) from exc
        from ..engine import PredictiveEngine

        return PredictiveEngine().predict_churn_risk(pd.DataFrame(list(records)))


__all__ = ["LegacyHRAdapter"]
