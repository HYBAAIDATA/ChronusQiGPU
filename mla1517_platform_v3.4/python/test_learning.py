"""The learning ledger judges learning the way a good teacher would.

Every expected value here is derived by hand from the scoring rule, never
read back from the module: a learner that knows an event happens 9 times in
10 scores 1 - H(0.9) = 0.531 bits per outcome over a coin-flip baseline.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from types import SimpleNamespace

import pytest

from mla1517.knowledge import KnowledgeFabric
from mla1517.learning import (
    DEFAULT_SEEDS,
    LearningLedger,
    Question,
    bernoulli_bits,
    gaussian_bits,
    load_questions,
)
from mla1517.mining.search_plan import CompletionState
from policy_bench import _record

EVENT = Question("event", "Will it happen?", "a test", "probability", "learner", "a coin flip")
LEVEL = Question("level", "How much?", "a test", "quantity", "learner", "a biased guess")
LAW = Question("law", "Does the law hold?", "a test", "law", law="k ~ Poisson(mu)")


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _entropy(p: float) -> float:
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def test_the_seeded_curriculum_loads_and_every_question_says_why():
    questions = load_questions(DEFAULT_SEEDS)
    kinds = {q.id: q.kind for q in questions}
    assert kinds["window.elapsed"] == "quantity" and kinds["window.invalidated"] == "probability"
    assert kinds["shares.follow.work"] == "law"
    assert all(q.why.strip() for q in questions)
    assert all(q.how for q in questions if q.kind == "open")


@pytest.mark.parametrize(
    "entry, reason",
    [
        ({"null": "x"}, "unknown keys"),  # YAML reads a bare `null` key as None
        ({"baseline": None}, "needs a learner and a baseline"),
        ({"kind": "hunch"}, "kind must be one of"),
        ({"why": " "}, "says what it asks and why"),
    ],
)
def test_a_malformed_seed_is_refused(tmp_path, entry, reason):
    base = {"id": "q", "kind": "quantity", "ask": "a", "why": "b", "learner": "l", "baseline": "n"}
    import yaml

    seed = tmp_path / "questions.yaml"
    seed.write_text(
        yaml.safe_dump({"schema": "pythia.questions/1", "questions": [{**base, **entry}]})
    )
    with pytest.raises(ValueError, match=reason):
        load_questions(seed)


def test_the_log_score_in_bits():
    assert bernoulli_bits(True, 0.5) == pytest.approx(1.0)
    assert bernoulli_bits(False, 0.25) == pytest.approx(math.log2(4 / 3))
    assert gaussian_bits(0.0, 0.0, 1.0) == pytest.approx(0.5 * math.log2(2 * math.pi))
    assert gaussian_bits(2.0, 0.0, 1.0) - gaussian_bits(0.0, 0.0, 1.0) == pytest.approx(
        2.0 / math.log(2)
    )


def test_learning_is_earned_then_lost_when_the_world_moves():
    ledger = LearningLedger([EVENT])
    assert ledger.status("event")["status"] == "open"
    blocks = [True] * 9 + [False]  # it happens 9 times in 10
    for happened in blocks * 2:
        ledger.score_probability("event", happened, learner=0.9, null=0.5)
    assert ledger.status("event")["status"] == "not_yet"  # 20 of 30 outcomes
    for happened in blocks:
        ledger.score_probability("event", happened, learner=0.9, null=0.5)
    status = ledger.status("event")
    assert status["status"] == "mastered"
    assert status["skill_bits"] == pytest.approx(1 - _entropy(0.9))  # 0.531 bits per outcome
    assert "a coin flip" in status["explanation"]

    # The world changes (it now happens 1 time in 10); the learner does not.
    for happened in ([True] + [False] * 9) * 2:
        ledger.score_probability("event", happened, learner=0.9, null=0.5)
    status = ledger.status("event")
    assert status["status"] == "regressed" and status["recent_bits"] < 0


def test_knowing_only_what_the_baseline_knows_is_not_learning():
    ledger = LearningLedger([EVENT])
    for i in range(100):
        ledger.score_probability("event", i % 2 == 0, learner=0.5, null=0.5)
    status = ledger.status("event")
    assert status["status"] == "not_yet" and status["skill_bits"] == 0.0


def test_quantity_forecasts_are_judged_for_skill_and_calibration():
    rng = random.Random(1517)
    outcomes = [rng.gauss(10.0, 2.0) for _ in range(400)]
    honest, overconfident = LearningLedger([LEVEL]), LearningLedger([LEVEL])
    for x in outcomes:
        honest.score_quantity("level", x, learner=(10.0, 2.0), null=(12.0, 2.0))
        overconfident.score_quantity("level", x, learner=(10.0, 0.6), null=(12.0, 2.0))
    status = honest.status("level")
    # E[bits(null) - bits(learner)] = bias^2 / (2 sigma^2 ln 2) = 4 / (8 ln 2) = 0.721
    assert status["status"] == "mastered"
    assert status["skill_ci95"][0] < 1 / (2 * math.log(2)) < status["skill_ci95"][1]
    assert status["calibration"] == "calibrated" and 0.85 < status["coverage90"] < 0.95
    # A 90% interval of 0.6 sigma-units covers P(|Z| < 1.645 * 0.3) = 38%.
    assert overconfident.status("level")["calibration"] == "overconfident"
    assert 0.3 < overconfident.status("level")["coverage90"] < 0.46


@pytest.mark.parametrize(
    "observed, status",
    [(0, "anomaly"), (100, "holds"), (150, "anomaly")],  # Garwood 95%: [81.4, 121.6] for 100
)
def test_a_law_is_exposed_to_refutation(observed, status):
    ledger = LearningLedger([LAW])
    assert ledger.status("law")["status"] == "open"
    ledger.law("law", expected=100.0, observed=observed)
    judged = ledger.status("law")
    assert judged["status"] == status
    assert ("ANOMALY" in judged["explanation"]) == (status == "anomaly")


def test_a_fact_question_is_answered_by_what_an_intelligence_publishes():
    fabric = KnowledgeFabric()
    fact_q = Question(
        "rate",
        "How fast?",
        "a test",
        "fact",
        answered_by={"topic": "mining.world", "path": ["routes", "gpu", "rate"]},
    )
    ledger = LearningLedger([fact_q], fabric)
    assert ledger.status("rate")["status"] == "open"
    assert fabric.observe("question.rate").value["ask"] == "How fast?"  # the question is shared
    basis = fabric.publish("d", "device", {"driver": 1}, evidence="measured")
    value = {"routes": {"gpu": {"rate": 0}}}
    fabric.publish("w", "mining.world", value, evidence="measured", depends_on=[basis])
    assert ledger.status("rate")["status"] == "answered" and ledger.status("rate")["answer"] == 0
    fabric.publish("d", "device", {"driver": 2}, evidence="measured")  # its basis moves
    assert ledger.status("rate")["status"] == "stale"


def test_learning_survives_a_restart_through_the_fabric(tmp_path):
    journal = tmp_path / "knowledge.jsonl"
    clock = Clock()
    ledger = LearningLedger([EVENT], KnowledgeFabric(journal), clock=clock)
    for happened in ([True] * 9 + [False]) * 3:
        ledger.score_probability("event", happened, learner=0.9, null=0.5)
    assert ledger.publish() == 1  # first publish is due
    assert ledger.publish() == 0  # nothing changed, not yet due
    restarted = LearningLedger([EVENT], KnowledgeFabric(journal), clock=clock)
    status = restarted.status("event")
    assert status["status"] == "mastered" and status["n"] == 30
    assert status["skill_bits"] == pytest.approx(1 - _entropy(0.9), abs=1e-5)


def test_a_status_change_is_published_at_once():
    clock = Clock()
    fabric = KnowledgeFabric()
    ledger = LearningLedger([LAW], fabric, clock=clock, publish_every_s=300.0)
    ledger.law("law", expected=100.0, observed=100)
    assert ledger.publish() == 1
    clock.t = 10.0
    ledger.law("law", expected=100.0, observed=101)
    assert ledger.publish() == 0  # same status, not yet due
    ledger.law("law", expected=100.0, observed=200)
    assert ledger.publish() == 1  # holds -> anomaly: at once
    assert fabric.observe("learning.law").value["status"] == "anomaly"


def test_the_miner_commits_forecasts_before_a_window_and_scores_them_after():
    from test_pool_only_mining import _pool_only_coordinator
    from manifold_pool_coordinator import PoolEndpoint

    coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", 1, "ckpool")])
    route = coord._execution_route()
    for hashes in (1_000, 1_000, 1_000):  # a directly measured route
        coord.world.observe_execution(
            _record(route, hashes, hashes, 0.002 + hashes * 1e-6, hashes * 1e-6, False)
        )
    coord._sec_per_hash[route] = 3e-6  # the previous window: the baseline's guess
    plan = SimpleNamespace(plan_id="p1", window=2_000)
    coord._commit_forecasts(plan)
    (learner, _), (baseline, _) = coord._forecasts["p1"]["elapsed"]
    assert math.exp(learner) == pytest.approx(0.002 + 2_000 * 1e-6)  # o + h/H
    assert math.exp(baseline) == pytest.approx(2_000 * 3e-6)

    done = replace(_record(route, 2_000, 2_000, 0.004, 0.002, False), plan_id="p1")
    coord._score_forecasts(done)
    for qid in ("window.elapsed", "window.invalidated"):
        assert coord.learning.status(qid)["n"] == 1
    assert "p1" not in coord._forecasts

    # A window cut short by a new job answers the invalidation question only.
    coord._commit_forecasts(SimpleNamespace(plan_id="p2", window=2_000))
    cut = replace(_record(route, 2_000, 700, 0.001, 0.0007, True), plan_id="p2")
    assert cut.completion_state is CompletionState.INVALIDATED
    coord._score_forecasts(cut)
    assert coord.learning.status("window.elapsed")["n"] == 1
    assert coord.learning.status("window.invalidated")["n"] == 2


def test_a_forecaster_is_judged_with_the_spread_its_own_errors_earn():
    from mla1517.learning import ResidualScale

    scale = ResidualScale()
    assert scale.sigma == 0.5  # no record yet: a humble default
    for _ in range(4):
        scale.observe(0.0)
    assert scale.sigma == 0.5  # four errors are not yet a record
    scale.observe(0.0)
    assert scale.sigma == 0.01  # perfect so far: the floor, never zero
    quick = ResidualScale(half_life=1.0)  # each older error weighs half as much
    for error in (1, 1, 1, 1, 1, 3):
        quick.observe(error)
    # w = 1 + 1/2 + ... + 1/32 = 1.96875; sq = 9 + (1/2 + ... + 1/32) = 9.96875
    assert quick.sigma == pytest.approx(math.sqrt(9.96875 / 1.96875))
    slow = ResidualScale()  # half-life 50 outcomes
    for error in (1, 1, 1, 1, 1, 3):
        slow.observe(error)
    d = 0.5 ** (1 / 50)
    w = sum(d**i for i in range(6))
    assert slow.sigma == pytest.approx(math.sqrt((9 + sum(d**i for i in range(1, 6))) / w))


def test_scores_at_their_limits():
    assert bernoulli_bits(True, 0.0) == pytest.approx(math.log2(1e6))  # never infinite
    assert bernoulli_bits(False, 1.0) == pytest.approx(math.log2(1e6))
    assert gaussian_bits(1.0, 0.0, 2.0) == pytest.approx(
        (0.5 * math.log(2 * math.pi * 4) + 1 / 8) / math.log(2)
    )
    assert math.isfinite(gaussian_bits(0.0, 0.0, 0.0))


def test_the_record_weighs_recent_outcomes_more_and_reports_an_exact_interval():
    fast = Question("q", "a", "b", "probability", "l", "n", min_n=1, recent_half_life=1.0)
    ledger = LearningLedger([fast, EVENT])
    one = ledger.status("event")
    assert one["n"] == 0 and one["status"] == "open"
    ledger.score("q", 0.0, 1.0)
    first = ledger.status("q")
    assert math.isinf(first["skill_ci95"][0]) and math.isinf(first["skill_ci95"][1])
    ledger.score("q", 0.0, 2.0)
    status = ledger.status("q")
    # diffs 1, 2: mean 1.5, variance 1/4, se sqrt(1/8); recent (1/2 + 2) / (1/2 + 1)
    assert status["skill_bits"] == 1.5 and status["evidence_bits"] == 3.0
    se = (0.25 / 2) ** 0.5
    assert status["skill_ci95"] == pytest.approx([1.5 - 1.959964 * se, 1.5 + 1.959964 * se])
    assert status["recent_bits"] == pytest.approx(2.5 / 1.5)
    assert status["status"] == "mastered"  # two agreeing outcomes are enough when min_n is 1
    default = LearningLedger([EVENT])
    default.score("event", 0.0, 1.0)
    default.score("event", 0.0, 3.0)
    d = 0.5 ** (1 / 100)
    assert default.status("event")["recent_bits"] == pytest.approx((d + 3) / (d + 1))


def test_not_yet_says_whether_evidence_or_skill_is_missing():
    ledger = LearningLedger([EVENT])
    for i in range(10):
        ledger.score_probability("event", i % 2 == 0, learner=0.5, null=0.5)
    assert "10 of 30 outcomes needed" in ledger.status("event")["explanation"]
    for i in range(20):
        ledger.score_probability("event", i % 2 == 0, learner=0.5, null=0.5)
    assert "does not reliably beat its baseline" in ledger.status("event")["explanation"]


@pytest.mark.parametrize(
    "inside, total, calibration",
    [
        (40, 50, "calibrated"),
        (39, 50, "overconfident"),
        (97, 100, "calibrated"),
        (49, 50, "underconfident"),
        (20, 49, "calibrated"),
    ],
)
def test_calibration_thresholds(inside, total, calibration):
    from mla1517.learning import _Z90

    ledger = LearningLedger([LEVEL])
    for i in range(total):
        # On the interval's edge counts as inside; far outside does not.
        outcome = _Z90 if i < inside else 10.0
        ledger.score_quantity("level", outcome, learner=(0.0, 1.0), null=(0.0, 1.0))
    status = ledger.status("level")
    assert status["calibration"] == calibration
    assert status["coverage90"] == pytest.approx(inside / total)


def test_a_law_with_little_work_is_already_tested():
    ledger = LearningLedger([LAW])
    ledger.law("law", expected=0.5, observed=0)  # P(0 | 0.5) is not surprising
    assert ledger.status("law")["status"] == "holds"
    ledger.law("law", expected=100.0, observed=150)
    assert ledger.status("law")["ratio"] == 1.5


def test_a_fact_without_the_named_field_does_not_answer():
    fabric = KnowledgeFabric()
    q = Question("r", "a", "b", "fact", answered_by={"topic": "t", "path": ["x", "y"]})
    ledger = LearningLedger([q], fabric)
    fabric.publish("s", "t", {"x": {"z": 1}}, evidence="measured")
    assert ledger.status("r")["status"] == "open"


def test_the_publishing_schedule():
    assert LearningLedger([EVENT]).publish() == 0  # no fabric: nothing to publish to
    clock = Clock()
    ledger = LearningLedger([EVENT], KnowledgeFabric(), clock=clock)  # every 300 s by default
    clock.t = 100.0
    assert ledger.publish() == 1
    clock.t = 350.0
    assert ledger.publish() == 0
    clock.t = 400.0
    assert ledger.publish() == 1


@pytest.mark.parametrize(
    "document, reason",
    [
        ({"schema": "pythia.questions/0", "questions": []}, "schema must be"),
        (
            {
                "schema": "pythia.questions/1",
                "questions": [
                    {"id": "f", "kind": "fact", "ask": "a", "why": "b", "answered_by": {}}
                ],
            },
            "names the topic",
        ),
        (
            {
                "schema": "pythia.questions/1",
                "questions": [
                    {
                        "id": "f",
                        "kind": "fact",
                        "ask": "a",
                        "why": "b",
                        "answered_by": {"path": ["x"]},
                    }
                ],
            },
            "names the topic",
        ),
        (
            {
                "schema": "pythia.questions/1",
                "questions": [{"id": "l", "kind": "law", "ask": "a", "why": "b"}],
            },
            "states its law",
        ),
        (
            {
                "schema": "pythia.questions/1",
                "questions": [{"id": "o", "kind": "open", "ask": "a", "why": "b"}] * 2,
            },
            "duplicate",
        ),
    ],
)
def test_a_malformed_curriculum_is_refused(tmp_path, document, reason):
    import yaml

    seed = tmp_path / "questions.yaml"
    seed.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match=reason):
        load_questions(seed)
    fact = {"id": "f", "kind": "fact", "ask": "a", "why": "b", "answered_by": {"topic": "t"}}
    seed.write_text(yaml.safe_dump({"schema": "pythia.questions/1", "questions": [fact]}))
    assert load_questions(seed)[0].answered_by == {"topic": "t"}


def test_after_a_setback_recovering_is_not_yet_mastery_and_not_regression():
    fast = Question("q", "a", "b", "probability", "l", "n", min_n=1, recent_half_life=1.0)
    ledger = LearningLedger([fast])
    for diff in (1.0, 1.0):
        ledger.score("q", 0.0, diff)
    assert ledger.status("q")["status"] == "mastered"
    ledger.score("q", 10.0, 0.0)  # a setback of 10 bits
    assert ledger.status("q")["status"] == "regressed"
    for _ in range(4):
        ledger.score("q", 0.0, 0.5)
    status = ledger.status("q")
    # Recently positive again (+0.18 bits), but the record (-0.86 bits) is not.
    assert 0 < status["recent_bits"] < 1 and status["skill_bits"] < 0
    assert status["status"] == "not_yet"


def test_questions_are_immutable_once_seeded():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        EVENT.kind = "law"


def test_the_miner_answers_the_three_formerly_open_questions():
    from test_pool_only_mining import _pool_only_coordinator
    from manifold_pool_coordinator import PoolEndpoint

    coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", 1, "ckpool")])
    route = coord._execution_route()

    # precompute.depth: nothing to forecast before a window has run...
    assert coord._forecast_plan_ready() is None
    coord._observe_recovery_effect(_record(route, 1_000, 1_000, 0.010, 0.0, False))
    coord.world.observe_plan_latency(0.001)
    forecast = coord._forecast_plan_ready()
    assert forecast is not None and forecast[1] == 0.5  # base rate: (0 + 1) / (0 + 2)
    coord._score_plan_ready(forecast, None)  # a plan was ready
    coord._score_plan_ready(coord._forecast_plan_ready(), "queue_empty")
    coord._score_plan_ready(coord._forecast_plan_ready(), "recovery")  # not a depth question
    assert coord._ready_record == [1, 2]
    assert coord.learning.status("precompute.depth")["n"] == 2

    # recovery.effect: sixteen windows before, the recovery, sixteen after.
    for _ in range(16):
        coord._observe_recovery_effect(_record(route, 1_000, 1_000, 0.020, 0.0, False))
    from mla1517.mining.recovery_authority import RecoveryRecord, RecoveryState

    record = RecoveryRecord("r1", "salamander", ("THROTTLE",), "test", RecoveryState.VERIFIED)
    coord._on_recovery_event("recovery_verified", record)
    for _ in range(16):
        coord._observe_recovery_effect(_record(route, 1_000, 1_000, 0.010, 0.0, False))
    effect = coord.knowledge.observe("salamander.recovery_effect").value
    assert effect["by_commands"]["THROTTLE"]["last_ratio"] == pytest.approx(2.0)
    assert coord.learning.status("recovery.effect")["status"] == "answered"

    # policy.promotion: a twin-round winner goes into shadow and says so.
    coord.knowledge.publish(
        "discovery.engine",
        "promotion.candidate",
        {"levers": ["envelope_half"], "verdict": "shadow"},
        evidence="simulated",
    )
    coord._follow_promotion()
    assert coord._shadow is not None and coord._shadow.levers == ("envelope_half",)
    assert coord.knowledge.observe("promotion.status").value["status"] == "shadow"
    assert coord.learning.status("policy.promotion")["status"] == "answered"
