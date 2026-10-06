"""PULVINI data orchestrator.

Quantum comes from maths. In this package quantum algebra serves data:
representation, reversible phi-folding, tensor evolution, Hamiltonian/data
operators, and measured reconstruction/topology evidence. This module is not
a mining planner and exposes no nonce, SHA-256d, Stratum, share, or pool API.

Pythagoras is historical lineage only. ``PythagorasOrchestrator`` remains as a
deprecated compatibility facade for older imports. It cannot acquire a second
authority domain and becomes read-only after construction. Canonical code must
use ``PulviniDataOrchestrator``.
"""

from __future__ import annotations

import warnings
from enum import Enum, auto
from typing import Any, Dict, Optional

import numpy as np

from .matrix_product_operator import MatrixProductOperator, MPOPulviniTTHybrid
from .pulvini_scaling import PulviniOperator
from .tensor_train import TTPulviniHybrid


class SolverStrategy(Enum):
    AUTO = auto()
    CLASSICAL = auto()
    PULVINI_TT = auto()
    MPO_PULVINI_TT = auto()
    HAMILTONIAN = auto()


PULVINI_DATA_ROUTING_THRESHOLD = 10_000
# Historical compatibility only. This constant does not define a separate
# "quantum" authority or a mining path.
QUANTUM_ROUTING_THRESHOLD = PULVINI_DATA_ROUTING_THRESHOLD


class PulviniDataOrchestrator:
    """Route data/tensor payloads through the PULVINI mathematical substrate.

    ``data_threshold`` selects when the higher-order MPO/PULVINI/TT data path
    is used. ``quantum_threshold`` is accepted only for backwards-compatible
    callers and maps to the same data-routing threshold.
    """

    AUTHORITY = "pulvini.data"
    DOMAIN = "data"

    def __init__(
        self,
        tolerance: float = 1e-5,
        max_tt_rank: int = 64,
        mpo_bond_dim: int = 8,
        data_threshold: int = PULVINI_DATA_ROUTING_THRESHOLD,
        quantum_threshold: int | None = None,
    ) -> None:
        if quantum_threshold is not None:
            data_threshold = int(quantum_threshold)
        self.tolerance = tolerance
        self.max_tt_rank = max_tt_rank
        self.mpo_bond_dim = mpo_bond_dim
        self.data_threshold = int(data_threshold)
        # Compatibility attribute for older consumers. It is intentionally an
        # alias of the data threshold, not a distinct quantum/mining control.
        self.quantum_threshold = self.data_threshold

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
        """Execute a data-domain solve and return measured routing evidence."""
        size = tensor.size

        if strategy == SolverStrategy.AUTO:
            if size > self.data_threshold:
                resolved = SolverStrategy.MPO_PULVINI_TT
                reason = (
                    f"size={size} > data_threshold={self.data_threshold}: "
                    "routed to MPO-PULVINI-TT"
                )
            elif tensor.ndim == 2 and tensor.shape[0] == tensor.shape[1]:
                resolved = SolverStrategy.HAMILTONIAN
                reason = "square data operator detected: Hamiltonian reduction path"
            else:
                resolved = SolverStrategy.PULVINI_TT
                reason = f"size={size} <= data_threshold: standard PULVINI-TT"
        else:
            resolved = strategy
            reason = f"explicit strategy override: {strategy.name}"

        audit = {
            "authority": self.AUTHORITY,
            "domain": self.DOMAIN,
            "mining_path": False,
            "strategy_used": resolved.name,
            "routing_reason": reason,
            "input_shape": tensor.shape,
            "input_size": size,
            "data_threshold": self.data_threshold,
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
        else:  # pragma: no cover - Enum closes this branch
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
        reduced, envelope = pulvini.hamiltonian_reduction(tensor)
        return {
            "solution": reduced,
            "audit_envelope": envelope.as_dict(),
            "reconstruction_error": envelope.reconstruction_error_bound,
            "topology_preserved": envelope.topology_preserved,
            # Mathematical dimensional ratio for this result only. It is not
            # a fleet/storage compression claim.
            "compression_ratio": tensor.size / max(1, reduced.size),
        }

    def _pulvini_tt_solve(self, tensor: np.ndarray) -> Dict[str, Any]:
        hybrid = TTPulviniHybrid(
            max_tt_rank=self.max_tt_rank,
            tolerance=self.tolerance,
            fold_depth=1,
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


class PythagorasOrchestrator(PulviniDataOrchestrator):
    """Deprecated read-only compatibility facade.

    The historical name can still execute the same data-domain computation so
    old callers do not break, but it cannot mutate its routing configuration
    after construction and it never emits a Pythagoras authority identity.
    Repository production code is separately forbidden by the architecture
    gate from importing this facade.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        object.__setattr__(self, "_compat_initialising", True)
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_compat_initialising", False)
        warnings.warn(
            "PythagorasOrchestrator is historical compatibility only; use "
            "PulviniDataOrchestrator",
            DeprecationWarning,
            stacklevel=2,
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_compat_initialising" or getattr(
            self, "_compat_initialising", True
        ):
            object.__setattr__(self, name, value)
            return
        raise AttributeError(
            "PythagorasOrchestrator is a read-only compatibility facade"
        )

    def solve(
        self,
        tensor: np.ndarray,
        strategy: SolverStrategy = SolverStrategy.AUTO,
        mpo: Optional[MatrixProductOperator] = None,
        num_time_steps: int = 1,
    ) -> Dict[str, Any]:
        result = super().solve(
            tensor,
            strategy=strategy,
            mpo=mpo,
            num_time_steps=num_time_steps,
        )
        result["compatibility_alias"] = "PythagorasOrchestrator"
        result["authority"] = self.AUTHORITY
        result["domain"] = self.DOMAIN
        result["mining_path"] = False
        return result


__all__ = [
    "PULVINI_DATA_ROUTING_THRESHOLD",
    "QUANTUM_ROUTING_THRESHOLD",
    "SolverStrategy",
    "PulviniDataOrchestrator",
    "PythagorasOrchestrator",
]
