"""Deterministic microbenchmark: period-516 F_257[phi] fold/step/unfold.

Runs the parity reference vectors [10**4, 10**5, 10**12, 10**15, 10**18,
10**20] and records function_sha256 and median_ns per operation. Exact
round-trip verification is included in the timed fold/step path scope note.
"""
import hashlib
import inspect
import json
import platform
import statistics
import sys
import time

from chronus.opencl_folded_adapter import (
    LUT_SHA256,
    LUT_TUPLE,
    PISANO_PERIOD,
    fold_scale_index,
    step_folded_record,
    unfold_scale_record,
)

REFERENCE_VECTORS = [10**4, 10**5, 10**12, 10**15, 10**18, 10**20]
WARMUPS = 1
REPETITIONS = 7


def function_sha256(fn) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()


def timed(fn, *args):
    fn(*args)
    samples = []
    for _ in range(REPETITIONS):
        start = time.perf_counter_ns()
        output = fn(*args)
        samples.append(time.perf_counter_ns() - start)
    return output, samples


def main():
    results = []
    for s in REFERENCE_VECTORS:
        q, r = divmod(s, PISANO_PERIOD)
        record, fold_samples = timed(fold_scale_index, s)
        stepped, step_samples = timed(step_folded_record, record, 10**12)
        (exact_s, (coeff_a, coeff_b), _flags), unfold_samples = timed(
            unfold_scale_record, record
        )
        if exact_s != s or (coeff_a, coeff_b) != LUT_TUPLE[r]:
            raise AssertionError("fold/unfold round-trip mismatch")
        step_s, _, _ = unfold_scale_record(stepped)
        if step_s != s + 10**12:
            raise AssertionError("step parity mismatch")
        for operation, samples in (
            ("fold_scale_index", fold_samples),
            ("step_folded_record", step_samples),
            ("unfold_scale_record", unfold_samples),
        ):
            results.append({
                "scale_index": s,
                "operation": operation,
                "times_ns": samples,
                "median_ns": statistics.median(samples),
                "function_sha256": function_sha256(
                    {
                        "fold_scale_index": fold_scale_index,
                        "step_folded_record": step_folded_record,
                        "unfold_scale_record": unfold_scale_record,
                    }[operation]
                ),
            })
        results[-3]["epoch_q"] = q
        results[-3]["r_mod_516"] = r
        results[-3]["coeff_a"], results[-3]["coeff_b"] = LUT_TUPLE[r]
        results[-3]["roundtrip_exact"] = True
    print(json.dumps({
        "_provenance": {"generated_by": "CodeRabbit Coding Agent",
                        "task_id": "f77d97e8-279f-4ff4-ba2d-b4ad6de3ebe2"},
        "workload": "period-516 F_257[phi] folded-state fold/step/unfold over reference vectors",
        "lut_sha256": LUT_SHA256,
        "lut_bytes": 2064,
        "pisano_period": PISANO_PERIOD,
        "warmups": WARMUPS,
        "repetitions": REPETITIONS,
        "timer": "perf_counter_ns",
        "timing_scope": "complete function call; exact round-trip verification excluded",
        "python": sys.version,
        "platform": platform.platform(),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
