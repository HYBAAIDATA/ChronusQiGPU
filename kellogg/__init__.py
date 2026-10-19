"""Kellogg — the PYTHIA tensor system.

The Kellogg Tensor (K) is the substrate-agnostic quantum-algebraic tensor
substrate of the PYTHIA repository. It is its own package and its own
system: TOE, Intelligence, and the MLA1517 mining path are *consumers* of
Kellogg — Kellogg owns the tensor, nothing else does.

Package layout:

    kellogg.exact_tensor     Exact substrate over F4 = Q(zeta_8): Qsqrt2,
                             F4, ExactStateVector, ExactTOETensor, the
                             declared Clifford+T gate set, exact Born
                             weights, deterministic measurement. Zero
                             floating-point drift; unsupported operations
                             fail closed.
    kellogg.exact_field      Exact sqrt_f over F4; plane-checked value
                             algebra (kept outside the training path by
                             contract, so it is lazy-loaded here).
    kellogg.quantum_tensor   Finite-precision C^N substrate: Complex,
                             ComplexMatrix, QuantumState, Observables,
                             Born rule, QFI, path-integral propagation,
                             the 32-face dual-overlay frame.
    kellogg.scales           Layer-0/1 algebraic scales: the exact Z[phi]
                             ring, Lucas/Binet/Pisot drift, Zeckendorf
                             folds, and the Cassini integrity ledger.
    kellogg.tensor_network   MPS, TT and MPO decomposition/operator algebra.
    kellogg.compressed_tensor Compression-aware quantum operator execution.
    kellogg.tensor_serialization Safe checksummed tensor artifact persistence.
    kellogg.tensor_ml        Exact-tensor ML family (canonical
                             ``exact_linear``), plane-separated
                             preprocessing, commitments/Merkle roots,
                             CV folds, JSON artifact persistence, and the
                             proof-governance gate.
    kellogg.traversal        Layer-6 traversal: 32-face frame, QFI face
                             bias, Cassini-certified geodesic steps, and
                             machine-checkable coverage certificates.
    kellogg.attest           Layer-7 attestation: proof boundaries,
                             canonical digests, version locks, and
                             Zeckendorf/Cassini certificates.
    kellogg.first_principles Dynamical substrate: standard-map KAM
                             diagnostics, continuous golden-angle gaps,
                             generalized-golden QMC, and drift-free
                             modular sampling. Device cost is not
                             computed here; Aethel prices the overhead.

Golden substrate (the DphiT stack; numpy, lazy-loaded):

    kellogg.dphi_transform   Discrete-phi transform: Sturmian Z[phi]
                             lattice split/merge, bit-exact integer
                             lifting, depth-d coefficient layout, the
                             reversible renormalizer, and the DphiT-vs-FFT
                             stability benchmark.
    kellogg.golden_convolution  DphiT convolution, Zeckendorf shifts,
                             the O(N^2) structural sum, and measured
                             transform-vs-structural error.
    kellogg.phi_dynamics     Golden Laplacian eigenspectrum, coefficient
                             propagation, structural fidelity, and the
                             symplectic integer time step.
    kellogg.golden_stealth   Scale-domain carrier encode/cloak/recover
                             and the Fourier-vs-golden recovery duel.
    kellogg.phi_stability    Stability horizon: MLE, Greene-residue
                             critical-K bisection, NN-variance and
                             discrepancy coverage, plastic sequences.
    kellogg.golden_stride    Cache-aware golden strides and the sparse
                             coverage benchmark.
    kellogg.phi_renormalizer Integer-exact phi renormalization group,
                             critical-Ising chain utilities, and the
                             Chrysalis decode benchmark.

Exact tensor networks (custody-backed; Q(zeta_8) on integer coordinates):

    kellogg.cyclotomic       Q8: Q(zeta_8) on integers, bit-equal to F4.
    kellogg.exact_linalg     Exact elimination: RREF, rank factorization,
                             inverse, solve, PSD, over any exact field.
    kellogg.custody          Where every core and certificate lives: the
                             custody protocol, resident custody, and the
                             fold-store binding (Aethel, by protocol).
    kellogg.certificate      TensorCertificate, CEX canonical JSON,
                             composition, Merkle aggregation and proofs.
    kellogg.exact_network    Exact TT / MPS / MPO with structural lossless
                             compression and a certificate per operation.
    kellogg.channels         Exact Kraus maps, Pauli Hamiltonians, Fisher.
    kellogg.surface_code     Planar surface code over GF(2), exact distance,
                             exact-MWPM and union-find decoders.
    kellogg.substrate        (Z[phi], R): transfer matrix identities, cat
                             map, Q(phi), beta-expansion, exact discrepancy.
    kellogg.vector11         The 11D golden-weighted vector, exact fold.
    kellogg.dmrg             Two-site DMRG (float plane).
    kellogg.spec             The canonical tensor specification registry.
    kellogg.benchmark        Correctness, cost and meta benchmarks.

Two scalar planes share the package by design:

* ``exact``      — F4/Qsqrt2 Fraction arithmetic; certificates and
                   authority data live here.
* ``diagnostic`` — IEEE-754 complex arithmetic; measurement-only displays.

``kellogg.exact_tensor`` and ``kellogg.quantum_tensor`` are pure-stdlib
and imported eagerly. The ``kellogg.tensor_ml`` names (which require
numpy) and ``sqrt_f`` (kept out of the training path by contract) resolve
lazily through ``__getattr__``.

Historical name: the Kellogg Tensor formalism (AGENTS.md, Appendix C;
docs/M32_TENSOR_BRIDGE.md), K over the structured search space
S = (X, G, M, g, chi, H*). PULVINI is the numerical execution package
that consumes this tensor; it is not the tensor itself.
"""

