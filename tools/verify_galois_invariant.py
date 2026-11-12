#!/usr/bin/env python3
"""Verify exact PV field identities and measure the six fixed reference inputs.

Inputs, checks, ordering and JSON schema are deterministic. Measured durations
vary with the host and are recorded as integer nanoseconds, without rounding.
"""

import argparse
import hashlib
import inspect
import json
import os
import platform
from pathlib import Path
from time import perf_counter_ns

from chronus.quantum.extension_search import PHI_PERIOD, _PHI_POWER_TABLE, phi_element_power


VECTORS = (
    (10**4, (170, 73)), (10**5, (186, 210)),
    (10**12, (87, 160)), (10**15, (96, 216)),
    (10**18, (2, 3)), (10**20, (248, 130)),
)


def matrix_power(index):
    """Independent companion-matrix exponentiation without period reduction."""
    def multiply(x, y):
        return tuple(tuple(sum(x[i][k] * y[k][j] for k in range(2)) % 257
                           for j in range(2)) for i in range(2))
    result, base = ((1, 0), (0, 1)), ((1, 1), (1, 0))
    while index:
        if index & 1:
            result = multiply(result, base)
        base = multiply(base, base)
        index >>= 1
    return result[1][1], result[0][1]


def verify_and_measure(repetitions=15):
    if type(repetitions) is not int or repetitions < 3 or repetitions % 2 != 1:
        raise ValueError("repetitions must be an odd integer of at least three")
    if PHI_PERIOD != 516 or _PHI_POWER_TABLE.itemsize < 2 or not _PHI_POWER_TABLE.readonly:
        raise ArithmeticError("Invalid period or residue storage")
    if phi_element_power(516) != (1, 0):
        raise ArithmeticError("Period closure failed")
    if any(phi_element_power(i) == (1, 0) for i in range(1, 516)):
        raise ArithmeticError("Period is not minimal")
    for index in range(516):
        a, b = phi_element_power(index)
        if phi_element_power(index + 258) != ((-a) % 257, (-b) % 257):
            raise ArithmeticError("Anti-period failed")
    rows = []
    for index, expected in VECTORS:
        if phi_element_power(index) != expected or matrix_power(index) != expected:
            raise ArithmeticError("Reference vector mismatch")
        if (expected[0]**2 + expected[0]*expected[1] - expected[1]**2) % 257 != pow(256, index, 257):
            raise ArithmeticError("Norm parity failed")
        for _ in range(100):
            phi_element_power(index)
        samples = []
        for _ in range(repetitions):
            started = perf_counter_ns()
            phi_element_power(index)
            samples.append(perf_counter_ns() - started)
        rows.append({"scale_index": str(index), "result": list(expected),
                     "median_ns": sorted(samples)[repetitions // 2],
                     "samples_ns": samples})
    source_path = inspect.getsourcefile(phi_element_power)
    return {
        "_provenance": {"authored_by": "CodeRabbit Coding Agent",
                        "generator": "tools/verify_galois_invariant.py",
                        "task_id": "f77d97e8-279f-4ff4-ba2d-b4ad6de3ebe2"},
        "schema_version": 1, "status": "PASS", "period": PHI_PERIOD,
        "table_payload_bytes": _PHI_POWER_TABLE.nbytes,
        "residue_storage_bits": _PHI_POWER_TABLE.itemsize * 8,
        "function_sha256": hashlib.sha256(inspect.getsource(phi_element_power).encode()).hexdigest(),
        "module_sha256": hashlib.sha256(Path(source_path).read_bytes()).hexdigest(),
        "python": platform.python_version(), "architecture": platform.machine(),
        "timing_scope": "PV arithmetic kernel, one complete call per sample; 100 warm-up calls per vector",
        "repetitions": repetitions, "vectors": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(os.getenv("WORKSPACE_ROOT", ".")) / "output/mining-galois-invariant.json")
    parser.add_argument("--repetitions", type=int, default=15)
    args = parser.parse_args()
    report = verify_and_measure(args.repetitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
