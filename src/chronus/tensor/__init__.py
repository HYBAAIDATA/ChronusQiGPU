"""Chronus Consortium Falsifiable Tensor Engine.

Auditable block-sparse tensor network engine with rigorous mathematical bounds,
explicit error ledgers, hardware-derived caps, and honest refusals.
"""

from chronus.tensor.charter import (
    CharterViolation,
    ConsortiumCharter,
    ScientificIntegrityLead,
    charter,
    program_entry_check,
    scientific_integrity_lead,
)
from chronus.tensor.dmrg import (
    DMRG,
    qsim_ground_energy_32,
    truncate_to_first_32,
)
from chronus.tensor.evolution import (
    evolve_tdvp,
    evolve_trotter,
)
from chronus.tensor.experiments import (
    E1_exactness_oracle,
    E2_symmetry_stress_test,
    E3_honest_1000_node_claim,
    ExperimentResult,
    PUBLISH,
    reference_statevector_simulation,
)
from chronus.tensor.gate import (
    apply_gate,
    bound_from_method,
    factorize_two_site,
    theorem_for,
)
from chronus.tensor.hamiltonian import (
    HamiltonianTerm,
    TFIM_terms,
    build_hamiltonian_mpo,
)
from chronus.tensor.measurement import (
    expectation_value,
    sample_measurement,
)
from chronus.tensor.network import (
    HARD_CAP_THEOREM,
    TensorNetwork,
    build_network,
)
from chronus.tensor.peps import (
    contract_peps_approximate,
)
from chronus.tensor.enhanced_representation import (
    EnhancedTensorRepresentation,
    TensorNetworkNDArray,
)
from chronus.tensor.adaptive_contraction import (
    AdaptiveTensorContractionPathway,
)
from chronus.tensor.causal_intelligence import (
    CausalInterferenceEngine,
)
from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.folded_inference import FoldedInferencePilot
from chronus.tensor.geodesic import (
    BackendProfile,
    EnergyComparison,
    EnergyModel,
    GeodesicScheduler,
    HybridGPU,
    IntegrityVerdict,
    KernelBoundary,
    KernelLaunchConfig,
    MetricTensor,
    PhiGPU,
    PhiMemoryHierarchy,
    PhiTensorCore,
    ProfiledHybridRouter,
    TopologicalIntegrityGate,
)
from chronus.tensor.opencl_backend import OpenCLTensorBackend, OpenCLTensorUnavailable
from chronus.tensor.cuda_backend import CUDATensorBackend, CUDATensorUnavailable
from chronus.tensor.metal_backend import MetalTensorBackend, MetalTensorUnavailable
from chronus.tensor.types import (
    BondId,
    ChargeTuple,
    ContractionCertificate,
    ErrorLedger,
    Leg,
    LegDirection,
    Node,
    RefusedMethod,
    SymmetricTensor,
    TruncationRecord,
    UnsupportedHamiltonian,
    UntrustedApproximation,
    UntrustedResult,
    charge_conserving,
    theory_saving,
)

__all__ = [
    # Charter
    "charter",
    "program_entry_check",
    "scientific_integrity_lead",
    "ConsortiumCharter",
    "ScientificIntegrityLead",
    "CharterViolation",
    # Types & Exceptions
    "Leg",
    "LegDirection",
    "SymmetricTensor",
    "Node",
    "TruncationRecord",
    "ContractionCertificate",
    "ErrorLedger",
    "ChargeTuple",
    "BondId",
    "theory_saving",
    "charge_conserving",
    "UntrustedApproximation",
    "UntrustedResult",
    "UnsupportedHamiltonian",
    "RefusedMethod",
    # Network
    "HARD_CAP_THEOREM",
    "TensorNetwork",
    "build_network",
    "EnhancedTensorRepresentation",
    "TensorNetworkNDArray",
    "AdaptiveTensorContractionPathway",
    "CausalInterferenceEngine",
    # Gate & Decomposition
    "apply_gate",
    "factorize_two_site",
    "theorem_for",
    "bound_from_method",
    # Hamiltonian & MPO
    "HamiltonianTerm",
    "TFIM_terms",
    "build_hamiltonian_mpo",
    # Evolution
    "evolve_tdvp",
    "evolve_trotter",
    # Measurement
    "sample_measurement",
    "expectation_value",
    # 2D PEPS
    "contract_peps_approximate",
    # DMRG
    "DMRG",
    "truncate_to_first_32",
    "qsim_ground_energy_32",
    # Experiments
    "ExperimentResult",
    "E1_exactness_oracle",
    "E2_symmetry_stress_test",
    "E3_honest_1000_node_claim",
    "PUBLISH",
    "reference_statevector_simulation",
    "ExactFoldState",
    "FoldedInferencePilot",
    "BackendProfile",
    "EnergyComparison",
    "EnergyModel",
    "GeodesicScheduler",
    "HybridGPU",
    "IntegrityVerdict",
    "KernelBoundary",
    "KernelLaunchConfig",
    "MetricTensor",
    "PhiGPU",
    "PhiMemoryHierarchy",
    "PhiTensorCore",
    "ProfiledHybridRouter",
    "TopologicalIntegrityGate",
    "OpenCLTensorBackend",
    "OpenCLTensorUnavailable",
    "CUDATensorBackend",
    "CUDATensorUnavailable",
    "MetalTensorBackend",
    "MetalTensorUnavailable",
]
