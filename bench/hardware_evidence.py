#!/usr/bin/env python3
"""Validate and content-address a measured HybridCoordinator job artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class HardwareEvidenceError(ValueError):
    pass


def validate_job_artifact(value: dict[str, Any]) -> dict[str, Any]:
    perf = value.get("performance")
    if not isinstance(perf, dict) or perf.get("truth_class") != "measured":
        raise HardwareEvidenceError("job artifact lacks measured performance evidence")
    samples = perf.get("samples")
    if not isinstance(samples, list) or not samples:
        raise HardwareEvidenceError("job artifact lacks per-device samples")
    if any(sample.get("source") != "measured" for sample in samples):
        raise HardwareEvidenceError("non-measured sample in hardware artifact")
    if int(perf.get("protocol_hashes", 0)) <= 0:
        raise HardwareEvidenceError("hardware artifact contains no executed protocol hashes")
    if int(perf.get("wall_ns", 0)) <= 0:
        raise HardwareEvidenceError("hardware artifact has no observation window")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": "hyba.hardware-evidence.v1",
        "artifact_sha256": hashlib.sha256(canonical).hexdigest(),
        "job": value,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    value = json.loads(args.input.read_text(encoding="utf-8"))
    evidence = validate_job_artifact(value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(evidence["artifact_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
