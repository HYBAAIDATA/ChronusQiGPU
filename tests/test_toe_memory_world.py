"""Memory, world model, revision, consequence loop, online — §§19-26."""

from __future__ import annotations

import random

from toe.memory import MemoryStore
from toe.receipts import ReceiptLedger
from toe.world_model import (
    MODEL_CONTRADICTED,
    MODEL_SUPPORTED,
    INSUFFICIENT_EVIDENCE,
    OnlineAdapter,
    WorldModel,
    bind_outcome,
)


class TestMemoryTaxonomy:
    def test_namespaces_share_one_store(self):
        m = MemoryStore()
        m.remember("observation", {"t": 0}, causal_tags=["x"])
        m.remember("episodic", {"ep": 1}, causal_tags=["x"])
        m.remember("causal", {"rule": "r"}, causal_tags=["x"])
        # one underlying list, three namespaces
        assert len(m.export()) == 3
        assert len(m.recall(causal_tags=["x"])) == 3

    def test_unknown_namespace_rejected(self):
        m = MemoryStore()
        try:
            m.remember("bogus", {})
        except ValueError:
            return
        raise AssertionError("should have rejected")


class TestLongHorizon:
    def test_decisive_event_survives_1000_distractors(self):
        m = MemoryStore()
        m.remember("episodic", {"fact": "decisive"}, causal_tags=["decision-node"],
                   regime="r0", t=0)
        for i in range(1, 1001):
            m.remember("observation", {"noise": i}, t=i)
        hits = m.recall(causal_tags=["decision-node"])
        assert [h["content"]["fact"] for h in hits] == ["decisive"]
        # recency-only baseline forgets it
        assert m.recent_window_baseline(50, causal_tags=["decision-node"]) == []


class TestConsolidation:
    def test_invariant_links_source_episodes(self):
        m = MemoryStore()

        def sig(c):
            return c.get("pattern")
        for i in range(3):
            m.remember("episodic", {"pattern": "p", "noise": i},
                       causal_tags=["learn"], regime="r0")
        inv = m.consolidate(sig, min_support=2)
        assert len(inv) == 1
        assert inv[0]["content"]["invariant"] == "p"
        assert inv[0]["content"]["support"] == 3
        assert len(inv[0]["source_receipts"]) == 3  # evidence preserved


class TestInvalidation:
    def test_regime_change_stales_derived_keeps_history(self):
        m = MemoryStore()
        m.remember("episodic", {"e": 1}, regime="old", causal_tags=["k"])
        m.remember("causal", {"rule": "stale-rule"}, regime="old", causal_tags=["k"])
        out = m.invalidate("old", "new")
        assert out["staled_records"] == 1
        # stale causal rule no longer recalled
        assert all(
            r["namespace"] != "causal" for r in m.recall(causal_tags=["k"])
        )
        # history preserved verbatim
        assert len(m.export()) == 2
        assert len(m.recall(causal_tags=["k"], include_stale=True)) == 2


class TestWorldModel:
    def _model(self) -> WorldModel:
        return WorldModel(
            nodes=["x", "y"], edges=[("x", "y")], actions={"set_x": "x"}
        )

    def test_predicts_transitions(self):
        wm = self._model()
        wm.dynamics["y"] = {"x": 2.0, "bias": 0.0}
        pred = wm.predict_transition({"x": 1.0, "y": 0.0}, {"x": 3.0})
        assert pred["y"] == 6.0  # dynamics on post-action state
        assert pred["x"] == 3.0  # action pins the node

    def test_observe_records_prediction_error(self):
        wm = self._model()
        obs = wm.observe({"x": 1.0, "y": 0.0}, {"x": 2.0}, {"x": 2.0, "y": 5.0})
        assert "errors" in obs and "receipt_sha256" in obs

    def test_supported_and_contradicted_states(self):
        wm = self._model()
        wm.dynamics["y"] = {"x": 1.0, "bias": 0.0}
        for _ in range(5):
            wm.observe({"x": 1.0, "y": 0.0}, None, {"x": 1.0, "y": 1.01})
        assert wm.assess()["status"] == MODEL_SUPPORTED
        wm2 = self._model()
        for _ in range(5):
            wm2.observe({"x": 1.0, "y": 0.0}, None, {"x": 1.0, "y": 9.9})
        assert wm2.assess()["status"] == MODEL_CONTRADICTED

    def test_insufficient_evidence(self):
        assert self._model().assess()["status"] == INSUFFICIENT_EVIDENCE

    def test_revise_requires_evidence_and_logs(self):
        wm = self._model()
        assert wm.revise(min_evidence=5)["revised"] is False
        for _ in range(8):
            wm.observe({"x": 1.0, "y": 0.0}, None, {"x": 1.0, "y": 3.0})
        assert wm.revise(min_evidence=5)["revised"] is True
        assert len(wm.revisions) == 1  # history appended, not rewritten


class TestConsequenceLoop:
    def test_outcome_binds_exact_decision(self):
        ledger = ReceiptLedger(run_id="t")
        out = bind_outcome(
            "decision-sha-abc",
            {"x": 2.0},
            {"y": 4.0},
            {"y": 5.5},
            ledger,
        )
        assert out["decision_sha256"] == "decision-sha-abc"
        assert out["prediction_error"]["y"] == 1.5
        assert out["largest_error_dimension"] == "y"
        assert out["bound"]


class TestOnlineAdaptation:
    def test_regime_change_detected_and_adapted(self):
        rng = random.Random(0)
        wm = WorldModel(nodes=["x", "y"], edges=[("x", "y")])
        ad = OnlineAdapter(wm, cusum_threshold=3.0, lr=0.1)
        change = 40
        for t in range(80):
            x = rng.uniform(0.5, 1.5)
            coef = 1.0 if t < change else 3.0  # regime flip mid-run
            y = coef * x + rng.gauss(0, 0.01)
            ad.step({"x": x, "y": y}, None, {"x": x, "y": y})
        m = ad.metrics(change_point=change)
        assert m["detected"]
        assert m["detection_latency"] is not None and m["detection_latency"] < 30
        assert m["performance_after_adaptation"] < ad.errors[change + 1]
        # adapted model now predicts the NEW regime's dynamics
        pred_err = abs(wm.predict_transition({"x": 1.0, "y": 0.0}, None)["y"] - 3.0)
        assert pred_err < 1.0
