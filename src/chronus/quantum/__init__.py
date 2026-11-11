"""Legacy finite-field and algebraic research code for Chronus.

This namespace is not TURING and is not a conventional complex-Hilbert-space
quantum-mathematics library. Its finite-field and algebraic constructions are
research models; names and exact arithmetic do not establish physical quantum
semantics, hardware execution, or quantum advantage. See the package README and
``docs/system-update/quantum-package-taxonomy.md`` for scope and limitations.
"""

from chronus.quantum.extension_search import (
    ExtensionSubspaceState,
    exact_extension_search,
    extension_norm,
    extension_one_shot_phases,
    phi_element_power,
)
from chronus.quantum.grover import (
    diffusion,
    grover_iterate,
    grover_trajectory,
    oracle_flip,
)
from chronus.quantum.metallic_search import (
    METALLIC_COEFFICIENTS,
    QSqrt2,
    algebraic_search,
    exact_search,
    exact_search_multi,
    generalized_iterate,
    one_shot_phases,
    one_shot_phases_multi,
    phase_iterate,
    phase_iterate_multi,
)
from chronus.quantum.subspace import (
    SubspaceState,
    exact_subspace_search,
    subspace_iterate,
    uniform_subspace,
)
from chronus.quantum.geometric_polychoron import (
    Cyclotomic5,
    CyclotomicBraidCompiler,
    F257Phi,
    PisotLucasStateCompression,
    Polychoron600Cell,
    QuantumGeometricTensor,
)
from chronus.quantum.statevector import (
    I_UNIT,
    INV_SQRT2,
    MAX_QUBITS,
    OMEGA_8,
    P,
    SQRT2,
    StateVector,
)
from chronus.quantum.entanglement import (
    BellStateKind,
    algebraic_concurrence_determinant,
    create_bell_state,
    create_ghz_state,
    create_superposition_state,
    entanglement_entropy_proxy,
    is_entangled_bipartite,
    superposition_memory_lookup,
)

__all__ = [
    "ExtensionSubspaceState",
    "Cyclotomic5",
    "F257Phi",
    "Polychoron600Cell",
    "QuantumGeometricTensor",
    "CyclotomicBraidCompiler",
    "PisotLucasStateCompression",
    "I_UNIT",
    "INV_SQRT2",
    "MAX_QUBITS",
    "METALLIC_COEFFICIENTS",
    "OMEGA_8",
    "P",
    "QSqrt2",
    "SQRT2",
    "SubspaceState",
    "StateVector",
    "algebraic_search",
    "diffusion",
    "exact_extension_search",
    "exact_search",
    "exact_subspace_search",
    "extension_norm",
    "extension_one_shot_phases",
    "exact_search_multi",
    "generalized_iterate",
    "grover_iterate",
    "grover_trajectory",
    "one_shot_phases",
    "one_shot_phases_multi",
    "oracle_flip",
    "phase_iterate",
    "phase_iterate_multi",
    "phi_element_power",
    "subspace_iterate",
    "uniform_subspace",
    "BellStateKind",
    "create_superposition_state",
    "create_bell_state",
    "create_ghz_state",
    "algebraic_concurrence_determinant",
    "is_entangled_bipartite",
    "entanglement_entropy_proxy",
    "superposition_memory_lookup",
]
