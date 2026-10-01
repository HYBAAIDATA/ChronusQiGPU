import math
import numpy as np

from experiments.lucas15_operator_ablation import (
    ALGORITHMS, ARMS, LUCAS_15, M, M15_EXACT, PISOT_15,
    apply_operator, operator_for_arm, run_ablation, summarise,
)


def test_lucas15_constants_are_exact():
    actual = np.linalg.matrix_power(M.astype(np.int64), 15)
    assert np.array_equal(actual, M15_EXACT.astype(np.int64))
    assert int(round(np.trace(actual))) == LUCAS_15 == 1364
    assert math.isclose(PISOT_15, 0.0007331374358574045, rel_tol=1e-12)


def test_raw_and_golden_eigenbasis_m15_agree():
    assert np.allclose(operator_for_arm("m15"), operator_for_arm("m15_golden_eigenbasis"), atol=1e-12)


def test_schedule_arm_is_a_permutation_not_an_operator_claim():
    vector = np.arange(64, dtype=float).astype(complex)
    scheduled = apply_operator(vector, "lucas15_schedule")
    assert sorted(scheduled.real.tolist()) == vector.real.tolist()
    assert not np.array_equal(scheduled, vector)


def test_ablation_is_complete_and_seeded():
    first = run_ablation(repeats=1, dimension=16, seed=42)
    second = run_ablation(repeats=1, dimension=16, seed=42)
    assert len(first) == len(ALGORITHMS) * len(ARMS)
    assert {(r.algorithm, r.arm) for r in first} == {
        (algorithm, arm) for algorithm in ALGORITHMS for arm in ARMS
    }
    # Timing/memory vary; scientific outputs do not.
    assert [r.final_objective_or_error for r in first] == [r.final_objective_or_error for r in second]
    assert all(r.backend == "numpy_cpu" for r in first)


def test_summary_preserves_claim_boundary():
    summary = summarise(run_ablation(repeats=1, dimension=16, seed=7))
    assert "no physical quantum or mining acceleration claim" in summary["claim_boundary"]
    assert summary["constants"]["lucas_15"] == 1364
