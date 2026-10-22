"""Millennium Mathematics Laboratory World — bounded hypothesis and invariant experiments.

This is a governed mathematical-reasoning environment. It does not claim to solve,
prove, disprove, or independently validate any Millennium Prize Problem.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from .kairos_execution import KairosExecutionLayer, OperatorAction

class MillenniumProblem(str, Enum):
    BIRCH_SWYNNERTON_DYER = "birch_swinnerton_dyer"
    HODGE = "hodge"
    NAVIER_STOKES = "navier_stokes"
    P_NP = "p_vs_np"
    POINCARE = "poincare"
    RIEMANN = "riemann"
    YANG_MILLS = "yang_mills_mass_gap"

@dataclass(frozen=True)
class MathematicalExperiment:
    experiment_id: str
    problem: MillenniumProblem
    hypothesis: str
    invariants: tuple[str, ...]
    constraints: Mapping[str, object]

class MillenniumMathematicsWorld:
    """Single-operator Kairos world for reproducible constraint experiments."""
    def __init__(self, layer: KairosExecutionLayer | None = None) -> None:
        self.layer = layer or KairosExecutionLayer()
        self.world_id: str | None = None
        self.session_id: str | None = None
        self.experiments: list[MathematicalExperiment] = []

    def create(self, operator_id: str = "andre") -> Mapping[str, str]:
        if self.world_id is not None: raise RuntimeError("Millennium world already created")
        world = self.layer.runtime.create_world("millennium-mathematics-laboratory", "sha256:" + "m" * 64)
        self.layer.runtime.bootstrap_world(world.world_id)
        session = self.layer.runtime.activate_session(self.layer.runtime.open_session(operator_id).session_id)
        self.world_id, self.session_id = world.world_id, session.session_id
        return {"world_id": world.world_id, "session_id": session.session_id, "claim_boundary": "Hypothesis, invariant, and counterexample research only; no Millennium-problem solution claim."}

    def run(self, experiment: MathematicalExperiment) -> Mapping[str, object]:
        if self.world_id is None or self.session_id is None: raise RuntimeError("Millennium world not created")
        if not experiment.hypothesis.strip() or not experiment.invariants: raise ValueError("hypothesis and invariants required")
        action = OperatorAction("symbolic_orchard", "geometric_plane", "cultivate", {"experiment_id": experiment.experiment_id, "problem": experiment.problem.value, "hypothesis": experiment.hypothesis, "invariants": experiment.invariants}, {"invariant_violations": tuple(experiment.constraints.get("invariant_violations", ()))}, {"research_mode": "laboratory", "solution_claim": False})
        outcome = self.layer.execute(self.world_id, self.session_id, action)
        self.experiments.append(experiment)
        state = self.layer.world_state(self.world_id)
        return {"outcome": outcome.outcome.value, "world_hash": state["world_hash"], "chronicle_head": state["chronicle_head"], "problem": experiment.problem.value, "claim_boundary": "No proof, disproof, solution, peer review, or external validation is asserted."}

__all__ = ["MillenniumProblem", "MathematicalExperiment", "MillenniumMathematicsWorld"]
