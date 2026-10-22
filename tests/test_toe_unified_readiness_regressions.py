"""Deterministic regression for live-model mutation during held-out scoring."""
from toe.unified import UnifiedAnalyticsPlatform
from toe.unified import intelligence


def test_retrain_never_scores_mutable_live_model(monkeypatch):
    platform = UnifiedAnalyticsPlatform()
    rows = [{"amount": float(i), "defaulted": int(i > 5)} for i in range(12)]
    platform.train("risk", rows, ["amount"], "defaulted")
    live = platform.models._live["risk"].model
    original = intelligence._accuracy
    evaluated = []

    def score(model, *args):
        assert model is not live, "held-out scoring must not mutate the published model"
        evaluated.append(model)
        return original(model, *args)

    monkeypatch.setattr(intelligence, "_accuracy", score)
    held_out = [{"amount": float(i) + .25, "defaulted": int(i > 5)} for i in range(12)]
    result = platform.retrain("risk", rows, eval_rows=held_out)
    assert result.live_version == 2
    assert len(evaluated) == 2
