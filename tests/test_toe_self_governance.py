"""Adversarial battery, self-check, promotion boundary — §§39-41."""

from __future__ import annotations

from toe.self_governance import (
    adversarial_battery,
    promotion_decision,
    self_check,
)


class TestAdversarialBattery:
    def test_battery_runs_and_reports(self):
        out = adversarial_battery()
        attacks = {p["attack"] for p in out["probes"]}
        for expected in (
            "latent confounder",
            "collider bias",
            "missing evidence",
            "regime change",
            "near-tie decision",
            "precision-sensitive decision",
            "adversarial action choice",
            "contradictory observations",
            "false causal graph",
        ):
            assert expected in attacks

    def test_no_probe_is_vulnerable(self):
        out = adversarial_battery()
        # The battery's honest claim: nothing measured comes back
        # 'vulnerable' — refusals and detections are the capability.
        assert out["vulnerable"] == []
        assert out["counts"]["refused"] >= 2
        assert out["counts"]["detected"] >= 3


class TestSelfCheck:
    def test_causal_without_identifiability_withheld(self):
        out = self_check(
            "causal", {"identifiability_verdict": "NOT_IDENTIFIED",
                       "estimate_released": False}
        )
        assert out["released"] is False
        assert out["degraded"]

    def test_causal_identified_released(self):
        out = self_check(
            "causal", {"identifiability_verdict": "IDENTIFIED"}
        )
        assert out["released"] is True

    def test_action_with_violation_withheld(self):
        out = self_check(
            "action", {"violated_constraints": ["cap"]}
        )
        assert out["released"] is False

    def test_explanation_below_faithfulness_floor(self):
        out = self_check("explanation", {"faithfulness": 0.2})
        assert out["released"] is False

    def test_receipt_chain_verification(self):
        assert self_check("receipt", {"verify_ok": True})["released"]
        assert not self_check("receipt", {"verify_ok": False})["released"]

    def test_unknown_kind_withheld(self):
        assert not self_check("mystery", {})["released"]


class TestPromotionBoundary:
    def test_measured_improvement_promotes(self):
        out = promotion_decision(
            baseline_metrics={"accuracy": 0.8},
            candidate_metrics={"accuracy": 0.9},
            higher_is_better=["accuracy"],
            regression_suite_passed=True,
        )
        assert out["promoted"] is True

    def test_regression_reverts(self):
        out = promotion_decision(
            baseline_metrics={"accuracy": 0.8},
            candidate_metrics={"accuracy": 0.9},
            higher_is_better=["accuracy"],
            regression_suite_passed=False,
        )
        assert out["promoted"] is False

    def test_no_improvement_reverts(self):
        out = promotion_decision(
            baseline_metrics={"accuracy": 0.8},
            candidate_metrics={"accuracy": 0.8},
            higher_is_better=["accuracy"],
            regression_suite_passed=True,
        )
        assert out["promoted"] is False

    def test_metric_regression_reverts(self):
        out = promotion_decision(
            baseline_metrics={"accuracy": 0.8, "latency": 0.5},
            candidate_metrics={"accuracy": 0.9, "latency": 0.4},
            higher_is_better=["accuracy", "latency"],
            regression_suite_passed=True,
        )
        assert out["promoted"] is False

    def test_new_vulnerability_blocks(self):
        out = promotion_decision(
            baseline_metrics={"accuracy": 0.8},
            candidate_metrics={"accuracy": 0.99},
            higher_is_better=["accuracy"],
            regression_suite_passed=True,
            adversarial_delta={"collider bias": "vulnerable"},
        )
        assert out["promoted"] is False
