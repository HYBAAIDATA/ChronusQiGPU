#!/usr/bin/env python3
"""Capture reproducible, evidence-first Chronus iGPU measurements.

This command runs the production Chronus tensor runtime.  It never substitutes
CPU execution for a requested GPU, never invents unavailable sensor values, and
labels package-level RAPL data as a proxy rather than iGPU-only power.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import time
from typing import Any, Iterable

import numpy as np

SCHEMA = "chronus.igpu-evidence.v1"
UNAVAILABLE = "Unavailable"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _array_digest(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    metadata = json.dumps(
        {"dtype": contiguous.dtype.str, "shape": list(contiguous.shape)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _sha256_bytes(metadata + memoryview(contiguous).cast("B"))


def _read_float(path: Path, scale: float = 1.0) -> float | None:
    try:
        value = float(path.read_text(encoding="utf-8").strip()) / scale
    except (OSError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _sensor_rows(sys_root: Path = Path("/sys")) -> list[dict[str, Any]]:
    """Read only GPU hwmon values physically exposed by the host."""
    rows: list[dict[str, Any]] = []
    pattern = sys_root / "class" / "drm"
    for hwmon in sorted(pattern.glob("card*/device/hwmon/hwmon*")):
        names = list(hwmon.glob("temp*_input"))
        powers = list(hwmon.glob("power*_average"))
        row: dict[str, Any] = {
            "source": str(hwmon),
            "scope": "gpu_hwmon",
            "temperature_c": UNAVAILABLE,
            "power_w": UNAVAILABLE,
        }
        temperatures = [value for path in names if (value := _read_float(path, 1000.0)) is not None]
        watts = [value for path in powers if (value := _read_float(path, 1_000_000.0)) is not None]
        if temperatures:
            row["temperature_c"] = max(temperatures)
        if watts:
            row["power_w"] = sum(watts)
        rows.append(row)
    return rows


def _rapl_snapshot(sys_root: Path = Path("/sys")) -> dict[str, dict[str, Any]]:
    """Read Intel RAPL energy domains; these are package proxies, not GPU power."""
    out: dict[str, dict[str, Any]] = {}
    base = sys_root / "class" / "powercap"
    for energy_path in sorted(base.glob("intel-rapl*/energy_uj")):
        energy = _read_float(energy_path)
        if energy is None:
            continue
        domain = energy_path.parent
        try:
            name = (domain / "name").read_text(encoding="utf-8").strip()
        except OSError:
            name = domain.name
        out[str(domain)] = {
            "name": name,
            "energy_uj": energy,
            "max_energy_range_uj": _read_float(domain / "max_energy_range_uj"),
        }
    return out


def _rapl_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    elapsed_s: float,
) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(set(before) & set(after)):
        first, last = before[key], after[key]
        delta = float(last["energy_uj"]) - float(first["energy_uj"])
        maximum = first.get("max_energy_range_uj")
        if delta < 0 and isinstance(maximum, (int, float)) and maximum > 0:
            delta += float(maximum)
        if delta < 0:
            continue
        joules = delta / 1_000_000.0
        rows.append(
            {
                "source": key,
                "domain": first["name"],
                "scope": "package_proxy",
                "energy_j": joules,
                "average_power_w": joules / elapsed_s if elapsed_s > 0 else UNAVAILABLE,
            }
        )
    return rows


def roofline_record(
    arithmetic_intensity_flops_per_byte: float,
    measured_gflops: float,
    *,
    peak_gflops: float | None,
    peak_bandwidth_gbps: float | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "arithmetic_intensity_flops_per_byte": arithmetic_intensity_flops_per_byte,
        "measured_gflops": measured_gflops,
        "peak_compute_gflops": peak_gflops if peak_gflops is not None else UNAVAILABLE,
        "peak_bandwidth_gbps": (
            peak_bandwidth_gbps if peak_bandwidth_gbps is not None else UNAVAILABLE
        ),
        "ridge_point_flops_per_byte": UNAVAILABLE,
        "attainable_gflops": UNAVAILABLE,
        "classification": UNAVAILABLE,
    }
    if not peak_gflops or not peak_bandwidth_gbps:
        return record
    ridge = peak_gflops / peak_bandwidth_gbps
    bandwidth_ceiling = arithmetic_intensity_flops_per_byte * peak_bandwidth_gbps
    record["ridge_point_flops_per_byte"] = ridge
    record["attainable_gflops"] = min(peak_gflops, bandwidth_ceiling)
    record["classification"] = (
        "memory_bound" if arithmetic_intensity_flops_per_byte < ridge else "compute_bound"
    )
    return record


def _topology() -> dict[str, Any]:
    try:
        import pyopencl as cl
        from chronus.gpu_capabilities import probe_opencl_topology
    except Exception as exc:
        return {"devices": [], "error": f"{type(exc).__name__}: {exc}"}
    devices = []
    try:
        mask = int(cl.device_type.GPU) | int(cl.device_type.ACCELERATOR)
        for platform in cl.get_platforms():
            for device in platform.get_devices():
                if int(getattr(device, "type", 0)) & mask:
                    devices.append(
                        probe_opencl_topology(
                            device, platform_name=str(getattr(platform, "name", ""))
                        ).as_dict()
                    )
    except Exception as exc:
        return {"devices": devices, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "devices": devices,
        "peer_access": UNAVAILABLE,
        "peer_access_reason": "generic OpenCL does not expose peer-access topology",
    }


def _remote_status() -> dict[str, Any]:
    """Report the already-wired remote paths without claiming remote tensors."""
    try:
        from chronus.mla1517.remote_gpu import RemoteGPUClient, remote_endpoints
    except Exception as exc:
        return {"configured": False, "error": f"{type(exc).__name__}: {exc}"}
    endpoints = remote_endpoints()
    rows = []
    for endpoint in endpoints:
        client = RemoteGPUClient(endpoint)
        try:
            health = client.health()
            devices = [device.as_dict() for device in client.devices()]
            rows.append(
                {
                    "endpoint": client.endpoint,
                    "reachable": True,
                    "advertised_paths": health.get("endpoints", []),
                    "devices": devices,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "endpoint": client.endpoint,
                    "reachable": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "configured": bool(endpoints),
        "agents": rows,
        "sha256d_path": "implemented",
        "ladder_path": "implemented",
        "tensor_path": "unimplemented",
    }


def _benchmark_once(runtime: Any, a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    result, evidence = runtime.execute_with_evidence(
        "matmul", (a, b), (a.shape, b.shape), (a.shape[0], b.shape[1])
    )
    expected = a @ b
    difference = np.abs(result - expected)
    passed = bool(np.allclose(result, expected, rtol=1e-4, atol=1e-4))
    if not passed:
        raise RuntimeError(
            f"Chronus iGPU result failed CPU reference: max_abs_error={difference.max()}"
        )
    operations = 2 * a.shape[0] * a.shape[1] * b.shape[1]
    bytes_minimum = a.nbytes + b.nbytes + result.nbytes
    device_s = (
        evidence.device_time_ns / 1e9
        if evidence.device_time_ns is not None and evidence.device_time_ns > 0
        else None
    )
    return {
        "evidence": evidence.as_dict(),
        "correctness": {
            "passed": True,
            "reference": "numpy.matmul_float32",
            "max_abs_error": float(difference.max(initial=0.0)),
            "output_sha256": _array_digest(result),
        },
        "work": {
            "operations": operations,
            "minimum_bytes": bytes_minimum,
            "arithmetic_intensity_flops_per_byte": operations / bytes_minimum,
        },
        "measured": {
            "device_gflops": (operations / device_s / 1e9 if device_s is not None else UNAVAILABLE),
            "device_effective_bandwidth_gbps": (
                bytes_minimum / device_s / 1e9 if device_s is not None else UNAVAILABLE
            ),
            "wall_gflops": operations / (evidence.wall_time_ns / 1e9) / 1e9,
        },
    }


def _mining_measurement(count: int) -> dict[str, Any]:
    """Measure the production SHA256d path; never equate it with pool acceptance."""
    if count <= 0:
        return {"status": UNAVAILABLE, "reason": "sha256d count was not requested"}
    from mining.bitcoin_hasher import BitcoinHasher

    hasher = BitcoinHasher(backend="opencl")
    header = bytes(80)
    target = bytes(32)  # practically forces complete traversal; any hit is still verified
    started_ns = time.perf_counter_ns()
    nonce, digest, hashes = hasher.grind_target_range_chunked(header, target, 0, count)
    wall_ns = time.perf_counter_ns() - started_ns
    if not 0 < int(hashes) <= count:
        raise RuntimeError(f"SHA256d path reported incoherent work count {hashes}/{count}")
    return {
        "status": "measured",
        "backend": str(hasher.backend),
        "device": str(hasher.device),
        "requested_hashes": count,
        "executed_hashes": int(hashes),
        "wall_ns": wall_ns,
        "hashes_per_second": int(hashes) / (wall_ns / 1e9),
        "kernel_ms": float(getattr(hasher, "kernel_ms", 0.0)),
        "launches": int(getattr(hasher, "launches", 0)),
        "share": (
            UNAVAILABLE if nonce is None else {"nonce": int(nonce), "digest": bytes(digest).hex()}
        ),
        "share_verification": "production BitcoinHasher exact recheck",
        "pool_acknowledgement": UNAVAILABLE,
    }


def _summary(samples: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(samples)
    device = [
        row["measured"]["device_gflops"]
        for row in rows
        if isinstance(row["measured"]["device_gflops"], (int, float))
    ]
    wall = [float(row["measured"]["wall_gflops"]) for row in rows]
    return {
        "sample_count": len(rows),
        "device_gflops_median": statistics.median(device) if device else UNAVAILABLE,
        "device_gflops_min": min(device) if device else UNAVAILABLE,
        "device_gflops_max": max(device) if device else UNAVAILABLE,
        "wall_gflops_median": statistics.median(wall),
    }


def capture(
    *,
    size: int,
    iterations: int,
    stress_seconds: float,
    sha256d_count: int = 0,
    peak_gflops: float | None = None,
    peak_bandwidth_gbps: float | None = None,
) -> dict[str, Any]:
    from chronus.tensor_compute import get_runtime

    runtime = get_runtime()
    rng = np.random.default_rng(1517)
    a = rng.standard_normal((size, size), dtype=np.float32)
    b = rng.standard_normal((size, size), dtype=np.float32)
    # Warm-up compiles/caches before the observation window.
    _benchmark_once(runtime, a, b)
    before_rapl = _rapl_snapshot()
    started = time.perf_counter()
    samples = [_benchmark_once(runtime, a, b) for _ in range(iterations)]
    stress_samples: list[dict[str, Any]] = []
    stress_started = time.perf_counter()
    while stress_seconds > 0 and time.perf_counter() - stress_started < stress_seconds:
        stress_samples.append(_benchmark_once(runtime, a, b))
    elapsed = time.perf_counter() - started
    after_rapl = _rapl_snapshot()
    mining = _mining_measurement(sha256d_count)
    summary = _summary(samples)
    stress_summary = _summary(stress_samples) if stress_samples else UNAVAILABLE
    degradation = UNAVAILABLE
    if stress_samples:
        rates = [
            row["measured"]["device_gflops"]
            for row in stress_samples
            if isinstance(row["measured"]["device_gflops"], (int, float))
        ]
        if len(rates) >= 2 and rates[0] > 0:
            degradation = max(0.0, (rates[0] - statistics.median(rates[-5:])) / rates[0] * 100)
    ai = samples[0]["work"]["arithmetic_intensity_flops_per_byte"]
    measured = summary["device_gflops_median"]
    roofline = roofline_record(
        ai,
        float(measured) if isinstance(measured, (int, float)) else 0.0,
        peak_gflops=peak_gflops,
        peak_bandwidth_gbps=peak_bandwidth_gbps,
    )
    module_path = Path(__file__).resolve().parents[2] / "chronus" / "tensor_compute.py"
    kernel_path = Path(__file__).resolve().parents[2] / "chronus" / "kernels" / "tensor_ops.cl"
    attestation_record = {
        "kind": "software_content_binding",
        "hardware_rooted": False,
        "device_id": runtime.device_id,
        "runtime_sha256": _sha256_file(module_path),
        "kernel_sha256": _sha256_file(kernel_path),
        "input_a_sha256": _array_digest(a),
        "input_b_sha256": _array_digest(b),
        "sample_output_sha256": samples[-1]["correctness"]["output_sha256"],
    }
    attestation_record["binding_sha256"] = _sha256_bytes(
        json.dumps(attestation_record, sort_keys=True, separators=(",", ":")).encode()
    )
    artifact = {
        "schema": SCHEMA,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "truth_class": "measured_runtime_evidence",
        "device": runtime.probe.as_dict(),
        "configuration": {
            "matrix_size": size,
            "iterations": iterations,
            "stress_seconds_requested": stress_seconds,
            "sha256d_count_requested": sha256d_count,
            "float_dtype": "float32",
            "seed": 1517,
            "implementation_identity": os.getenv("GITHUB_SHA") or UNAVAILABLE,
        },
        "samples": samples,
        "summary": summary,
        "stress": {
            "status": "measured" if stress_samples else UNAVAILABLE,
            "summary": stress_summary,
            "degradation_pct": degradation,
            "correctness_failures": 0,
        },
        "roofline": roofline,
        "mining": mining,
        "sensors": {
            "gpu_hwmon": _sensor_rows(),
            "rapl": _rapl_delta(before_rapl, after_rapl, elapsed),
            "rapl_scope": "package_proxy; not an iGPU-only measurement",
        },
        "topology": _topology(),
        "remote": _remote_status(),
        "attestation": attestation_record,
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    artifact["artifact_sha256"] = _sha256_bytes(canonical)
    return artifact


def validate_artifact(artifact: dict[str, Any]) -> None:
    """Reject an artifact that does not prove physical, correct Chronus execution."""
    if artifact.get("schema") != SCHEMA:
        raise ValueError("wrong Chronus iGPU evidence schema")
    device = artifact.get("device")
    if not isinstance(device, dict) or not device.get("available"):
        raise ValueError("artifact has no available physical OpenCL device")
    samples = artifact.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("artifact has no measured tensor samples")
    for sample in samples:
        evidence = sample.get("evidence") or {}
        correctness = sample.get("correctness") or {}
        if evidence.get("hardware_executed") is not True:
            raise ValueError("artifact contains a non-hardware tensor sample")
        if correctness.get("passed") is not True:
            raise ValueError("artifact contains an unverified tensor result")
        if int(evidence.get("wall_time_ns", 0)) <= 0:
            raise ValueError("artifact contains no observation window")
    claimed = str(artifact.get("artifact_sha256", ""))
    unsigned = dict(artifact)
    unsigned.pop("artifact_sha256", None)
    actual = _sha256_bytes(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode())
    if claimed != actual:
        raise ValueError("artifact content hash mismatch")


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "igpu"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--stress-seconds", type=float, default=0.0)
    parser.add_argument("--sha256d-count", type=int, default=0)
    parser.add_argument("--peak-gflops", type=float)
    parser.add_argument("--peak-bandwidth-gbps", type=float)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.size <= 0 or args.iterations <= 0 or args.stress_seconds < 0 or args.sha256d_count < 0:
        parser.error("size/iterations must be positive; durations/counts must be non-negative")
    artifact = capture(
        size=args.size,
        iterations=args.iterations,
        stress_seconds=args.stress_seconds,
        sha256d_count=args.sha256d_count,
        peak_gflops=args.peak_gflops,
        peak_bandwidth_gbps=args.peak_bandwidth_gbps,
    )
    output = args.output
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = Path("bench/results") / (
            f"igpu_{_safe_name(artifact['device']['device_name'])}_{stamp}.json"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    validate_artifact(artifact)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    print(artifact["artifact_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
