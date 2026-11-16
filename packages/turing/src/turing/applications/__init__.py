"""TURING VQC applications: 1,000-qubit stabilizer machine + variational Grover.

`turing.applications` carries application layers over the canonical exact
core. The canonical stabilizer remains
`turing.algorithms.clifford` (bit-packed Aaronson-Gottesman) and
`turing.exact.stabilizer` (finite-field qudit tableau).

- `vqc_fold`: vendored PULVINI fold kernel, byte-identical (sha256
  `8D14A821…`) to the guarded `chronus.pulvini.formal`. Vendored, not
  imported, because TURING never imports `chronus`.
- `vqc_machine`: 1,000-logical-qubit NumPy stabilizer machine with affine
  Z-sampler, QASM-2.0 subset importer, fold checkpoints and the
  12-algorithm planning catalogue. Source: HYBA_1000_QUBIT_VQC_20260724
  (sha256 `7B4EF036…`).
- `vqc_grover`: 32-face variational nonce ranker with injectable M_32
  adjacency, SHA-256d verifier and bounded fallback. Application
  heuristic — validity is SHA-256d only, never the rank.

Not production qualification: unfalsified archive claims (training-loss
curves, 4.1775e-16 checkpoint error, 144/144 suite) are provenance, not
current-commit evidence.
"""

from turing.applications.vqc_fold import (
    PHI,
    FoldState,
    PhiRecursiveOperator,
    ValidationError,
)
from turing.applications.vqc_grover import (
    PhiGroverVQC,
    VQCConfig,
    VQCPhiGroverIntegration,
    VQCTrainingDataGenerator,
)
from turing.applications.vqc_machine import (
    ALGORITHM_CATALOG,
    AffineZSampler,
    ExecutionResult,
    PhiCheckpoint,
    PhiQuantumCircuit,
    PhiQuantumMachine1000,
    StabilizerRegister,
    run_1000_qubit_demonstration,
)

__all__ = [
    "ALGORITHM_CATALOG",
    "AffineZSampler",
    "ExecutionResult",
    "FoldState",
    "PHI",
    "PhiCheckpoint",
    "PhiGroverVQC",
    "PhiQuantumCircuit",
    "PhiQuantumMachine1000",
    "PhiRecursiveOperator",
    "StabilizerRegister",
    "VQCConfig",
    "VQCPhiGroverIntegration",
    "VQCTrainingDataGenerator",
    "ValidationError",
    "run_1000_qubit_demonstration",
]
