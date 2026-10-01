"""Production Chronus measurement: existing stack plus physical tensor evidence.

The historical :func:`measure_chronus` API remains unchanged. This production
entry point layers physical Chronus tensor execution and execution-device
provenance into a new content-addressed artifact without removing any existing
host, mining, topology, stability, or efficiency measurement.
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


def _device_tensor_stage(*, quick: bool) -> Dict[str, Any]:
    try:
        measurement = measure_device_tensor_matmul(
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
            "backend": str(measurement.get("backend", "") if isinstance(measurement, dict) else ""),
            "device_id": str(measurement.get("device_id", "") if isinstance(measurement, dict) else ""),
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


def measure_chronus_production(
    *,
    quick: bool = True,
    hmac_key: Optional[bytes] = None,
    store: Optional[EvidenceStore] = None,
) -> Tuple[MeasurementArtifact, Dict[str, bool]]:
    """Return a production evidence artifact without changing existing paths."""
    persistent_attestation = hmac_key is not None or bool(os.environ.get(ENV_KEY, "").strip())
    base_artifact, availability = measure_chronus(
        quick=quick,
        hmac_key=hmac_key,
        store=EvidenceStore(),
    )

    workloads = dict(base_artifact.workloads)
    tensor_device = _device_tensor_stage(quick=quick)
    workloads["tensor_device"] = tensor_device

    baseline = dict(base_artifact.baseline)
    bindings = [
        _binding(baseline, "hashrate", workloads.get("hashrate", {})),
        _binding(baseline, "tensor_device", tensor_device),
    ]
    baseline["execution_provenance"] = bindings

    execution_fp = next(
        (
            str(binding.get("device_fingerprint", ""))
            for binding in reversed(bindings)
            if binding.get("matched") and binding.get("device_fingerprint")
        ),
        "",
    )

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
        device_fingerprint=execution_fp or base_artifact.device_fingerprint,
    )
    key = hmac_key if hmac_key is not None else load_hmac_key()
    artifact.attestation = attest_artifact(artifact, key)
    target_store = store if store is not None else EvidenceStore()
    target_store.write(artifact)

    result = dict(availability)
    result["workloads.tensor_device"] = bool(
        isinstance(tensor_device, dict) and tensor_device.get("available", True)
    )
    result["artifact.replay"] = replay_artifact(artifact)
    result["artifact.execution_device_bound"] = bool(execution_fp)
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
        help="return non-zero unless physical Chronus tensor execution was measured",
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
    if args.require_device and not availability.get("workloads.tensor_device", False):
        return 2
    if args.require_device and not availability.get("artifact.execution_device_bound", False):
        return 3
    if args.require_persistent_attestation and not availability.get(
        "artifact.persistent_attestation_key", False
    ):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
