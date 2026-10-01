"""Machine-readable capability/status manifest for the ``tensor`` package.

Statuses are honest, not aspirational:

* ``implemented_tested`` — code exists and has passing unit tests in this
  repository checkout.
* ``hardware_evidence_required`` — the interface exists and fails closed,
  but a real pass requires hardware this sandbox cannot certify (e.g. a
  physical OpenCL/GPU device). No performance or correctness claim is made
  without that evidence.
* ``not_implemented`` — intentionally out of scope for this change.
"""

from __future__ import annotations

from typing import Any, Dict

CAPABILITY_MANIFEST: Dict[str, Dict[str, Any]] = {
    "contracts.validation": {
        "status": "implemented_tested",
        "implementation": "tensor/contracts.py",
        "tests": "tests/test_tensor_contracts.py",
    },
    "backend.numpy_reference": {
        "status": "implemented_tested",
        "implementation": "tensor/backends/numpy_backend.py",
        "tests": "tests/test_tensor_backends.py",
    },
    "backend.chronus_adapter": {
        "status": "hardware_evidence_required",
        "implementation": "tensor/backends/chronus_backend.py",
        "tests": "tests/test_tensor_backends.py (availability honesty only)",
        "evidence_needed": (
            "A host with a chronus-detectable OpenCL device, plus a Chronus "
            "tensor kernel (none exists yet; SUPPORTED_OPERATIONS is empty)."
        ),
    },
    "router.explicit_backend_fail_closed": {
        "status": "implemented_tested",
        "implementation": "tensor/router.py",
        "tests": "tests/test_tensor_backends.py",
    },
    "router.policy_gated_fallback": {
        "status": "implemented_tested",
        "implementation": "tensor/router.py",
        "tests": "tests/test_tensor_backends.py",
    },
    "runtime.timing_cancellation_memory": {
        "status": "implemented_tested",
        "implementation": "tensor/runtime.py",
        "tests": "tests/test_tensor_runtime.py",
    },
    "tflops.declared_op_count_only": {
        "status": "implemented_tested",
        "implementation": "tensor/contracts.py:TensorMeasurement",
        "tests": "tests/test_tensor_contracts.py",
    },
    "exact.kellogg_exact_tensor": {
        "status": "implemented_tested",
        "implementation": "kellogg/exact_tensor.py (bridged via tensor/kellogg_bridge.py)",
        "tests": "tests/test_kellogg_tensor.py",
    },
    "exact.kellogg_quantum_tensor": {
        "status": "implemented_tested",
        "implementation": "kellogg/quantum_tensor.py (bridged via tensor/kellogg_bridge.py)",
        "tests": "tests/test_kellogg_tensor.py",
    },
    "exact.kellogg_tensor_ml": {
        "status": "implemented_tested",
        "implementation": "kellogg/tensor_ml.py (bridged via tensor/kellogg_bridge.py)",
        "tests": "tests/test_toe_tensor_ml.py",
    },
    "vqc.exact_and_quantum_tensor_loaders": {
        "status": "implemented_tested",
        "implementation": "tensor/kellogg_bridge.py:load_exact_tensor_module/load_quantum_tensor_module",
        "tests": "tests/test_tensor_package.py",
    },
    "mining.advisor_boundary": {
        "status": "implemented_tested",
        "implementation": "hyba/hybrid/tensor_advisor.py (re-exported by tensor/advisor.py)",
        "tests": "tests/test_three_layer_runtime.py, tests/test_tensor_advisor_safety.py",
    },
    "compat.gpu_tensor_shim": {
        "status": "implemented_tested",
        "implementation": "gpu/tensor.py",
        "tests": "tests/test_tensor_gpu_compat.py",
    },
    "packaging.tensor_distribution": {
        "status": "implemented_tested",
        "implementation": "pyproject.toml ([tool.setuptools] packages, package-data)",
        "tests": "tests/test_package_layout.py",
    },
    "grover.hendrix_entry_points": {
        "status": "not_implemented",
        "implementation": None,
        "evidence_needed": (
            "No currently-supported Grover/Hendrix tensor entry point was "
            "found wired to production code in this audit; see "
            "docs/TENSOR_ARCHITECTURE.md for the audit notes. Add a bridge "
            "here if/when such an entry point is identified as in-scope."
        ),
    },
    "vqc_manifold_bridge": {
        "status": "not_implemented",
        "implementation": None,
        "evidence_needed": (
            "Intelligence/asi/manifold_bridge.py exists but is an advisory "
            "ASI surface, not a tensor execution entry point; no production "
            "consumer imports it through a tensor contract today."
        ),
    },
}


def render_markdown() -> str:
    """Render the manifest as a Markdown table (used to regenerate the docs)."""
    lines = ["| Feature | Status | Implementation | Tests/Evidence |", "|---|---|---|---|"]
    for feature, row in CAPABILITY_MANIFEST.items():
        impl = row.get("implementation") or "—"
        evidence = row.get("tests") or row.get("evidence_needed") or "—"
        lines.append(f"| `{feature}` | {row['status']} | `{impl}` | {evidence} |")
    return "\n".join(lines)


__all__ = ["CAPABILITY_MANIFEST", "render_markdown"]
