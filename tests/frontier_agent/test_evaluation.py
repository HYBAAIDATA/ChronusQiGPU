from dataclasses import replace
from fractions import Fraction as F
from conftest import trial
from chronus.agent.evaluation import evaluate_agent, calibrate_uncertainty


def test_authority_ignores_public_scores(qualification, identity, task):
    s, r, a, g, k = qualification
    assert r.metrics.n_trials == 12
    assert r.admitted(identity, task, now=2, keys=s.evaluator_keys, max_age=100)
    assert not replace(r, tool_fingerprint="c" * 64).admitted(
        identity, task, now=2, keys=s.evaluator_keys, max_age=100
    )


def test_ece_not_brier():
    ts = (
        trial("a", predicted_success=F(3, 4)),
        trial("b", accepted=False, predicted_success=F(1, 4)),
    )
    assert calibrate_uncertainty(ts, bins=2) == F(1, 4)


def test_all_contamination_controls_fail_closed(qualification, identity, task):
    s, r, a, g, k = qualification

    def runner(cohort, suite, task):
        c = next(c for c in r.cohorts if c.cohort == cohort)
        return replace(c, isolated=False, leaked=True, exposure_overlap=("unit exposed",))

    report = evaluate_agent(
        identity,
        task,
        r.suite,
        runner=runner,
        evaluator="unit-evaluator",
        signer=s.evaluator_keys["unit-evaluator"],
        now=2,
    )
    assert report.contamination and not report.admitted(
        identity, task, now=3, keys=s.evaluator_keys, max_age=100
    )
