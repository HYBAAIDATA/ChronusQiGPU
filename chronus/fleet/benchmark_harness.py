"""Benchmark Harness & GPU Reference Comparison Panel for Chronus Native Quantum Execution.

Implements Section 2 of the Native Quantum Fleet Elevation Mandate:
- Host environment & runtime capture (OS/kernel, CPU topology, RAM, BLAS/NumPy/Python runtime,
  thread caps, import origins, and artifact SHA-256 hashes).
- Explicit separation of source-checkout/namespace-bootstrap studies from clean-venv installed acceptance.
- Separation of cold import/startup latency from warm execution latency.
- Separation of kernel-only timings from end-to-end profiles (allocation, transfer, execution,
  independent verification, pre-mutation audit, and custody persistence).
- Seeded randomized workload order across configurable observations (>= 100 observations per case
  for comparative study claims), retaining all raw samples, explicit quantile methods
  (Weibull/linear for p50, p90, p95, p99, max), uncertainty (stddev, 95% CI half-width),
  and failed/refused counts.
- Subprocess verification of `python -O` (`__debug__ == False`) parity to prove required runtime
  checks are never stripped by bytecode optimization.
- Comparative panel against documented leading-GPU reference specifications
  (Rubin R100, HGX B300, AMD Instinct MI355X, AMD Instinct MI325X, Hopper H100) with
  unavailable physical competitor endpoints explicitly marked `NOT_RUN` (`native_blocker=False`).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from ..gpu_reference import GPU_REFERENCE_2026, get_gpu_spec
from .workload_contracts import (
    WorkloadFixtureContract,
    canonical_workload_fixtures,
    ensure_canonical_import_roots,
)


BENCHMARK_HARNESS_SCHEMA = "chronus.benchmark-harness/v1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_ram_bytes() -> int | None:
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys)
        elif hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if isinstance(pages, int) and isinstance(page_size, int) and pages > 0 and page_size > 0:
                return int(pages * page_size)
    except Exception:
        pass
    return None


def _detect_blas_info() -> dict[str, Any]:
    try:
        cfg = getattr(np, "__config__", None)
        if cfg is not None and hasattr(cfg, "show"):
            info = cfg.show(mode="dicts")
            if isinstance(info, Mapping):
                blas = info.get("Build Dependencies", {}).get("blas", {})
                return {
                    "blas_name": blas.get("name", "unknown"),
                    "blas_version": blas.get("version", "unknown"),
                    "simd_extensions": info.get("SIMD Extensions", {}).get("found", []),
                }
    except Exception:
        pass
    return {"blas_name": "numpy-builtin", "blas_version": np.__version__, "simd_extensions": []}


@dataclass(frozen=True, kw_only=True)
class HostEnvironmentProfile:
    """Recorded host, OS, CPU, RAM, BLAS, thread-cap, and import-origin baseline."""

    os_system: str
    os_release: str
    os_version: str
    machine: str
    processor: str
    logical_cpus: int
    total_ram_bytes: int | None
    python_version: str
    python_executable: str
    python_optimize_flag: int
    numpy_version: str
    blas_info: dict[str, Any]
    thread_env_caps: dict[str, str | None]
    git_head_sha: str | None
    import_origins: dict[str, str]
    artifact_sha256: dict[str, str]
    acceptance_classification: str  # "installed_acceptance" | "source_component_study"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_host_environment() -> HostEnvironmentProfile:
    """Capture host topology, runtime versions, import origins, and artifact digests."""
    bootstrap = ensure_canonical_import_roots()
    repo_root = Path(bootstrap["repo_root"]).resolve()

    import chronus
    import kellogg
    import turing_universal_quantum_computer

    origins = {
        "chronus": str(Path(getattr(chronus, "__file__", "")).resolve()),
        "kellogg": str(Path(getattr(kellogg, "__file__", "")).resolve()),
        "turing_universal_quantum_computer": str(
            Path(getattr(turing_universal_quantum_computer, "__file__", "")).resolve()
        ),
    }

    in_checkout = any(
        Path(p).is_relative_to(repo_root) for p in origins.values() if p
    )
    classification = (
        "source_component_study"
        if (in_checkout or bootstrap["bootstrapped_paths"])
        else "installed_acceptance"
    )

    tracked_files = (
        repo_root / "chronus" / "gpu_reference.py",
        repo_root / "chronus" / "fleet" / "workload_contracts.py",
        repo_root / "chronus" / "fleet" / "capacity.py",
        repo_root / "chronus" / "fleet" / "scheduler.py",
        repo_root / "chronus" / "fleet" / "custody.py",
        repo_root / "docs" / "NATIVE_QUANTUM_CONTRACT.md",
    )
    artifact_hashes = {
        str(p.relative_to(repo_root)).replace("\\", "/"): _sha256_file(p)
        for p in tracked_files
        if p.is_file()
    }

    git_sha: str | None = None
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            git_sha = proc.stdout.strip()
    except Exception:
        git_sha = None

    thread_vars = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
    thread_caps = {k: os.environ.get(k) for k in thread_vars}

    return HostEnvironmentProfile(
        os_system=platform.system(),
        os_release=platform.release(),
        os_version=platform.version(),
        machine=platform.machine(),
        processor=platform.processor(),
        logical_cpus=os.cpu_count() or 1,
        total_ram_bytes=_detect_ram_bytes(),
        python_version=sys.version.split()[0],
        python_executable=sys.executable,
        python_optimize_flag=int(sys.flags.optimize),
        numpy_version=np.__version__,
        blas_info=_detect_blas_info(),
        thread_env_caps=thread_caps,
        git_head_sha=git_sha,
        import_origins=origins,
        artifact_sha256=artifact_hashes,
        acceptance_classification=classification,
    )


@dataclass(frozen=True, kw_only=True)
class QuantileSummary:
    """Statistical summary with explicit quantile method, tail latencies, and uncertainty."""

    count: int
    method: str  # "weibull" | "linear"
    min_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    mean_ms: float
    stddev_ms: float
    ci95_halfwidth_ms: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_quantiles(samples: Sequence[float], *, method: str = "weibull") -> QuantileSummary:
    """Compute quantiles (p50, p90, p95, p99, max) and 95% confidence interval half-width."""
    if not samples:
        raise ValueError("compute_quantiles requires at least one sample")
    if method not in {"weibull", "linear"}:
        raise ValueError(f"Unsupported quantile method: {method!r}")
    arr = np.sort(np.asarray(samples, dtype=np.float64))
    if not np.all(np.isfinite(arr)):
        raise ValueError("All timing samples must be finite")
    n = int(arr.size)
    p50, p90, p95, p99 = (
        float(np.quantile(arr, q, method=method)) for q in (0.50, 0.90, 0.95, 0.99)
    )
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    ci95 = 1.96 * (std / math.sqrt(n)) if n > 1 else 0.0
    return QuantileSummary(
        count=n,
        method=method,
        min_ms=float(arr[0]),
        p50_ms=p50,
        p90_ms=p90,
        p95_ms=p95,
        p99_ms=p99,
        max_ms=float(arr[-1]),
        mean_ms=mean,
        stddev_ms=std,
        ci95_halfwidth_ms=ci95,
    )


@dataclass(frozen=True, kw_only=True)
class BenchmarkCaseResult:
    """Benchmark telemetry for one workload case separating cold start, kernel, and end-to-end."""

    case_id: str
    fixture_class: str
    observations: int
    cold_start_ms: float
    kernel_only_quantiles: QuantileSummary
    end_to_end_quantiles: QuantileSummary
    raw_kernel_samples_ms: tuple[float, ...]
    raw_end_to_end_samples_ms: tuple[float, ...]
    succeeded_count: int
    refused_count: int
    failed_count: int
    all_verified: bool
    comparative_study_eligible: bool  # True only when observations >= 100

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kernel_only_quantiles"] = self.kernel_only_quantiles.as_dict()
        data["end_to_end_quantiles"] = self.end_to_end_quantiles.as_dict()
        return data


def _fast_benchmark_cases() -> dict[str, tuple[str, str, Callable[[], dict[str, Any]], Callable[[dict[str, Any]], bool]]]:
    """High-frequency unit kernels for >=100-observation statistical latency distribution studies.

    Each case executes real mathematical/custody work and separates:
    - kernel execution time
    - end-to-end time (allocation + kernel + independent verification + audit digest + persistence)
    """
    from chronus.family_algebra import FamilyCertificate
    from chronus.gpu_capabilities import BufferIntegrityGate, ChronusTensorPipeline
    from chronus.igpu.exact_fold import ExactFoldState
    from chronus.igpu.structured_solver import StructuredHamiltonian
    from kellogg.exact_tensor import ExactTOETensor
    from turing_universal_quantum_computer import cassini_check, lucas, zeckendorf_decode, zeckendorf_encode
    from turing_universal_quantum_computer.backends.algebraic import ExactFieldBackend
    from turing_universal_quantum_computer.backends.base import Operation, Program
    from turing_universal_quantum_computer.quantum_library import QuantumLibrary

    def _case_a() -> dict[str, Any]:
        vals = {n: int(lucas(n)) for n in (10, 15, 20, 31)}
        cas = all(bool(cassini_check(n)) for n in (10, 15, 20, 31))
        z_ok = zeckendorf_decode(zeckendorf_encode(1364)) == 1364
        cert = FamilyCertificate.create([10, 15])
        folded = ExactFoldState.fold([13, 21, 34, 55])
        return {
            "outcome": "success",
            "l15": vals[15],
            "cassini": cas,
            "zeck": z_ok,
            "cert": cert,
            "folded": folded,
        }

    def _ver_a(ev: dict[str, Any]) -> bool:
        return bool(
            ev["l15"] == 1364
            and ev["cassini"]
            and ev["zeck"]
            and FamilyCertificate.verify(ev["cert"])
            and list(ev["folded"].unfold()) == [13, 21, 34, 55]
        )

    def _case_a_refusal() -> dict[str, Any]:
        ops = tuple(Operation("h", (q,)) for q in range(16)) + tuple(Operation("t", (q,)) for q in range(16))
        prog = Program(16, ops)
        adm = ExactFieldBackend(max_amplitudes=4096).admit(prog)
        return {"outcome": "refusal" if not adm.admitted else "success", "admitted": adm.admitted, "reason": adm.reason}

    def _ver_a_refusal(ev: dict[str, Any]) -> bool:
        return bool(ev["outcome"] == "refusal" and ev["admitted"] is False and ev["reason"])

    amps8 = [1.0 / math.sqrt(8.0)] * 8
    phi_val = (1.0 + math.sqrt(5.0)) / 2.0
    vec8 = np.array(
        [complex(1.0 / math.sqrt(8.0), 0.0) * np.exp(1j * k * np.pi / 4.0) for k in range(8)],
        dtype=np.complex128,
    )

    def _case_b() -> dict[str, Any]:
        ham = StructuredHamiltonian(amps8, phi_val)
        mv = ham.matvec(vec8)
        g = QuantumLibrary.grover(3, marked=5)
        return {"outcome": "success", "mv": mv, "grover": g}

    def _ver_b(ev: dict[str, Any]) -> bool:
        return bool(
            ev["mv"].dtype == np.complex128
            and np.all(np.isfinite(ev["mv"]))
            and ev["grover"].verify_exactness().exact
        )

    exact_toe = ExactTOETensor(num_qubits=3)
    tensor_pipe = ChronusTensorPipeline()
    ghz4 = np.zeros(16, dtype=np.float64)
    ghz4[0] = 1.0 / math.sqrt(2.0)
    ghz4[15] = 1.0 / math.sqrt(2.0)

    def _case_c() -> dict[str, Any]:
        st, dig = exact_toe.encode([1, 2, 3, 5, 8, 13, 21, 34])
        mps = tensor_pipe.decompose(ghz4, "mps", max_rank=4)
        return {"outcome": "success", "state": st, "digest": dig, "mps": mps}

    def _ver_c(ev: dict[str, Any]) -> bool:
        inv = tensor_pipe.verify_network(ev["mps"], require_normalized=True)
        return bool(ev["state"].normalized_exact() and inv.passed)

    def _case_d() -> dict[str, Any]:
        gate = BufferIntegrityGate(authentication_key=b"chronus-bench-d-hmac-key")
        payload = np.arange(32, dtype=np.float64)
        att = gate.attest(payload, device_fingerprint="native-chronus-resident")
        return {"outcome": "success", "gate": gate, "payload": payload, "att": att}

    def _ver_d(ev: dict[str, Any]) -> bool:
        return bool(ev["gate"].verify(ev["payload"], ev["att"]))

    return {
        "case_a_exact_algebra": ("A", "success", _case_a, _ver_a),
        "case_a_domain_refusal": ("A", "refusal", _case_a_refusal, _ver_a_refusal),
        "case_b_quantum_numerical": ("B", "success", _case_b, _ver_b),
        "case_c_kellogg_tensor": ("C", "success", _case_c, _ver_c),
        "case_d_custody_attestation": ("D", "success", _case_d, _ver_d),
    }


def run_benchmark_suite(
    *,
    observations_per_case: int = 100,
    seed: int = 20261024,
    quantile_method: str = "weibull",
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the seeded randomized benchmark suite separating cold start, kernel, and end-to-end."""
    if observations_per_case < 1:
        raise ValueError("observations_per_case must be >= 1")

    env_profile = capture_host_environment()
    cases = _fast_benchmark_cases()

    with tempfile.TemporaryDirectory(prefix="chronus_bench_") as tmp_str:
        base_dir = Path(work_dir) if work_dir is not None else Path(tmp_str)
        base_dir.mkdir(parents=True, exist_ok=True)
        audit_log_path = base_dir / "benchmark_durable_audit.jsonl"

        # 1. Cold start pass (1 observation per case before warm schedule)
        cold_start_ms: dict[str, float] = {}
        for cid, (_cls, _exp, fn, ver) in cases.items():
            t0 = time.perf_counter()
            ev = fn()
            _ = ver(ev)
            cold_start_ms[cid] = (time.perf_counter() - t0) * 1000.0

        # 2. Build seeded randomized schedule across all cases * observations_per_case
        schedule: list[str] = []
        for cid in cases:
            schedule.extend([cid] * observations_per_case)
        rng = random.Random(seed)
        rng.shuffle(schedule)

        kernel_samples: dict[str, list[float]] = {cid: [] for cid in cases}
        e2e_samples: dict[str, list[float]] = {cid: [] for cid in cases}
        succeeded: dict[str, int] = {cid: 0 for cid in cases}
        refused: dict[str, int] = {cid: 0 for cid in cases}
        failed: dict[str, int] = {cid: 0 for cid in cases}
        verified_flags: dict[str, bool] = {cid: True for cid in cases}

        with audit_log_path.open("a", encoding="utf-8") as audit_fp:
            for step_idx, cid in enumerate(schedule):
                f_cls, expected_outcome, fn, ver = cases[cid]
                t_e2e_start = time.perf_counter()

                # Pre-execution allocation & audit record preparation
                pre_audit = {
                    "step": step_idx,
                    "case_id": cid,
                    "fixture_class": f_cls,
                }

                # Kernel-only execution timing
                t_kern_start = time.perf_counter()
                ev = fn()
                t_kern_ms = (time.perf_counter() - t_kern_start) * 1000.0

                # Independent verification + persistence into durable audit log
                ok = bool(ver(ev))
                actual_outcome = str(ev.get("outcome", "unknown"))
                if actual_outcome != expected_outcome:
                    ok = False

                record_bytes = json.dumps(
                    {
                        **pre_audit,
                        "outcome": actual_outcome,
                        "verified": ok,
                        "kernel_ms": round(t_kern_ms, 6),
                    },
                    sort_keys=True,
                )
                audit_fp.write(record_bytes + "\n")
                t_e2e_ms = (time.perf_counter() - t_e2e_start) * 1000.0

                kernel_samples[cid].append(t_kern_ms)
                e2e_samples[cid].append(t_e2e_ms)
                if not ok:
                    failed[cid] += 1
                    verified_flags[cid] = False
                elif actual_outcome == "refusal":
                    refused[cid] += 1
                else:
                    succeeded[cid] += 1

            audit_fp.flush()

        case_results: dict[str, dict[str, Any]] = {}
        for cid, (f_cls, _exp, _fn, _ver) in cases.items():
            res = BenchmarkCaseResult(
                case_id=cid,
                fixture_class=f_cls,
                observations=observations_per_case,
                cold_start_ms=cold_start_ms[cid],
                kernel_only_quantiles=compute_quantiles(kernel_samples[cid], method=quantile_method),
                end_to_end_quantiles=compute_quantiles(e2e_samples[cid], method=quantile_method),
                raw_kernel_samples_ms=tuple(kernel_samples[cid]),
                raw_end_to_end_samples_ms=tuple(e2e_samples[cid]),
                succeeded_count=succeeded[cid],
                refused_count=refused[cid],
                failed_count=failed[cid],
                all_verified=verified_flags[cid],
                comparative_study_eligible=(observations_per_case >= 100),
            )
            case_results[cid] = res.as_dict()

        # Also run one full pass of the heavy canonical fixtures (Classes A–E including E cold restart)
        full_fixture_suite = {}
        for idx, (fid, contract) in enumerate(canonical_workload_fixtures().items()):
            out = contract.run(base_dir / "fx" / f"f{idx}")
            full_fixture_suite[fid] = {
                "fixture_class": out.fixture_class,
                "expected_outcome": out.expected_outcome,
                "actual_outcome": out.actual_outcome,
                "verified": out.verified,
                "wall_ms": out.wall_ms,
                "evidence_digest": out.evidence_digest,
            }

    return {
        "schema": BENCHMARK_HARNESS_SCHEMA,
        "seed": seed,
        "observations_per_case": observations_per_case,
        "quantile_method": quantile_method,
        "comparative_study_qualified": observations_per_case >= 100,
        "host_environment": env_profile.as_dict(),
        "cases": case_results,
        "canonical_fixtures_summary": full_fixture_suite,
        "gpu_reference_comparison": build_gpu_reference_comparison_panel(),
    }


