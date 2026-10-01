"""Entry point — the full tech-stack measurement, one attested artifact.

Every stage that cannot execute reports ``available: False`` with its reason
inside the artifact — the artifact is honest about what was and was not
measured. Stages that do run measured real work.

Invariants:
    RUN1: every measurement is captured (or its absence recorded).
    RUN2: every measurement is attested.
    RUN3: every measurement is stored.
    RUN4: every measurement is replayable.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

from ._common import to_payload, unavailable
from .attestation.artifact import MeasurementArtifact, build_artifact
from .attestation.hmac import attest_artifact, load_hmac_key
from .attestation.replay import replay_artifact
from .efficiency.energy import measure_energy
from .efficiency.perf_per_watt import compute_perf_per_watt
from .efficiency.power import measure_power
from .efficiency.thermal import measure_thermal
from .profiling.events import profile_kernel
from .profiling.timeline import capture_timeline
from .roofline.bandwidth import measure_bandwidth
from .roofline.compute import measure_peak_compute
from .roofline.plot import build_roofline
from .stability.regression import run_regression
from .stability.stress import run_stress_test
from .stability.throttle import detect_throttle
from .store.evidence import EvidenceStore
from .system.baseline import capture_baseline
from .topology.cache import measure_cache_hierarchy
from .topology.compute import measure_compute_topology
from .topology.interconnect import measure_interconnect
from .topology.memory import measure_memory_hierarchy
from .workload.hashrate import measure_hashrate
from .workload.mpo import measure_mpo_apply
from .workload.mps import measure_mps_gate
from .workload.tensor import measure_tensor_contraction
from .workload.tt import measure_tt_svd

logger = logging.getLogger("chronus.measurement")


def _stage(name: str, fn: Callable[[], Any]) -> Dict[str, Any]:
    """Run a stage; an exception becomes an unavailable record, never a crash."""
    try:
        out = fn()
        return to_payload(out)
    except Exception as exc:
        logger.debug("measurement stage %s unavailable: %s", name, exc)
        return unavailable(f"{type(exc).__name__}: {exc}")


def measure_chronus(
    *,
    quick: bool = True,
    hmac_key: Optional[bytes] = None,
    store: Optional[EvidenceStore] = None,
) -> Tuple[MeasurementArtifact, Dict[str, Any]]:
    """Run the full measurement tree; return (artifact, availability report).

    ``quick`` keeps every workload small enough for CI; pass ``quick=False``
    for the longer production sampling windows.
    """
    samples = {"hashrate": (4, 1, 2048)} if quick else {"hashrate": (16, 4, 8192)}
    repeats = 8 if quick else 32
    matmul_n = 256 if quick else 512
    bw_bytes = 16 * 1024 * 1024 if quick else 64 * 1024 * 1024
    stress_s = 2.0 if quick else 30.0

    availability: Dict[str, bool] = {}

    # 1. System baseline
    baseline = capture_baseline()
    device = baseline.devices[0]

    # 2. Hardware topology
    topology = {
        "memory": _stage("topology.memory", lambda: measure_memory_hierarchy(device)),
        "compute": _stage("topology.compute", lambda: measure_compute_topology(device)),
        "cache": _stage("topology.cache", lambda: measure_cache_hierarchy(device)),
        "interconnect": _stage("topology.interconnect", lambda: measure_interconnect(device)),
    }

    # 3. Profiling — a real SHA-256d window is the kernel under observation
    from ..opencl_host import OpenClPunchHost

    host = OpenClPunchHost()
    import os

    def _scan() -> Any:
        return host.scan_sha256d(os.urandom(76), 0, 512)

    profiles = _stage(
        "profiling.events",
        lambda: profile_kernel("sha256d_scan", _scan, runs=3),
    )
    timeline = _stage(
        "profiling.timeline",
        lambda: capture_timeline([("sha256d_scan", _scan)]),
    )
    profiling = {"profiles": profiles, "timeline": timeline}

    # 4. Roofline — measured host peaks; workloads classified against them
    bw = _stage("roofline.bandwidth", lambda: measure_bandwidth(size_bytes=bw_bytes))
    pk = _stage(
        "roofline.compute",
        lambda: measure_peak_compute(n=matmul_n, repeats=3),
    )
    roofline: Dict[str, Any] = {"bandwidth": bw, "compute": pk}
    if bw.get("bandwidth_gbps") and pk.get("tflops"):
        try:
            roofline["model"] = to_payload(
                build_roofline(
                    pk["tflops"],
                    bw["bandwidth_gbps"],
                    [],
                )
            )
        except Exception as exc:
            roofline["model"] = unavailable(str(exc))
    else:
        roofline["model"] = unavailable("peak measurements unavailable")

    # 5. Workloads — real scans, real contractions, real substrate ops
    n_samp, n_warm, window = samples["hashrate"]
    hashrate = _stage(
        "workload.hashrate",
        lambda: measure_hashrate(samples=n_samp, warmup=n_warm, window=window, host=host),
    )
    tensor = _stage(
        "workload.tensor",
        lambda: measure_tensor_contraction(shape=(128, 128), repeats=repeats),
    )
    mps = _stage(
        "workload.mps",
        lambda: measure_mps_gate(n_qubits=16, chi_max=8, repeats=repeats),
    )
    tt = _stage(
        "workload.tt",
        lambda: measure_tt_svd(tensor_shape=(6, 6, 6), max_rank=4, repeats=repeats),
    )
    mpo = _stage(
        "workload.mpo",
        lambda: measure_mpo_apply(n_sites=6, repeats=repeats),
    )
    workloads = {
        "hashrate": hashrate,
        "tensor": tensor,
        "mps": mps,
        "tt": tt,
        "mpo": mpo,
    }

    # 6. Efficiency — power only if a sensor exists
    power = measure_power(duration_s=0.5 if quick else 5.0)
    power_dict = to_payload(power)
    hash_obj = hashrate if isinstance(hashrate, dict) else {}
    tensor_obj = tensor if isinstance(tensor, dict) else {}
    hps_mean = (hash_obj.get("hps") or {}).get("mean")
    gf_mean = (tensor_obj.get("gflops") or {}).get("mean")

    from .workload.hashrate import HashrateMeasurement
    from .workload.tensor import TensorMeasurement
    from ..seam.types import Distribution

    def _dist(d: Dict[str, Any]) -> Distribution:
        return Distribution(
            mean=d.get("mean", 0.0),
            stddev=d.get("stddev", 0.0),
            samples=d.get("samples", 0),
            p50=d.get("p50", 0.0),
            p95=d.get("p95", 0.0),
            p99=d.get("p99", 0.0),
        )

    hr_obj = (
        HashrateMeasurement(
            hps=_dist(hash_obj["hps"]),
            kernel=hash_obj.get("kernel", ""),
            device_id=hash_obj.get("device_id", ""),
            precision=hash_obj.get("precision", ""),
            backend=hash_obj.get("backend", ""),
            samples=hash_obj.get("samples", 0),
            warmup=hash_obj.get("warmup", 0),
        )
        if hash_obj.get("hps")
        else None
    )
    tn_obj = (
        TensorMeasurement(
            gflops=_dist(tensor_obj["gflops"]),
            operation=tensor_obj.get("operation", ""),
            shape=tuple(tensor_obj.get("shape", (0, 0))),
            precision=tensor_obj.get("precision", ""),
            bytes_transferred=tensor_obj.get("bytes_transferred", 0),
            method=tensor_obj.get("method", ""),
        )
        if tensor_obj.get("gflops")
        else None
    )

    efficiency = {
        "power": power_dict,
        "thermal": _stage("efficiency.thermal", measure_thermal),
        "energy": _stage(
            "efficiency.energy",
            lambda: measure_energy(power, hps_mean, gf_mean),
        ),
        "ppw": _stage(
            "efficiency.ppw",
            lambda: compute_perf_per_watt(hr_obj, tn_obj, power),
        ),
    }

    # 7. Stability — repeated real hashrate windows
    def _hps_once() -> float:
        return measure_hashrate(samples=1, warmup=0, window=1024, host=host).hps.mean

    stability = {
        "stress": _stage("stability.stress", lambda: run_stress_test(_hps_once, stress_s)),
        "throttle": _stage("stability.throttle", lambda: detect_throttle(samples=5)),
        "regression": _stage("stability.regression", lambda: run_regression(_hps_once, runs=3)),
    }

    # 8. Artifact, 9. Attest, 10. Store
    artifact = build_artifact(
        {
            "baseline": baseline.as_dict(),
            "topology": topology,
            "profiling": profiling,
            "roofline": roofline,
            "workloads": workloads,
            "efficiency": efficiency,
            "stability": stability,
        }
    )
    key = hmac_key if hmac_key is not None else load_hmac_key()
    artifact.attestation = attest_artifact(artifact, key)
    store = store if store is not None else EvidenceStore()
    store.write(artifact)

    for section_name, section in (
        ("topology", topology),
        ("profiling", profiling),
        ("roofline", roofline),
        ("workloads", workloads),
        ("efficiency", efficiency),
        ("stability", stability),
    ):
        for stage_name, stage_out in section.items():
            if isinstance(stage_out, dict):
                availability[f"{section_name}.{stage_name}"] = bool(
                    stage_out.get("available", True)
                )
    availability["artifact.replay"] = replay_artifact(artifact)
    return artifact, availability


def main() -> int:
    """CLI: run quick measurement, print digest + availability."""
    artifact, availability = measure_chronus(quick=True)
    print(f"artifact {artifact.id} digest {artifact.digest}")
    print(f"attestation {artifact.attestation[:32]}…")
    for stage, ok in sorted(availability.items()):
        print(f"  {'ok ' if ok else 'n/a'} {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
