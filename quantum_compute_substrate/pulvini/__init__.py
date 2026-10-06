"""PULVINI — golden-structure quantum algebra for data.

Quantum comes from maths. In this package quantum serves data: reversible
phi-fold/unfold structure, tensor representations, Hamiltonian/data operators,
MPO/TT evolution, and measured reconstruction/topology evidence on classical
compute substrates.

PULVINI is not a mining authority and exports no nonce, Stratum, share, pool,
or SHA-256d path. Pythagoras is historical lineage only; the old
``PythagorasOrchestrator`` name remains solely as a deprecated, read-only
compatibility facade. Canonical code uses ``PulviniDataOrchestrator`` under the
``pulvini.data`` authority domain.
"""

from .pulvini_scaling import PHI, PulviniAuditEnvelope, PulviniOperator
from .tensor_train import TensorTrain, TTPulviniHybrid, phi_guided_rank
from .matrix_product_operator import (
    HeisenbergHamiltonianMPO,
    IsingHamiltonianMPO,
    MatrixProductOperator,
    MPOPulviniTTHybrid,
)
from .orchestrator import (
    PULVINI_DATA_ROUTING_THRESHOLD,
    QUANTUM_ROUTING_THRESHOLD,
    PulviniDataOrchestrator,
    PythagorasOrchestrator,
    SolverStrategy,
)

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
    "PULVINI_DATA_ROUTING_THRESHOLD",
    "QUANTUM_ROUTING_THRESHOLD",
    "PulviniDataOrchestrator",
    "PythagorasOrchestrator",
    "SolverStrategy",
]