from __future__ import annotations

import importlib
from typing import Any

from .exact_tensor import (
    GATES,
    I_UNIT,
    MINUS_ONE,
    ONE,
    SQRT2,
    ZERO,
    ZETA8,
    ExactGate,
    ExactResourceError,
    ExactStateVector,
    ExactTOETensor,
    F4,
    NotInF4,
    Qsqrt2,
    canonical_digest,
    density_is_pure,
    density_purity,
    density_trace,
    hermitian_eigenvalues,
    phase_gate,
    rz,
    von_neumann_entropy,
)
from .quantum_tensor import (
    Complex,
    ComplexMatrix,
    IrreversibleBoundary,
    Observables,
    QuantumState,
    born_probabilities,
    causal_factor_ranking,
    decoherence_measure,
    density_matrix_purity,
    dual_overlay_frame,
    effective_subspace_dimension,
    encode_data_to_state,
    model_agreement_from_ensemble,
    path_integral_propagate,
    project_to_32_face,
    quantum_fisher_information,
    state_tomography,
    trajectory_forecast,
)
from .quantum_tensor import (
    float_to_exact,
    partial_trace as partial_trace_density,
)
from .quantum_tensor import von_neumann_entropy as float_von_neumann_entropy
from .scales import (
    PHI,
    NotRepresentable,
    Zphi,
    binet_fold,
    cassini,
    cassini_store,
    cassini_verify,
    fibonacci,
    lucas,
    phi_power,
    pisot_drift,
    pisot_wind,
    zeckendorf,
    zeckendorf_11d,
    zeckendorf_is_legal,
)
from .traversal import (
    FRAME_32,
    TRAVERSAL_STRIDE,
    CoverageCertificate,
    bloch_vector,
    cassini_offset,
    coverage_certificate,
    face_bias,
    geodesic_step,
)
from .attest import (
    ATTESTATION_SCHEMA,
    CONSENSUS_AUTHORITY,
    AttestationError,
    ProofBoundary,
    VersionLockError,
    attest,
    verify_attestation,
    verify_version,
)
from .canonical_tensor import (
    CanonicalKelloggTensor,
    CoverageProofCertificate,
    RepresentationChoice,
    build_kellogg_search_plan,
    host_sha256d_recheck,
)

