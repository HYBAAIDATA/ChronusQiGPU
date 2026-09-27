"""Train, rollback, transfer, and the exact_linear identity."""

from toe.unified import UnifiedAnalyticsPlatform


def _rows():
    return [{"amount": float(i), "tenure": float(i % 3), "defaulted": int(i > 5)} for i in range(12)]


def test_train_retrain_rollback():
    platform = UnifiedAnalyticsPlatform()
    rows = _rows()
    trained = platform.train("risk", rows, ["amount", "tenure"], "defaulted")
    assert trained.record.version == 1
    assert trained.record.model.model_family == "exact_linear"
    flipped = [{**row, "defaulted": 1 - row["defaulted"]} for row in rows]
    result = platform.retrain("risk", flipped, eval_rows=rows)
    assert result.rolled_back is True
    assert result.live_version == 1
    assert platform.predict("risk", rows)


def test_transfer_overlap():
    platform = UnifiedAnalyticsPlatform()
    platform.train("risk", _rows(), ["amount", "tenure"], "defaulted")
    transferred = platform.transfer("risk", [{"amount": 9.0}], ["amount"])
    assert transferred["missing"] == ("tenure",)
    assert transferred["overlap"] == ("amount",)
    assert transferred["overlap_ratio"] == 0.5
    assert set(transferred["scores"]) <= {0, 1}


def test_model_family_is_exact_linear():
    platform = UnifiedAnalyticsPlatform()
    trained = platform.train("risk", _rows(), ["amount"], "defaulted")
    assert trained.record.model.model_family == "exact_linear"
    assert trained.record.model.weights_exact_
