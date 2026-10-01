"""Pythagoras Master Orchestrator.

Routes computational payloads through the appropriate solver pipeline based
on dimensionality and problem type. Same substrate, one entry point.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional
from enum import Enum, auto
from .pulvini_scaling import PulviniOperator
from .tensor_train import TTPulviniHybrid
from .matrix_product_operator import MPOPulviniTTHybrid, MatrixProductOperator


class SolverStrategy(Enum):
    AUTO = auto()
    CLASSICAL = auto()
    PULVINI_TT = auto()
    MPO_PULVINI_TT = auto()
    HAMILTONIAN = auto()


QUANTUM_ROUTING_THRESHOLD = 10_000


class PythagorasOrchestrator:
    """Auto-routing master agent for the substrate."""

    def __init__(
        self,
        tolerance: float = 1e-5,
        max_tt_rank: int = 64,
        mpo_bond_dim: int = 8,
        quantum_threshold: int = QUANTUM_ROUTING_THRESHOLD,
    ) -> None:
        self.tolerance = tolerance
        self.max_tt_rank = max_tt_rank
        self.mpo_bond_dim = mpo_bond_dim
        self.quantum_threshold = quantum_threshold

    def _auto_fold_depth(self, size: int) -> int:
        if size < 1000:
            return 1
        return min(5, max(1, int(np.log10(size / 100))))

    def solve(
        self,
        tensor: np.ndarray,
        strategy: SolverStrategy = SolverStrategy.AUTO,
        mpo: Optional[MatrixProductOperator] = None,
        num_time_steps: int = 1,
    ) -> Dict[str, Any]:
        size = tensor.size

        if strategy == SolverStrategy.AUTO:
            if size > self.quantum_threshold:
                resolved = SolverStrategy.MPO_PULVINI_TT
                reason = f"size={size} > threshold={
                    self.quantum_threshold}: routed to MPO-PULVINI-TT"
            elif tensor.ndim == 2 and tensor.shape[0] == tensor.shape[1]:
                resolved = SolverStrategy.HAMILTONIAN
                reason = "square matrix detected: Hamiltonian reduction path"
            else:
                resolved = SolverStrategy.PULVINI_TT
                reason = f"size={size} <= threshold: standard PULVINI-TT"
        else:
            resolved = strategy
            reason = f"explicit strategy override: {strategy.name}"

        audit = {
            "strategy_used": resolved.name,
            "routing_reason": reason,
            "input_shape": tensor.shape,
            "input_size": size,
        }

        if resolved == SolverStrategy.CLASSICAL:
            result = self._classical_solve(tensor)
        elif resolved == SolverStrategy.HAMILTONIAN:
            result = self._hamiltonian_solve(tensor)
        elif resolved == SolverStrategy.PULVINI_TT:
            result = self._pulvini_tt_solve(tensor)
        elif resolved == SolverStrategy.MPO_PULVINI_TT:
            fold_depth = self._auto_fold_depth(size)
            result = self._mpo_pulvini_tt_solve(tensor, mpo, num_time_steps, fold_depth)
        else:
            raise ValueError(f"Unknown strategy: {resolved}")

        return {**audit, **result}

    def _classical_solve(self, tensor: np.ndarray) -> Dict[str, Any]:
        return {
            "solution": tensor.copy(),
            "reconstruction_error": 0.0,
            "compression_ratio": 1.0,
            "topology_preserved": True,
        }

    def _hamiltonian_solve(self, tensor: np.ndarray) -> Dict[str, Any]:
        pulvini = PulviniOperator(tolerance=self.tolerance)
        H_reduced, envelope = pulvini.hamiltonian_reduction(tensor)
        return {
            "solution": H_reduced,
            "audit_envelope": envelope.as_dict(),
            "reconstruction_error": envelope.reconstruction_error_bound,
            "topology_preserved": envelope.topology_preserved,
            "compression_ratio": tensor.size / max(1, H_reduced.size),
        }

    def _pulvini_tt_solve(self, tensor: np.ndarray) -> Dict[str, Any]:
        hybrid = TTPulviniHybrid(
            max_tt_rank=self.max_tt_rank, tolerance=self.tolerance, fold_depth=1
        )
        result = hybrid.process(tensor)
        return {"solution": result["reconstructed"], **result}

    def _mpo_pulvini_tt_solve(
        self,
        tensor: np.ndarray,
        mpo: Optional[MatrixProductOperator],
        num_time_steps: int,
        fold_depth: int,
    ) -> Dict[str, Any]:
        pipeline = MPOPulviniTTHybrid(
            max_tt_rank=self.max_tt_rank,
            mpo_bond_dim=self.mpo_bond_dim,
            tolerance=self.tolerance,
            fold_depth=fold_depth,
        )
        result = pipeline.process(tensor, mpo=mpo, num_time_steps=num_time_steps)
        return {"solution": result["reconstructed"], **result}