__version__ = "1.0.0"

# Lazy surfaces: tensor_ml requires numpy; exact_field.sqrt_f is kept out
# of the training path by contract (tests assert it never enters
# sys.modules through the ML import chain).
_LAZY_SUBMODULE_ATTRS = {
    "cyclotomic": ("Q8", "NotReal"),
    "exact_linalg": ("SingularMatrix", "cr_factor", "rref"),
    "custody": ("CustodyError", "FoldStoreCustody", "ResidentCustody", "default_custody"),
    "certificate": (
        "AggregateCertificate",
        "CertificateError",
        "CertificateLedger",
        "TensorCertificate",
        "aggregate",
        "certify",
        "cex",
        "compose",
        "merkle_proof",
        "verify_certificate",
        "verify_merkle_proof",
    ),
    "exact_network": (
        "Core",
        "ExactMPO",
        "ExactMPS",
        "ExactNetworkError",
        "ExactTensorTrain",
        "ghz_circuit",
        "heisenberg_mpo",
        "ising_mpo",
    ),
    "channels": (
        "KrausChannel",
        "PauliHamiltonian",
        "channel_mpo",
        "cramer_rao_holds",
        "fisher_matrix",
        "heisenberg_bound_holds",
        "pauli_rotation",
    ),
    "surface_code": ("PlanarSurfaceCode", "SurfaceCodeError", "edge_star_report"),
    "substrate": (
        "QPhi",
        "TRANSFER",
        "cassini_step",
        "cat_map",
        "korobov_point",
        "lucas_cassini",
        "lucas_wind",
        "phi_beta_expansion",
        "star_discrepancy_2d",
    ),
    "vector11": ("RootVector", "fold", "lift", "unfold", "unit_lift"),
    "dmrg": ("DMRGResult", "dmrg"),
    "spec": ("REGISTRY", "SpecItem", "verify_registry"),
    "dphi_transform": (
        "DphiTError",
        "INV_PHI",
        "INV_PHI_SQ",
        "ReversibleRenormalizer",
        "StabilityBenchmarkResult",
        "dphi_transform",
        "fibonacci_word_signal",
        "get_golden_grading_vector",
        "golden_lifting_step",
        "idphi_transform",
        "inverse_golden_lifting_step",
        "merge_phi_lattice",
        "phi_lattice_mask",
        "run_stability_benchmark",
        "split_phi_lattice",
    ),
    "exact_field": ("sqrt_f",),
    "golden_convolution": (
        "GoldenConvolutionError",
        "convolution_theorem_error",
        "golden_convolution",
        "golden_scale_filter",
        "golden_shift",
        "structural_convolution_sum",
        "structural_vs_transform_error",
        "zeckendorf_scale",
    ),
    "golden_stealth": (
        "GoldenStealth",
        "GoldenStealthError",
        "StealthDuelResult",
        "run_stealth_duel",
    ),
    "golden_stride": (
        "CacheAwareGoldenStride",
        "GoldenHilbertOptimizer",
        "GoldenStrideError",
        "sparse_coverage_benchmark",
    ),
    "phi_dynamics": (
        "FidelityDeltaResult",
        "GoldenDynamicsError",
        "apply_golden_laplacian",
        "golden_propagate",
        "measure_structural_fidelity",
        "propagation_energy_drift",
        "reversible_time_step",
        "run_fidelity_duel",
        "standard_fft_wave_propagation",
    ),
    "phi_renormalizer": (
        "ChrysalisResult",
        "RGEfficiencyResult",
        "RenormalizationError",
        "benchmark_rg_efficiency",
        "block_spin_decimate",
        "chrysalis_benchmark",
        "critical_ising_chain",
        "generate_ising_chain",
        "mutual_information",
        "phi_reconstruct_deep",
        "phi_renormalize_deep",
        "phi_rg_step",
        "scale_information_retained",
    ),
    "phi_stability": (
        "GREENE_CRITICAL_RESIDUE",
        "GoldenStabilityEngine",
        "PlasticSequenceGenerator",
        "StabilityError",
        "StabilityMetrics",
        "benchmark_golden_vs_others",
        "continued_fraction_convergent",
    ),
    "phi_tensor_core": (
        "ManifoldType",
        "MetricTensor",
        "PhiTensorCore",
        "TensorCoreError",
        "TensorOpRecord",
    ),
    "tensor_network": (
        "HeisenbergHamiltonianMPO",
        "IsingHamiltonianMPO",
        "MatrixProductOperator",
        "TensorNetworkAudit",
        "TensorNetworkError",
        "TensorTrain",
        "hamiltonian_with_tensor_network",
        "mps_decompose",
        "mps_reconstruct",
        "natural_gradient_step",
        "persistent_homology_comparison",
        "phi_guided_rank",
        "quantum_fisher_metric",
        "topology_preserved",
        "topology_signature",
        "tt_compress_with_budget",
        "tt_decompose",
        "tt_reconstruct",
        "tt_svd",
    ),
    "compressed_tensor": (
        "CompressedQuantumState",
        "CompressedTensor",
        "CompressedTensorError",
        "CompressionScheme",
        "EngineConfig",
        "ExpertRouter",
        "MeasurementResult",
        "OperatorType",
        "Precision",
        "QuantumCompressedTensorEngine",
        "QuantumOperator",
    ),
    "tensor_serialization": (
        "TensorSerializationError",
        "load_pv",
        "save_pv",
        "validate_pv",
    ),
    "tensor_ml": (
        "CANONICAL",
        "FIELD_ID",
        "ARTIFACT_SCHEMA",
        "MLA1517_VERSION",
        "SUBSTRATE_TAG",
        "TOE_VERSION",
        "DiagnosticValue",
        "ExactValue",
        "Fold",
        "GovernanceValue",
        "Plane",
        "PlaneViolation",
        "Proof",
        "ProofTamperedError",
        "SchemaTag",
        "TensorClassifier",
        "TensorModelAPI",
        "TensorSimpleImputer",
        "TensorState",
        "TensorStandardScaler",
        "TensorTfidfVectorizer",
        "Unitary",
        "accuracy_score",
        "apply_unitary",
        "center_apply",
        "center_fit",
        "commit",
        "cross_val_score",
        "dump",
        "exact_accuracy",
        "exact_f1",
        "exact_linear",
        "exact_precision",
        "exact_recall",
        "f1_score",
        "fit",
        "from_int",
        "from_rat",
        "govern",
        "joint",
        "joint_for_cv",
        "kfold",
        "load",
        "load_proof",
        "measure",
        "median_f",
        "merkle_root",
        "partial_trace",
        "plane_multiply",
        "precision_score",
        "predict",
        "predict_proba",
        "preprocess_exact",
        "range_apply",
        "range_fit",
        "recall_score",
        "re_encode",
        "row_commit",
        "save",
        "verify",
        "verify_artifact",
        "witness_scalar",
    ),
}