def verify_optimized_python_parity(timeout_s: float = 90.0) -> dict[str, Any]:
    """Run canonical verification checks under `python -O` (`__debug__ == False`).

    Proves that security, admission, exactness, and custody checks do not rely on
    `assert` statements that disappear under bytecode optimization.
    """
    code = (
        "import json, sys; "
        "from chronus.fleet.workload_contracts import canonical_workload_fixtures; "
        "fx = canonical_workload_fixtures(); "
        "r_a = fx['fixture_a_exact_algebraic_quantum'].run(); "
        "r_ref = fx['fixture_a_exact_domain_refusal'].run(); "
        "print(json.dumps({"
        "'optimize_flag': int(sys.flags.optimize), "
        "'debug_enabled': bool(__debug__), "
        "'fixture_a_verified': r_a.verified, "
        "'fixture_a_refusal_verified': r_ref.verified, "
        "'refusal_outcome': r_ref.actual_outcome"
        "}))"
    )
    proc = subprocess.run(
        [sys.executable, "-O", "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "passed": False,
            "returncode": proc.returncode,
            "stderr": proc.stderr.strip(),
        }
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    passed = bool(
        payload.get("optimize_flag") == 1
        and payload.get("debug_enabled") is False
        and payload.get("fixture_a_verified") is True
        and payload.get("fixture_a_refusal_verified") is True
        and payload.get("refusal_outcome") == "refusal"
    )
    return {
        "passed": passed,
        "returncode": 0,
        "sub_payload": payload,
    }


def build_gpu_reference_comparison_panel() -> dict[str, Any]:
    """Build the comparative reference panel against documented leading GPUs.

    Separates:
    - sparse vs. dense
    - vector vs. matrix
    - native vs. emulated precision
    - per-GPU vs. node vs. rack
    - kernel vs. end-to-end
    Marks unavailable physical competitor endpoints as `NOT_RUN` (`native_blocker=False`).
    """
    panel_entries: list[dict[str, Any]] = []
    for key in GPU_REFERENCE_2026:
        spec = get_gpu_spec(key)
        panel_entries.append(
            {
                "key": key,
                "vendor": spec.manufacturer,
                "product": spec.name,
                "memory_type": spec.memory_type,
                "HBM_capacity_GB": spec.memory_capacity_gb,
                "HBM_bandwidth_TBps": spec.memory_bandwidth_tbs,
                "TDP_W": spec.tdp_watts,
                "precision_separation": {
                    "fp32_vector_tflops_dense": spec.fp32_tflops,
                    "fp16_bf16_tensor_tflops": spec.fp16_tflops,
                    "fp8_tensor_tflops": spec.fp8_tflops,
                    "fp4_tensor_pflops_sparse": spec.fp4_pflops,
                    "exact_algebraic_ring_native": False,
                },
                "scale_scope": "per_gpu_module_datasheet",
                "live_competitor_execution_status": "NOT_RUN",
                "native_blocker": False,
                "fictional_gpu_equivalence_claimed": False,
                "source_refs": list(spec.source_refs),
            }
        )
    return {
        "schema": "chronus.gpu-reference-comparison-panel/v1",
        "native_chronus_lane": {
            "logical_device": "ONE_iGPU",
            "physical_gpu_required": False,
            "exact_algebraic_ring_native": True,
            "supported_exact_domains": [
                "Z[phi] Lucas/Cassini/Zeckendorf",
                "Q(sqrt(2)) + i*Q(sqrt(2)) Clifford+T",
                "F_2^{2n} Gottesman-Knill symplectic",
            ],
            "numerical_planes": ["fp64", "complex128", "bf16_budgeted"],
            "timing_scope": "measured_host_kernel_and_end_to_end",
            "fictional_tflops_or_hbm_claimed": False,
        },
        "vendor_reference_devices": panel_entries,
    }


__all__ = [
    "BENCHMARK_HARNESS_SCHEMA",
    "BenchmarkCaseResult",
    "HostEnvironmentProfile",
    "QuantileSummary",
    "build_gpu_reference_comparison_panel",
    "capture_host_environment",
    "compute_quantiles",
    "run_benchmark_suite",
    "verify_optimized_python_parity",
]
