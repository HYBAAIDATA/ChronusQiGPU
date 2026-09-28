#!/usr/bin/env python3
"""Sovereign CI gate: real OpenCL device plus exact ladder and PRIME-DB round trip."""

from __future__ import annotations
import json
import os
import tempfile
import struct
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "python"))
from mla1517.scaling import OpenCLLadderExecutor, LUCAS_PISOT_LADDER
from mla1517.store import PrimeDB


def _write_report(report_path: Path, report: dict[str, object]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def main() -> int:
    report_path = Path(__file__).parents[1] / "results/strict_hardware_gate.json"
    if os.getenv("MLA1517_STRICT_HARDWARE_CI") != "1":
        report = {
            "status": "FAIL",
            "reason": "MLA1517_STRICT_HARDWARE_CI=1 is required for sovereign hardware CI",
        }
        _write_report(report_path, report)
        return 1
    if os.getenv("MLA1517_GPU_BACKEND", "").lower() != "opencl":
        report = {"status": "FAIL", "reason": "MLA1517_GPU_BACKEND=opencl is required"}
        _write_report(report_path, report)
        return 1
    try:
        executor = OpenCLLadderExecutor()
        results = executor.execute()
    except Exception as exc:
        report = {"status": "FAIL", "reason": "exact OpenCL ladder unavailable", "detail": str(exc)}
        _write_report(report_path, report)
        return 1
    if tuple(item.scale for item in results) != LUCAS_PISOT_LADDER:
        report = {"status": "FAIL", "reason": "ladder mismatch"}
        _write_report(report_path, report)
        return 1
    with tempfile.TemporaryDirectory() as directory:
        db = PrimeDB(Path(directory) / "prime.db")
        for item in results:
            obj = db.put(
                {
                    "tensor_state": {
                        "scale": item.scale,
                        "fibonacci": item.fibonacci,
                        "lucas": item.lucas,
                        "padovan": item.padovan,
                    },
                    "backend": "opencl",
                },
                sequence_index=item.scale,
                scale=item.scale,
                family="lucas_pisot_gpu",
            )
            loaded = db.get(obj.object_id)
            if loaded.payload != obj.payload or loaded.scale != item.scale:
                raise RuntimeError("PRIME-DB invariant round trip failed")
            tensor_id = db.put_exact_tensor(
                struct.pack("<4q", item.fibonacci, item.lucas, item.padovan, 0),
                global_scale=0,
            )
            tensor = db.get_exact_tensor(tensor_id)
            if tensor["amplitude_count"] != 1 or len(tensor["payload"]) != 32:
                raise RuntimeError("PRIME-DB exact long4 tensor invariant failed")
        if db.count() != len(LUCAS_PISOT_LADDER):
            raise RuntimeError("PRIME-DB count mismatch")
        db.close()
    report = {
        "status": "PASS",
        "gpu_backend": "opencl",
        "device_name": str(getattr(executor.device, "name", "")),
        "device_vendor": str(getattr(executor.device, "vendor", "")),
        "ladder": LUCAS_PISOT_LADDER,
        "primedb_round_trip": True,
    }
    _write_report(report_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
