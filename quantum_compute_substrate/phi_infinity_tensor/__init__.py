"""HYBA Quantum Tensor X-Infinity.

Rank-6 implicit tensor at phi^37 scale in each axis. Never materialized.
Every element is computed on demand from a generative phi-character rule.

This is the mathematical monument that supports the entire substrate:
  * axis 0 (Time)          - temporal evolution
  * axis 1 (Space)         - spatial configuration
  * axis 2 (QuantumState)  - amplitude distribution
  * axis 3 (Entanglement)  - quantum correlations
  * axis 4 (Coherence)     - phase relationships
  * axis 5 (Topology)      - invariant structure

Each axis has length L(37) = 54,018,521 (round(phi^37) exactly).
Total elements: L(37)^6 ~ 2.48 x 10^46.
"""

from .phi_identities import (
    PHI,
    PHI_STR_100,
    fib,
    lucas,
    phi_power_identity_holds,
)
from .dimensions import TensorDimension, AXIS_NAMES, AXIS_MEANINGS
from .tensor import HYBAQuantumTensorXInfinity, make_default_tensor
from .generator import PhiCharacterRule, RankOneRule
from .network import MPSNetwork
from .operations import (
    tensor_product,
    contract,
    phi_scaling_transform,
    quantum_fourier_transform_all_axes,
    topological_decomposition,
)
from .comparisons import (
    compare_to_universe,
    compare_to_storage,
    compare_to_computational_limits,
    honest_size_context,
)
from .decomposition import (
    svd_metadata,
    cp_decomposition_metadata,
    tucker_decomposition_metadata,
    tensor_train_metadata,
)
from .factory import (
    create_base_tensor,
    create_scaled_tensor,
    create_n_dimensional_tensor,
    create_quantum_state_tensor,
)

__all__ = [
    "PHI",
    "PHI_STR_100",
    "fib",
    "lucas",
    "phi_power_identity_holds",
    "TensorDimension",
    "AXIS_NAMES",
    "AXIS_MEANINGS",
    "HYBAQuantumTensorXInfinity",
    "make_default_tensor",
    "PhiCharacterRule",
    "RankOneRule",
    "MPSNetwork",
    "tensor_product",
    "contract",
    "phi_scaling_transform",
    "quantum_fourier_transform_all_axes",
    "topological_decomposition",
    "compare_to_universe",
    "compare_to_storage",
    "compare_to_computational_limits",
    "honest_size_context",
    "svd_metadata",
    "cp_decomposition_metadata",
    "tucker_decomposition_metadata",
    "tensor_train_metadata",
    "create_base_tensor",
    "create_scaled_tensor",
    "create_n_dimensional_tensor",
    "create_quantum_state_tensor",
]

# v0.4.1 qubit-scale additions
from .qubit_scale import (
    QubitMPS,
    bell_pair,
    uniform_superposition,
    ghz_state,
    H_GATE,
    X_GATE,
    Y_GATE,
    Z_GATE,
    S_GATE,
    T_GATE,
    I2,
    CNOT_MAT,
    CNOT_TENSOR,
)
from .phi_fold_compression import (
    PhiFoldCompressor,
    CompressionMetrics,
    benchmark_on,
)
from .qubit_demo import demonstrate_n_qubits, demonstrate_compression_across_scales
