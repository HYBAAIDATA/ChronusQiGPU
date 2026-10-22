"""φ-Folding Engine (Φ-UFE) v1.2.1 — platform substrate, gap-closure complete.

Package tree matches CERN-grade platform layout:
  backends/ kernels/ corpus/ ai/ deterministic/ geometry/ streaming/ cli/
"""

from .ai import make_jax_layer, make_torch_module, train_phi_layer_classifier
from .ai_layers import PhiFoldLayer, layer_roundtrip_error, onnx_op_spec
from .backend_router import ArrayBackend, probe_backends, select_backend

# Platform packages
from .backends.router import hermes_batch_plan, hermes_schedule
from .corpus import run_all_corpus_scorecards
from .deterministic import (
    AuditTrail,
    PhiDeterministicMode,
    deterministic_fold,
    deterministic_unfold,
    run_compliance_demo,
)
from .deterministic import verify as deterministic_verify
from .embeddings import embed_roundtrip_error, phi_embed, phi_unembed
from .geometry import GeometryReport, build_phase_diagram, characterize, full_geometry
from .holograph_nd import fold as holograph_nd_fold
from .holograph_nd import metrics as holograph_nd_metrics
from .holograph_nd import unfold as holograph_nd_unfold
from .invariants import InvariantReport, compute_invariants
from .kernels import compile_status, list_cuda_sources
from .real_workloads import run_real_workload_scorecards
from .regime_selector import RegimePrediction, get_or_train_model, predict_regime, train_selector
from .scientific import run_scientific_suite
from .streaming import PhiStream, PhiStreamEngine, run_telemetry_integration
from .ufe import ENGINE_VERSION, MODES, PhiFoldingEngine, ProfileCard

# bump patch for gap-closure packaging
try:
    from .ufe import ENGINE_VERSION as _V

    if _V == "1.2.0":
        # keep engine file as source of truth; expose platform tag
        PLATFORM_TAG = "1.2.1-gap-closure"
    else:
        PLATFORM_TAG = _V
except Exception:
    PLATFORM_TAG = "1.2.1-gap-closure"

__all__ = [
    "PhiFoldingEngine",
    "ENGINE_VERSION",
    "PLATFORM_TAG",
    "MODES",
    "ProfileCard",
    "InvariantReport",
    "compute_invariants",
    "select_backend",
    "probe_backends",
    "ArrayBackend",
    "hermes_schedule",
    "hermes_batch_plan",
    "list_cuda_sources",
    "compile_status",
    "predict_regime",
    "train_selector",
    "get_or_train_model",
    "RegimePrediction",
    "PhiStream",
    "PhiStreamEngine",
    "run_telemetry_integration",
    "phi_embed",
    "phi_unembed",
    "embed_roundtrip_error",
    "deterministic_fold",
    "deterministic_unfold",
    "deterministic_verify",
    "PhiDeterministicMode",
    "run_compliance_demo",
    "AuditTrail",
    "characterize",
    "full_geometry",
    "GeometryReport",
    "build_phase_diagram",
    "holograph_nd_fold",
    "holograph_nd_unfold",
    "holograph_nd_metrics",
    "run_real_workload_scorecards",
    "run_scientific_suite",
    "run_all_corpus_scorecards",
    "PhiFoldLayer",
    "layer_roundtrip_error",
    "onnx_op_spec",
    "train_phi_layer_classifier",
    "make_torch_module",
    "make_jax_layer",
]