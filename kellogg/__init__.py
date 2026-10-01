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
    CONSENSUS_AUTHORITY,
    ProofBoundary,
    VersionLockError,
    attest,
    verify_version,
)

__version__ = "3.5.0"

# Lazy surfaces: tensor_ml requires numpy; exact_field.sqrt_f is kept out
# of the training path by contract (tests assert it never enters
# sys.modules through the ML import chain).
_LAZY_SUBMODULE_ATTRS = {
    "exact_field": ("sqrt_f",),
    "phi_tensor_core": (
        "ManifoldType",
        "MetricTensor",
        "PhiTensorCore",
        "TensorCoreError",
        "TensorOpRecord",
    ),
    "tensor_ml": (
        "CANONICAL",
        "FIELD_ID",
        "MLA1517_VERSION",
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
    "CONSENSUS_AUTHORITY",
    "ProofBoundary",
    "VersionLockError",
    "attest",
    "verify_version",
    # tensor data plane + ML (lazy)
    *_LAZY_SUBMODULE_ATTRS["phi_tensor_core"],
    *_LAZY_SUBMODULE_ATTRS["tensor_ml"],
]
