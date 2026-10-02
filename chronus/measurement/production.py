"""Production Chronus measurement across physical tensor substrates.

The historical :func:`measure_chronus` API remains unchanged. This production
entry point preserves the existing OpenCL tensor evidence and layers native
CUDA/Metal measurements beside it. At least one verified physical tensor path
may satisfy the production device gate; no execution substrate is substituted
for another and unavailable paths remain explicit evidence.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ._common import canonical_json, to_payload, unavailable
from .attestation.artifact import MeasurementArtifact, build_artifact
from .attestation.hmac import ENV_KEY, attest_artifact, load_hmac_key
from .attestation.replay import replay_artifact
from .run import measure_chronus
from .store.evidence import EvidenceStore
from .system.execution import bind_execution_device
from .workload.device_tensor import measure_device_tensor_matmul
from .workload.native_device_tensor import measure_native_device_tensor_matmul


def _device_tensor_stage(*, quick: bool) -> Dict[str, Any]:
    """Preserve the historical physical OpenCL tensor evidence stage."""
    try:
        measurement = measure_device_tensor_matmul(
            shape=(128, 128) if quick else (512, 512),
            repeats=8 if quick else 32,
            warmup=1 if quick else 4,
        )
        return to_payload(measurement)
    except Exception as exc:
        return unavailable(f"{type(exc).__name__}: {exc}")


def _native_tensor_stage(execution_api: str, *, quick: bool) -> Dict[str, Any]:
    try:
        measurement = measure_native_device_tensor_matmul(
            execution_api,
            shape=(128, 128) if quick else (512, 512),
            repeats=8 if quick else 32,
            warmup=1 if quick else 4,
        )
        return to_payload(measurement)
    except Exception as exc:
        return unavailable(f"{type(exc).__name__}: {exc}")


def _binding(
    baseline: Dict[str, Any],
    workload: str,
    measurement: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(measurement, dict) or measurement.get("available") is False:
        return {
            "workload": workload,
            "backend": str(
                measurement.get("backend", "") if isinstance(measurement, dict) else ""
            ),
            "device_id": str(
                measurement.get("device_id", "") if isinstance(measurement, dict) else ""
            ),
            "matched": False,
            "device_fingerprint": "",
            "matched_device": "",
            "matched_backend": "",
            "method": "measurement_unavailable",
        }
    return bind_execution_device(
        baseline,
        workload=workload,
        backend=str(measurement.get("backend", "") or ""),
        device_id=str(measurement.get("device_id", "") or ""),
    )


def _stage_available(stage: Dict[str, Any]) -> bool:
    return bool(isinstance(stage, dict) and stage.get("available", True))


def _first_bound_fingerprint(bindings: list[Dict[str, Any]]) -> str:
    return next(
        (
            str(binding.get("device_fingerprint", ""))
            for binding in bindings
            if binding.get("matched") and binding.get("device_fingerprint")
        ),
        "",
    )


def measure_chronus_production(
    *,
    quick: bool = True,
    hmac_key: Optional[bytes] = None,
    store: Optional[EvidenceStore] = None,
) -> Tuple[MeasurementArtifact, Dict[str, bool]]:
    """Return attested evidence for every physical Chronus tensor path present."""
    persistent_attestation = hmac_key is not None or bool(
        os.environ.get(ENV_KEY, "").strip()
    )
    base_artifact, availability = measure_chronus(
        quick=quick,
        hmac_key=hmac_key,
        store=EvidenceStore(),
    )

    workloads = dict(base_artifact.workloads)
    tensor_opencl = _device_tensor_stage(quick=quick)
    tensor_cuda = _native_tensor_stage("cuda", quick=quick)
    tensor_metal = _native_tensor_stage("metal", quick=quick)

    # Historical key retained for compatibility. Native stages are additive.
    workloads["tensor_device"] = tensor_opencl
    workloads["tensor_cuda_device"] = tensor_cuda
    workloads["tensor_metal_device"] = tensor_metal

    baseline = dict(base_artifact.baseline)
    bindings = [
        _binding(baseline, "hashrate", workloads.get("hashrate", {})),
        _binding(baseline, "tensor_device", tensor_opencl),
        _binding(baseline, "tensor_cuda_device", tensor_cuda),
        _binding(baseline, "tensor_metal_device", tensor_metal),
    ]
    baseline["execution_provenance"] = bindings

    tensor_bindings = bindings[1:]
    tensor_execution_fp = _first_bound_fingerprint(tensor_bindings)
    execution_fp = _first_bound_fingerprint(bindings)

    artifact = build_artifact(
        {
            "baseline": baseline,
            "topology": base_artifact.topology,
            "profiling": base_artifact.profiling,
            "roofline": base_artifact.roofline,
            "workloads": workloads,
            "efficiency": base_artifact.efficiency,
            "stability": base_artifact.stability,
        },
        device_fingerprint=(
            tensor_execution_fp or execution_fp or base_artifact.device_fingerprint
        ),
    )
    key = hmac_key if hmac_key is not None else load_hmac_key()
    artifact.attestation = attest_artifact(artifact, key)
    target_store = store if store is not None else EvidenceStore()
    target_store.write(artifact)

    opencl_ok = _stage_available(tensor_opencl)
    cuda_ok = _stage_available(tensor_cuda)
    metal_ok = _stage_available(tensor_metal)

    result = dict(availability)
    result["workloads.tensor_device"] = opencl_ok
    result["workloads.tensor_cuda_device"] = cuda_ok
    result["workloads.tensor_metal_device"] = metal_ok
    result["workloads.tensor_device_any"] = bool(opencl_ok or cuda_ok or metal_ok)
    result["artifact.replay"] = replay_artifact(artifact)
    result["artifact.execution_device_bound"] = bool(execution_fp)
    result["artifact.tensor_device_bound"] = bool(tensor_execution_fp)
    result["artifact.persistent_attestation_key"] = persistent_attestation
    return artifact, result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run production Chronus measurement")
    parser.add_argument(
        "--full",
        action="store_true",
        help="use production-size sampling windows instead of CI-sized quick windows",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the canonical attested artifact JSON to this path",
    )
    parser.add_argument(
        "--require-device",
        action="store_true",
        help=(
            "return non-zero unless at least one physical OpenCL, CUDA, or Metal "
            "Chronus tensor path was measured and bound to its execution device"
        ),
    )
    parser.add_argument(
        "--require-persistent-attestation",
        action="store_true",
        help="return non-zero unless attestation uses an explicit durable key",
    )
    args = parser.parse_args(argv)

    artifact, availability = measure_chronus_production(quick=not args.full)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical_json(artifact.as_dict()), encoding="utf-8")

    print(f"artifact {artifact.id} digest {artifact.digest}")
    print(f"device_fingerprint {artifact.device_fingerprint or 'unbound'}")
    print(f"attestation {artifact.attestation[:32]}…")
    for stage, ok in sorted(availability.items()):
        print(f"  {'ok ' if ok else 'n/a'} {stage}")

    if not availability.get("artifact.replay", False):
        return 1
    if args.require_device and not availability.get("workloads.tensor_device_any", False):
        return 2
    if args.require_device and not availability.get("artifact.tensor_device_bound", False):
        return 3
    if args.require_persistent_attestation and not availability.get(
        "artifact.persistent_attestation_key", False
    ):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