_LAZY_ATTR_MODULE = {
    attr: module for module, attrs in _LAZY_SUBMODULE_ATTRS.items() for attr in attrs
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_ATTR_MODULE.get(name)
    if module_name is not None:
        value = getattr(importlib.import_module(f".{module_name}", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_ATTR_MODULE))


__all__ = [
    # exact field
    "Qsqrt2",
    "F4",
    "ZERO",
    "ONE",
    "MINUS_ONE",
    "I_UNIT",
    "SQRT2",
    "ZETA8",
    "sqrt_f",
    "density_trace",
    "density_purity",
    "density_is_pure",
    # exact state vector
    "ExactStateVector",
    "ExactGate",
    "GATES",
    "ExactResourceError",
    "NotInF4",
    "ExactTOETensor",
    "canonical_digest",
    "phase_gate",
    "rz",
    "hermitian_eigenvalues",
    "von_neumann_entropy",
    # algebraic scales (Layers 0-1)
    "Zphi",
    "NotRepresentable",
    "PHI",
    "fibonacci",
    "lucas",
    "phi_power",
    "binet_fold",
    "pisot_drift",
    "pisot_wind",
    "zeckendorf",
    "zeckendorf_11d",
    "zeckendorf_is_legal",
    "cassini",
    "cassini_verify",
    "cassini_store",
    # finite-precision complex substrate
    "Complex",
    "ComplexMatrix",
    "QuantumState",
    "Observables",
    "quantum_fisher_information",
    "dual_overlay_frame",
    "project_to_32_face",
    "effective_subspace_dimension",
    "path_integral_propagate",
    "trajectory_forecast",
    "causal_factor_ranking",
    "born_probabilities",
    "density_matrix_purity",
    "decoherence_measure",
    "model_agreement_from_ensemble",
    "encode_data_to_state",
    "state_tomography",
    "IrreversibleBoundary",
    "float_to_exact",
    "partial_trace_density",
    "float_von_neumann_entropy",
    # traversal (Layer 6)
    "FRAME_32",
    "TRAVERSAL_STRIDE",
    "CoverageCertificate",
    "bloch_vector",
    "cassini_offset",
    "coverage_certificate",
    "face_bias",
    "geodesic_step",
    # attestation (Layer 7)
    "ATTESTATION_SCHEMA",
    "CONSENSUS_AUTHORITY",
    "AttestationError",
    "ProofBoundary",
    "VersionLockError",
    "attest",
    "verify_attestation",
    "verify_version",
    # canonical tensor (canonical representation and coverage proof)
    "CanonicalKelloggTensor",
    "CoverageProofCertificate",
    "RepresentationChoice",
    "build_kellogg_search_plan",
    "host_sha256d_recheck",
    # exact tensor networks, custody, certificates, specification (lazy)
    *_LAZY_SUBMODULE_ATTRS["cyclotomic"],
    *_LAZY_SUBMODULE_ATTRS["exact_linalg"],
    *_LAZY_SUBMODULE_ATTRS["custody"],
    *_LAZY_SUBMODULE_ATTRS["certificate"],
    *_LAZY_SUBMODULE_ATTRS["exact_network"],
    *_LAZY_SUBMODULE_ATTRS["channels"],
    *_LAZY_SUBMODULE_ATTRS["surface_code"],
    *_LAZY_SUBMODULE_ATTRS["substrate"],
    *_LAZY_SUBMODULE_ATTRS["vector11"],
    *_LAZY_SUBMODULE_ATTRS["dmrg"],
    *_LAZY_SUBMODULE_ATTRS["spec"],
    # golden substrate + tensor data plane + ML (lazy)
    *_LAZY_SUBMODULE_ATTRS["dphi_transform"],
    *_LAZY_SUBMODULE_ATTRS["golden_convolution"],
    *_LAZY_SUBMODULE_ATTRS["golden_stealth"],
    *_LAZY_SUBMODULE_ATTRS["golden_stride"],
    *_LAZY_SUBMODULE_ATTRS["phi_dynamics"],
    *_LAZY_SUBMODULE_ATTRS["phi_renormalizer"],
    *_LAZY_SUBMODULE_ATTRS["phi_stability"],
    *_LAZY_SUBMODULE_ATTRS["phi_tensor_core"],
    *_LAZY_SUBMODULE_ATTRS["tensor_network"],
    *_LAZY_SUBMODULE_ATTRS["compressed_tensor"],
    *_LAZY_SUBMODULE_ATTRS["tensor_serialization"],
    *_LAZY_SUBMODULE_ATTRS["tensor_ml"],
]
