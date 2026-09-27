#!/usr/bin/env python3
"""Executable audit of the MLA1517 session requirements.

This checks that each architectural requirement has a concrete source artifact
and that unsupported claims remain prohibited. It is a release audit, not a
runtime workload and does not manufacture hardware results.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "exact_recurrence_math": ("python/mla1517/core.py", ("fib_pair", "lucas", "cassini", "zeckendorf")),
    "extended_algebra_families": ("python/extended_algebra.py", ("plastic", "supergolden", "tribonacci")),
    "scale_controls": ("python/mla1517/scale.py", ("ScaleBudget", "max_index", "authorize")),
    "progressive_four_stage_work": ("cpp/src/mla1517_progressive_miner.cpp", ("stage2_pass", "stage3_pass", "stage4_pass")),
    "11d_32_lane_12_20_contract": ("hardware/mla1517_igpu_v1.json", ("\"dimensions\": 11", "\"warp_width\": 32", "\"icosahedral_execution_nodes\": 12", "\"dodecahedral_memory_nodes\": 20")),
    "64_byte_hot_descriptor": ("cpp/include/mla1517_shm.h", ("Mla11DState", "sizeof(Mla11DState) == 64", "alignof(Mla11DState) == 64")),
    "fixed_point_zcore": ("rtl/mla1517_zcore.sv", ("$readmemh", "d6_binet_projection_o", "nonce_in_range")),
    "rom_generator": ("rtl/scripts/zcore_rom_generator.py", ("fixed", "zeckendorf", "ROM")),
    "sieve_ballot_crossbar": ("rtl/mla1517_sieve_crossbar.sv", ("warp_vote_o", "$countones", "MEMORY_NODES")),
    "cassini_dsp_stage": ("rtl/mla1517_cassini_dsp.sv", ("determinant_comb", "cassini_valid_o", "use_dsp")),
    "c11_mmio_driver": ("host/mla1517_mmio.c", ("mla1517_stage_lane_mask", "mla1517_request_supervisor_commit", "mla1517_supervisor_commit_ack")),
    "zero_copy_aethel_ring": ("host/mla1517_shm.c", ("atomic_store_explicit", "mla1517_shm_push", "MLA1517_State")),
    "primedb_20_vertex_storage": ("host/primedb_storage.c", ("PRIMEDB_VERTEX_COUNT", "d7_prime_addr", "cassini_valid")),
    "native_query_callback": ("python/mla1517/primedb_engine.py", ("primedb_storage_query_d5", "CFUNCTYPE")),
    "primedb_durability": ("host/primedb_storage.c", ("msync", "fsync", "head_cursor")),
    "telemetry_seqlock": ("host/telemetry_shm.c", ("memory_order_release", "seq")),
    "telemetry_dashboard": ("python/telemetry_daemon.py", ("/ws/topology", "FastAPI", "vertex")),
    "stratum_fail_closed": ("python/manifold_pool_coordinator.py", ("negotiated", "mining.submit")),
    "stratum_endpoints": ("python/manifold_pool_coordinator.py", ("stratum.braiins.com", "btc.viabtc.io")),
    "docker_ipc_deployment": ("docker-compose.yml", ("ipc:", "prime-db", "salamander")),
    "gpu_host_controls": ("python/mla1517/connectors.py", ("host_gpu_overlay", "allow_host_gpu", "require_host_gpu")),
    "salamander_corrected_controls": ("python/salamander_control.py", ("MIN_LANES", "FAULT_TAU_MS", "READMIT_PASSES", "orphan", "commit_lane_mask")),
    "measured_agentic_stack": ("python/agentic_mining.py", ("MeasuredForwardIndex", "CommissionedSCM", "ObservedCounterfactuals", "SupportViolation")),
    "no_synthetic_agent_runtime": ("python/agentic_mining.py", ("no simulator", "generated trajectory", "synthetic counterfactual")),
    "no_unlimited_claims": ("behavior.json", ('"unlimited_speed_or_capacity_claim": false',)),
    "shared_primedb_cursor_abi": ("host/primedb_storage.c", ("/dev/shm/primedb_cursors", "recover_head_cursor", "primedb_cursors_t")),
    "vertex_growth_no_drop": ("host/primedb_storage.c", ("grow_vertex", "MLA1517_PRIME_DB_MAX_BYTES", "ftruncate")),
    "ring_overflow_spill": ("host/mla1517_producer_daemon.c", ("MLA1517_PRIME_DB_OVERFLOW", "add_ring_overflow", "add_catastrophic_overflow")),
    "telemetry_abi_gate": ("scripts/abi_check.py", ("mla1517_telemetry_size", "mla1517_telemetry_offset")),
    "query_cassini_recheck": ("host/primedb_storage.c", ("mla1517_telemetry_add_query_fault", "cassini_valid(state)")),
    "docker_shared_shm_gate": ("scripts/docker_shm_smoke.py", ("target: /dev/shm", "type: tmpfs")),
    "salamander_imbalance_failover": ("python/salamander_engine.py", ("43.8", "_trigger_stratum_failover", "primedb_cursors")),
    "cassini_fault_producer": ("host/mla1517_producer_daemon.c", ("mla1517_telemetry_add_fault", "d10_cassini")),
    "measured_transition_population": ("python/agentic_mining.py", ("record_transition", "record_observed_result", "self.ledger.record")),
    "exact_integer_rings": ("python/mla1517/rings.py", ("class ZPhi", "class ZRho", "class ZPsi", "class ZTau", "def norm")),
    "canonical_exact_quantum_engine": ("python/mla1517/quantum.py", ("ExactStateVector", "tensor", "evolve_hamiltonian", "MemoryError")),
    "canonical_accelerator_boundary": ("python/mla1517/accelerator.py", ("CanonicalAccelerator", "AcceleratorUnavailable", "exact_cpu_reference")),
    "cpp_exact_hot_path": ("cpp/src/mla1517_progressive_miner.cpp", ("padovan", "prime_address", "state.d6_binet_view = static_cast<std::uint32_t>(lucas(index))", "state.d7_prime_address = prime_address(nonce)")),
    "no_float_exact_math_gate": ("scripts/no_float_in_math_core.py", ("ast.walk", "no_float_runtime")),
    "exact_long4_quantum_kernel": ("kernels/exact_quantum_kernel.cl", ("typedef long4 ExactAmp", "exact_hadamard_lucas_pisot_scale", "atomic_or")),
    "exact_tensor_primedb_persistence": ("python/mla1517/store.py", ("put_exact_tensor", "get_exact_tensor", "byte_length", "sha256")),
    "exact_lucas_pisot_ladder": ("python/mla1517/scaling.py", ("LUCAS_PISOT_LADDER = tuple(FULL_LADDER)", "OpenCLLadderExecutor", "GPUExecutionUnavailable")),
    "opencl_exact_kernel": ("kernels/mla1517_lucas_pisot_scale.cl", ("mla1517_lucas_pisot_scale", "ulong", "padovan")),
    "strict_hardware_ci": ("scripts/strict_hardware_gate.py", ("MLA1517_STRICT_HARDWARE_CI", "OpenCLLadderExecutor", "PRIME-DB invariant round trip")),
    "gpu_passthrough_manifest": ("docker-compose.gpu.yml", ("deploy:", "capabilities: [gpu]", "/dev/dri")),
    "live_lucas_scaling_harness": ("scripts/measure_lucas_scaling.py", ("OpenCLLadderExecutor", "MLA1517_ENABLE_LIVE_SUBMIT", "response is True", "effective_hashrate")),
    "no_simulated_scaling": ("scripts/measure_lucas_scaling.py", ("no default mapping exists", "time.perf_counter_ns", "accepted == 0")),
    "release_gate": ("scripts/release_gate.py", ("measured_only", "no_dev_mem_implicit_open")),
}

BOUNDARIES = {
    "physical_fpga_or_asic_execution": "requires deployed target hardware and synthesis/programming",
    "rust_runtime": "not selected for the production path; C11/C++17/Python/SystemVerilog are the chosen split",
    "external_pool_share_validity": "requires a negotiated adapter and external pool verification",
    "10_ehs_or_20000_gpu_equivalence": "not a mathematical consequence; must be measured on real hardware/workload",
    "unlimited_speed_or_capacity": "prohibited as a product claim",
}


def main() -> int:
    results = {}
    failures = []
    for name, (relative, needles) in CHECKS.items():
        path = ROOT / relative
        text = path.read_text(errors="replace") if path.exists() else ""
        missing = [needle for needle in needles if needle not in text]
        results[name] = {"status": "PASS" if path.exists() and not missing else "FAIL", "artifact": relative, "missing": missing}
        if results[name]["status"] == "FAIL":
            failures.append(name)
    report = {"status": "PASS" if not failures else "FAIL", "checks": results, "physical_boundaries": BOUNDARIES}
    out = ROOT / "results/requirements_audit.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checks": len(results), "failures": failures, "report": str(out)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
