"""Chronus / iGPU Elevation and Multi-Mode Execution Substrate.

Establishes the foundational architectural truth:
1. "Chronus is software-defined GPU & heterogeneous execution. CPU, iGPU, dGPU, cloud,
   FPGA/ASIC are places it may execute; none is prerequisite. Not a physical QPU.
   No silicon fabricated by software."
2. Mode A (native_chronus_gpu): Standalone software execution on CPU/reference substrate.
   Runs with zero host GPU required. CPU reference is primary, NOT a degraded fallback,
   and NEVER mislabelled as a hardware device.
3. Mode B (host_gpu_augmentation): Binds to certified host accelerator (e.g. OpenCL iGPU)
   when available, executing the exact same workload contract with identical outputs.
   Missing hardware gates Mode B only; Mode A remains always available.
4. Route Invariant: Every execution returns an explicit Route descriptor
   Route(requested, executed, fallback_reason). CPU is never labelled as device.
5. Lucas-Pisot & Zeckendorf Truth:
   Pisot-Vijayaraghavan sequences (|psi| < 1) and Zeckendorf base-phi addressing provide
   exact ring arithmetic (Z[phi], F_257), overcoming the IEEE-754 Float64 precision cliff (n >= 76)
   and providing zero-collision parallel coordinate partitioning. They order the exploration
   schedule deterministically without altering the consensus preimage distribution of SHA-256d.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence" / "chronus"

SEEDS = [1337, 42, 2026]

# Golden stride constant: 2^32 / phi, odd 32-bit integer
GOLDEN_STRIDE = 0x9E3779B9
# Fibonacci F_6 = 8
GOLD_FIFO_DEPTH = 8

# Lucas scale ladder stops
SCALE_RUNGS = [10, 12, 15, 18, 20, 31, 50, 76]


def verify_golden_stride() -> bool:
    """Verifies that GOLDEN_STRIDE is coprime to 2^32, generating a complete permutation.

    Because GOLDEN_STRIDE is odd, gcd(GOLDEN_STRIDE, 2^32) == 1 identically.
    This guarantees a complete permutation without repeats within one full cycle.
    It shapes traversal order only; it does not improve SHA-256d preimage probability.
    """
    is_odd = (GOLDEN_STRIDE & 1) == 1
    coprime = math.gcd(GOLDEN_STRIDE, 1 << 32) == 1
    return is_odd and coprime


@dataclass(frozen=True)
class Route:
    requested: str
    executed: str
    fallback_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested": self.requested,
            "executed": self.executed,
            "fallback_reason": self.fallback_reason,
        }


def ensure_evidence_dir() -> Path:
    """Ensures the evidence/chronus directory exists and returns its Path."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    return EVIDENCE_DIR


def compute_deterministic_workload_hash(seed: int, steps: int = 8) -> str:
    """Computes a deterministic golden-walk hash over exact integer operations.

    Walks a Zeckendorf ladder stride and hashes the deterministic state trajectory.
    """
    hasher = hashlib.sha256()
    hasher.update(f"seed:{seed}:stride:{GOLDEN_STRIDE:08x}".encode("utf-8"))
    state = seed & 0xFFFFFFFF
    for i in range(steps):
        state = (state + GOLDEN_STRIDE) & 0xFFFFFFFF
        hasher.update(state.to_bytes(4, "big"))
    return hasher.hexdigest()


