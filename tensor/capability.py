"""Machine-readable evidence manifest for the Tensor package."""

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
        "implementation": "tensor/backends/chronus_backend.py + chronus/tensor_compute.py + chronus/kernels/tensor_ops.cl",
        "tests": "tests/test_chronus_tensor_compute.py",
        "evidence_needed": "Physical OpenCL GPU numerical comparison against NumPy reference.",
    },
    "hardware.chronus_tensor_kernels": {
        "status": "hardware_evidence_required",
        "implementation": "chronus/kernels/tensor_ops.cl; chronus/tensor_compute.py",
        "tests": "tests/test_chronus_tensor_compute.py",
        "evidence_needed": "Physical float32 matmul/add/hadamard/scale/kron run with TensorMeasurement/provenance.",
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
        "implementation": "kellogg/exact_tensor.py via tensor/kellogg_bridge.py",
        "tests": "tests/test_kellogg_tensor.py",
    },
    "exact.kellogg_quantum_tensor": {
        "status": "implemented_tested",
        "implementation": "kellogg/quantum_tensor.py via tensor/kellogg_bridge.py",
        "tests": "tests/test_kellogg_tensor.py",
    },
    "exact.kellogg_tensor_ml": {
        "status": "implemented_tested",
        "implementation": "kellogg/tensor_ml.py via tensor/kellogg_bridge.py",
        "tests": "tests/test_toe_tensor_ml.py",
    },
    "pulvini.exact_geodesic_engine": {
        "status": "implemented_tested",
        "implementation": "python_backend/core_modules/geodesic_tensor_engine.py",
        "tests": "tests/test_geodesic_tensor_engine.py, tests/test_geodesic_tensor_extensions.py",
    },
    "pulvini.true_partial_unfold": {
        "status": "implemented_tested",
        "implementation": "python_backend/core_modules/geodesic_tensor_engine.py:unfold_partial",
        "tests": "tests/test_geodesic_tensor_extensions.py",
    },
    "geodesic.metric_energy_virtual_gpu": {
        "status": "implemented_tested",
        "implementation": "python_backend/core_modules/geodesic_tensor_engine.py",
        "tests": "tests/test_geodesic_tensor_extensions.py",
    },
    "hybrid.profiled_router": {
        "status": "implemented_tested",
        "implementation": "tensor/hybrid.py:ProfiledHybridRouter",
        "tests": "tests/test_tensor_hybrid_router.py",
    },
    "inference.folded_linear_pilot": {
        "status": "implemented_tested",
        "implementation": "tensor/folded_inference.py",
        "tests": "tests/test_folded_inference.py",
        "claim_boundary": "Exact reversible custody + measured inference; no physical compression ratio without physical evidence.",
    },
    "vqc.exact_and_quantum_tensor_loaders": {
        "status": "implemented_tested",
        "implementation": "tensor/kellogg_bridge.py",
        "tests": "tests/test_tensor_package.py",
    },
    "mining.advisor_boundary": {
        "status": "implemented_tested",
        "implementation": "hyba/hybrid/tensor_advisor.py",
        "tests": "tests/test_three_layer_runtime.py, tests/test_tensor_advisor_safety.py",
    },
    "compat.gpu_tensor_shim": {
        "status": "implemented_tested",
        "implementation": "gpu/tensor.py",
        "tests": "tests/test_tensor_gpu_compat.py",
    },
    "packaging.tensor_distribution": {
        "status": "implemented_tested",
        "implementation": "pyproject.toml",
        "tests": "tests/test_package_layout.py",
    },
    "grover.hendrix_entry_points": {
        "status": "not_implemented",
        "implementation": None,
        "evidence_needed": "Turing Hendrix/Grover exists; wire only for a concrete Tensor production consumer.",
    },
    "vqc_manifold_bridge": {
        "status": "not_implemented",
        "implementation": None,
        "evidence_needed": "ASI/TOE manifold bridges are advisory, not Tensor execution entry points.",
    },
    "folded.dtype_custody": {
        "status": "implemented_tested",
        "implementation": "aethel/phi_fold.py (NumericFoldState.dtype; bit-exact float32/64, complex64/128, int/uint)",
        "tests": "tests/test_phi_fold_dtype_custody.py",
    },
    "folded.region_decode": {
        "status": "implemented_tested",
        "implementation": "aethel/phi_fold.py unfold_region + region_flat_boundaries; geodesic_tensor_engine unfold_values_at/unfold_region; tensor/dependency.py cones",
        "tests": "tests/test_region_decode.py, tests/test_dependency_cone.py",
    },
    "folded.persistent_store": {
        "status": "implemented_tested",
        "implementation": "aethel/fold_store.py (versioned blocks, lineage, content hash, splice_region/commit_region, checkpoint/restore, evict/regenerate, device-loss invalidation)",
        "tests": "tests/test_fold_store.py",
    },
    "folded.operator_catalogue": {
        "status": "implemented_tested",
        "implementation": "tensor/folded.py (add/hadamard/fma/scale lifted with zero decoded bytes; matmul/kron committed row-block contraction; transpose/reduce_sum declared-materializing; evaluate_operator promotion evidence)",
        "tests": "tests/test_folded_operators.py, tests/test_committed_execution.py",
        "claim_boundary": "Lifted residency claims are measured per-op; declared-materializing ops report decoded bytes honestly on the receipt. Committed matmul reassociates (~1e-16) — declared bit_identical=False; kron remains bit-identical.",
    },
    "folded.committed_execution": {
        "status": "implemented_tested",
        "implementation": "tensor/folded.py committed row-block contraction (region-decoded operands, output spliced by declared coordinates exactly once); chronus/phi_gpu.py CoordinateCommit + KernelLaunchConfig.commit_to resident write-back gated on the integrity verdict; aethel/phi_memory.py commit_region",
        "tests": "tests/test_committed_execution.py",
        "claim_boundary": "Committed path still decodes the full dependency cone — the measured win is peak materialisation and exactly-once write-back, not decode volume. Failed verdicts withhold the write.",
    },
    "folded.scheduler_executor_coupling": {
        "status": "implemented_tested",
        "implementation": "chronus/phi_gpu.py (KernelTask.depends_on, ready queue, run_ready; scheduled boundary controls the launch)",
        "tests": "tests/test_phi_gpu_scheduler_executor.py",
    },
    "runtime.canonical_api": {
        "status": "implemented_tested",
        "implementation": "tensor/api.py TensorRuntime + tensor/__main__.py CLI; custody, folded/backend routing, cancellation, atomic publication",
        "tests": "tests/test_tensor_runtime.py",
    },
    "runtime.control_api_endpoints": {
        "status": "implemented_tested",
        "implementation": "chronus/mla1517_platform/python/control_api.py (guardian-preflighted POST /api/v1/tensor/execute, GET /api/v1/tensor/capabilities; ops allowlisted in al_haras_pythia._PYTHIA_ALLOWED_OPERATIONS; execute synthesizes the GET-style observation)",
        "tests": "tests/test_tensor_runtime.py, tests/test_al_haras_pythia_wiring.py (allowlist regression)",
    },
    "runtime.execution_receipts": {
        "status": "implemented_tested",
        "implementation": "tensor/receipts.py ExecutionReceipt (identity, backend/device, work, residency/transfers, timing scope, correctness; measured vs analytical bytes distinct)",
        "tests": "tests/test_tensor_receipts_benchmarks.py",
    },
    "benchmark.validated_matrix": {
        "status": "implemented_tested",
        "implementation": "tensor/benchmarks.py run_benchmarks (ops x sizes x dtypes x layouts x resident/nonresident x cold/warm; every sampled output validated)",
        "tests": "tests/test_tensor_receipts_benchmarks.py",
    },
    "consolidation.canonical_ownership": {
        "status": "implemented_tested",
        "implementation": "QuantumFoldTensorCore rename (quantum-amplitude unit); GeodesicRouter rename (virtual_igpu route planning); one-home gate",
        "tests": "tests/test_canonical_tensor_ownership.py",
    },
}


def render_markdown() -> str:
    lines = ["| Feature | Status | Implementation | Tests/Evidence |", "|---|---|---|---|"]
    for feature, row in CAPABILITY_MANIFEST.items():
        impl = row.get("implementation") or "—"
        evidence = row.get("tests") or row.get("evidence_needed") or "—"
        lines.append(f"| `{feature}` | {row['status']} | `{impl}` | {evidence} |")
    return "\n".join(lines)


__all__ = ["CAPABILITY_MANIFEST", "render_markdown"]
