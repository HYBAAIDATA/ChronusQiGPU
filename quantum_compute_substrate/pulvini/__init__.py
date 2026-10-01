"""PULVINI - Universal Golden-Exponential Scaling Operator.

In honour of a friend. Phi-recursive dimensional folding, deterministic
reversibility, spectral-gap-preserving Hamiltonian reduction, TT compression,
MPO dynamics, and the Pythagoras orchestrator.

Integrated into the ONE substrate at quantum_compute_substrate.pulvini.
"""

from .pulvini_scaling import PulviniOperator, PulviniAuditEnvelope, PHI
from .tensor_train import TensorTrain, TTPulviniHybrid, phi_guided_rank
from .matrix_product_operator import (
    MatrixProductOperator,
    IsingHamiltonianMPO,
    HeisenbergHamiltonianMPO,
    MPOPulviniTTHybrid,
)
from .orchestrator import PythagorasOrchestrator, SolverStrategy

__all__ = [
    "PHI",
    "PulviniOperator",
    "PulviniAuditEnvelope",
    "TensorTrain",
    "TTPulviniHybrid",
    "phi_guided_rank",
    "MatrixProductOperator",
    "IsingHamiltonianMPO",
    "HeisenbergHamiltonianMPO",
    "MPOPulviniTTHybrid",
    "PythagorasOrchestrator",
    "SolverStrategy",
]