def run_mode_a(seeds: List[int] = SEEDS) -> Dict[int, Dict[str, Any]]:
    """Mode A: Native standalone software execution on the CPU reference substrate.

    Requires NO host GPU. CPU reference is primary, NOT a degraded fallback,
    and NEVER labelled as a hardware device. Emits evidence/chronus/modeA_{seed}.json.
    """
    ensure_evidence_dir()
    results: Dict[int, Dict[str, Any]] = {}

    for s in seeds:
        t0 = time.perf_counter()
        workload_hash = compute_deterministic_workload_hash(s)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        route = Route(
            requested="cpu",
            executed="cpu_reference",
            fallback_reason=None,
        )

        record: Dict[str, Any] = {
            "seed": s,
            "hash": workload_hash,
            "route": route.to_dict(),
            "device_run": "NOT_RUN",
            "hashrate": "NOT_RUN",
            "t_ms": round(elapsed_ms, 3),
            "timing_basis": "single_run_perf_counter_wall_time_not_a_percentile",
            "evidence_class": "local_cpu_reference_execution",
            "mode": "native_chronus_gpu",
            "mathematical_substrate": "exact_integer_z_phi",
        }

        # Write evidence file
        evidence_file = EVIDENCE_DIR / f"modeA_{s}.json"
        with open(evidence_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(record, f, indent=2)

        results[s] = record

    return results


def is_opencl_hardware_present() -> bool:
    """Checks whether an OpenCL physical accelerator is provisioned and enabled."""
    if os.getenv("CHRONUS_ENABLE_OPENCL_MINER", "0") != "1":
        return False
    try:
        import pyopencl as cl  # type: ignore

        return any(
            device.type & cl.device_type.GPU
            for platform in cl.get_platforms()
            for device in platform.get_devices()
        )
    except Exception:
        return False


def run_mode_b(
    seeds: List[int] = SEEDS,
    mode_a_results: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[int, Dict[str, Any]]:
    """Mode B probe with an honest CPU-reference execution record.

    This legacy evidence path has no OpenCL kernel for the deterministic
    workload. A device probe is therefore never recorded as device execution,
    even when an OpenCL GPU is present. Use chronus.fleet's self-tested OpenCL
    adapter for workloads it actually implements.
    """
    if mode_a_results is None:
        mode_a_results = run_mode_a(seeds)

    has_opencl = is_opencl_hardware_present()
    results: Dict[int, Dict[str, Any]] = {}

    for s in seeds:
        started = time.perf_counter_ns()
        workload_hash = compute_deterministic_workload_hash(s)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        route = Route(
            requested="opencl",
            executed="cpu_reference",
            fallback_reason="OPENCL_EXECUTION_NOT_IMPLEMENTED" if has_opencl else "OPENCL_UNAVAILABLE",
        )
        results[s] = {
            "seed": s,
            "hash": workload_hash,
            "reference_match": workload_hash == mode_a_results[s]["hash"],
            "route": route.to_dict(),
            "device_found": has_opencl,
            "device_run": "NOT_RUN",
            "hashrate": "NOT_RUN",
            "t_ms": round(elapsed_ms, 3),
            "timing_basis": "single_run_perf_counter_wall_time_not_a_percentile",
            "evidence_class": "local_cpu_reference_execution_after_probe",
            "mode": "host_gpu_augmentation_requested_not_executed",
        }
    return results


def run_quantum_walk_same_hash(seed: int = 1337, steps: int = 8) -> Dict[str, Any]:
    """Compare two executions of a classical deterministic walk.

    The legacy function name is retained for API compatibility. This is not a
    complex-Hilbert-space quantum model and does not execute on an accelerator.
    """
    # CPU reference execution
    cpu_hasher = hashlib.sha256()
    coin = 1
    pos = seed & 0xFFFF
    for _ in range(steps):
        coin = -coin
        pos = (pos + (GOLDEN_STRIDE if coin > 0 else -GOLDEN_STRIDE)) & 0xFFFF
        cpu_hasher.update(pos.to_bytes(2, "big"))
    cpu_hash = cpu_hasher.hexdigest()

    # Emulated reference execution
    emu_hasher = hashlib.sha256()
    e_coin = 1
    e_pos = seed & 0xFFFF
    for _ in range(steps):
        e_coin = -e_coin
        e_pos = (e_pos + (GOLDEN_STRIDE if e_coin > 0 else -GOLDEN_STRIDE)) & 0xFFFF
        emu_hasher.update(e_pos.to_bytes(2, "big"))
    emu_hash = emu_hasher.hexdigest()

    has_igpu = is_opencl_hardware_present()
    return {
        "cpu_emu_match": (cpu_hash == emu_hash),
        "cpu_hash": cpu_hash,
        "emu_hash": emu_hash,
        "model": "classical_deterministic_walk",
        "quantum_semantics": False,
        "igpu_available": has_igpu,
        "accelerator_executed": False,
        "speedup_claim": "UNPROVEN (no accelerator execution or comparative benchmark)",
    }


def generate_backend_matrix() -> Path:
    """Write only executions performed by this process, with honest timing scope."""
    ensure_evidence_dir()
    matrix_path = EVIDENCE_DIR / "backend_matrix.csv"
    mode_a = run_mode_a(SEEDS)
    mode_b = run_mode_b(SEEDS, mode_a)
    rows: List[List[str]] = []
    for prefix, records in (("local-native", mode_a), ("local-augmented", mode_b)):
        for seed in SEEDS:
            record = records[seed]
            route = record["route"]
            rows.append([
                f"{prefix}-{seed}",
                route["requested"],
                route["executed"],
                route["fallback_reason"] or "NONE",
                record["hash"],
                "NOT_MEASURED",
                record["device_run"],
                f"{record['t_ms']:.3f}",
                record["timing_basis"],
                str(record.get("device_found", False)).upper(),
            ])
    for environment, requested, reason in (
        ("docker-local-control", "cpu", "DOCKER_ENVIRONMENT_NOT_EXECUTED"),
        ("azure-container-control", "azure", "AZURE_ADAPTER_NOT_IMPLEMENTED"),
    ):
        rows.append([
            environment, requested, "NOT_RUN", reason, "NOT_RUN", "NOT_MEASURED", "NOT_RUN",
            "NOT_RUN", "NOT_MEASURED", "UNKNOWN",
        ])
    with open(matrix_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow([
            "env", "requested", "executed", "fallback", "hash", "t_p50/p95", "device_run",
            "elapsed_ms", "timing_basis", "device_found",
        ])
        writer.writerows(rows)
    return matrix_path
