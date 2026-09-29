"""PYTHIA's older learner and curriculum now learn from evidence, not assertion.

Cell fate: a pattern that merely co-occurs with found shares used to become
a germ-line memory after three sightings. Under SHA-256d that is a
coincidence, so it now needs a real association (an exact binomial test
against the base rate, Bonferroni-corrected). Curriculum mastery used to be
"confidence = 1 - |psi|^(plan length + 1)": the longer the plan, the more
mastered. It now needs outcomes: the Wilson 95% lower bound of the success
rate over at least five attempts.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from Intelligence.pythia_learning import PythiaLearning, _binomial_tail
from Intelligence.pythia_memory import (
    MASTERY_MIN_TRIALS,
    CognitiveScaffolding,
    CurriculumTask,
    wilson_lower,
)

Z = 1.959964


def test_the_binomial_tail_is_exact():
    assert _binomial_tail(6, 6, 0.5) == pytest.approx(1 / 64)
    assert _binomial_tail(0, 9, 0.3) == 1.0
    exact = sum(math.comb(5, i) * 0.2**i * 0.8 ** (5 - i) for i in range(3, 6))
    assert _binomial_tail(3, 5, 0.2) == pytest.approx(exact)


def test_patterns_that_only_coincide_with_shares_stay_somatic():
    rng = random.Random(1517)
    learner = PythiaLearning()
    patterns = [np.full(32, i / 400) for i in range(200)]
    for _ in range(4):  # each pattern seen four times; shares at 2%, independent of it
        learner.learning_step(patterns, [rng.random() < 0.02 for _ in patterns])
    assert learner.learning_step([], []).germ_line_count == 0


def test_a_real_association_earns_germ_line_once_the_base_rate_is_known():
    learner = PythiaLearning()
    signal = np.linspace(0.0, 1.0, 32)
    result = learner.learning_step([signal] * 6, [True] * 6)
    # Alone, 6 of 6 against an unknown base rate (Laplace 1/2) is p = 1/64: not enough.
    assert result.germ_line_count == 0
    noise = [np.full(32, i * 0.013) for i in range(30)]
    result = learner.learning_step(noise, [False] * 30)
    # Against 0 of 30 elsewhere (base 1/32), p = (1/32)^6: germ-line.
    assert result.germ_line_count >= 1


def test_wilson_lower_bound():
    assert wilson_lower(0, 0) == 0.0
    assert wilson_lower(9, 9) == pytest.approx(9 / (9 + Z * Z))  # n / (n + z^2) at p = 1
    p, n = 0.8, 20
    expected = (p + Z * Z / (2 * n) - Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))) / (
        1 + Z * Z / n
    )
    assert wilson_lower(16, 20) == pytest.approx(expected)


class _Semantic:
    def learn_concept(self, concept):
        pass


def test_mastery_is_earned_from_outcomes_not_plan_length():
    scaffold = CognitiveScaffolding(_Semantic())
    task = CurriculumTask(99, "a task", 0.5, ["x"], [], mastery_threshold=0.7)
    # n / (n + z^2) >= 0.7 first at n = 9 straight successes.
    results = [scaffold.record_mastery(task, True) for _ in range(9)]
    assert results == [False] * 8 + [True]
    assert MASTERY_MIN_TRIALS == 5

    easy = CurriculumTask(98, "easy", 0.1, ["y"], [], mastery_threshold=0.2)
    fresh = CognitiveScaffolding(_Semantic())
    # Even an easy task needs five attempts; failures pull the bound down.
    assert [fresh.record_mastery(easy, ok) for ok in (True, True, True, True)] == [False] * 4
    assert fresh.record_mastery(easy, False) is True  # 4 of 5: lower bound 0.376 >= 0.2
