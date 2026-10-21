"""Held-out promotion using the actual canonical exact_linear implementation."""

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from toe.unified.intelligence import ModelRegistry


def rows(flipped=False, offset=0.0):
    return [{"x": i + offset, "label": int(i > 5) ^ int(flipped)} for i in range(12)]


def registry():
    models = ModelRegistry()
    models.train("m", rows(), ["x"], "label")
    return models


def test_missing_evaluation_cannot_promote_or_add_history():
    models = registry()
    with pytest.raises(ValueError, match="held-out"):
        models.retrain("m", rows(True), require_evaluation=True)
    assert models.get("m").version == 1
    assert len(models._history["m"]) == 1


@pytest.mark.parametrize("offset", [0.0, 0.25])
def test_evaluation_must_be_disjoint_from_both_training_sets_ignoring_row_ids(offset):
    models = registry()
    candidate = rows(True, offset=0.25)
    evaluation = [{**row, "irrelevant_id": f"new-{i}"} for i, row in enumerate(rows(True, offset))]
    with pytest.raises(ValueError, match="overlap"):
        models.retrain("m", candidate, evaluation, require_evaluation=True)
    assert models.get("m").version == 1


@pytest.mark.parametrize("floor", [float("nan"), -0.1, 1.1, True])
def test_invalid_accuracy_floor_rejected_before_training(floor):
    models = registry()
    with pytest.raises(ValueError, match="min_accuracy"):
        models.retrain(
            "m", rows(True), rows(True, 0.25), require_evaluation=True, min_accuracy=floor
        )
    assert len(models._history["m"]) == 1


def test_real_candidate_regression_retains_live_model():
    models = registry()
    result = models.retrain("m", rows(True), rows(False, 0.25), require_evaluation=True)
    assert result.rolled_back and not result.replaced
    assert result.reason == "candidate_regressed"
    assert result.candidate_accuracy == 0.0 and result.live_accuracy == 1.0
    assert len(result.evaluation_digest) == 64
    assert models.get("m").version == 1


def test_equal_but_poor_candidates_do_not_pass_the_accuracy_floor():
    models = registry()
    evaluation = [{"x": i + 0.25, "label": i % 2} for i in range(12)]
    result = models.retrain("m", rows(True), evaluation, require_evaluation=True)
    assert result.reason == "candidate_below_accuracy_floor"
    assert result.live_accuracy == result.candidate_accuracy == 0.5
    assert models.get("m").version == 1


def test_real_candidate_passes_disjoint_held_out_evaluation():
    models = registry()
    result = models.retrain("m", rows(True), rows(True, 0.25), require_evaluation=True)
    assert result.replaced and not result.rolled_back
    assert result.candidate_accuracy == 1.0 and result.live_accuracy == 0.0
    assert result.evaluation_rows == 12 and result.evaluated_version == 1
    assert models.get("m").version == 2
    assert models.get("m").model.model_family == "exact_linear"


def test_candidate_cannot_overwrite_a_concurrently_replaced_live_version(monkeypatch):
    import toe.unified.intelligence as intelligence

    models = registry()
    fitted = threading.Event()
    resume = threading.Event()
    main_thread = threading.current_thread()
    original = intelligence.tensor_fit

    def fit(*args, **kwargs):
        candidate = original(*args, **kwargs)
        if threading.current_thread() is not main_thread:
            fitted.set()
            assert resume.wait(5)
        return candidate

    monkeypatch.setattr(intelligence, "tensor_fit", fit)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            models.retrain, "m", rows(True), rows(True, 0.25), require_evaluation=True
        )
        try:
            assert fitted.wait(5)
            replacement = models.train("m", rows(), ["x"], "label")
        finally:
            resume.set()
        result = future.result(timeout=5)
    assert result.reason == "live_model_changed_during_evaluation"
    assert result.replaced is False
    assert models.get("m") is replacement.record
    assert models.get("m").version == 2
    assert len(models._history["m"]) == 2


def test_facade_watch_without_holdout_is_blocked_not_promoted():
    from toe.unified import UnifiedAnalyticsPlatform

    platform = UnifiedAnalyticsPlatform()
    platform.train("m", rows(), ["x"], "label")
    platform.watch("m", rows(True))
    platform.monitor.tick_once()
    assert platform.models.get("m").version == 1
    assert platform.drift_retrains == 0
    assert platform.health()["drift"]["state"] == "blocked_missing_evaluation"


def test_facade_monitor_promotes_only_an_evaluated_candidate():
    from toe.unified import UnifiedAnalyticsPlatform

    platform = UnifiedAnalyticsPlatform()
    platform.train("m", rows(), ["x"], "label")
    training, evaluation = rows(True), rows(True, 0.25)
    platform.watch("m", training, eval_rows=evaluation)
    # The watch owns detached evidence, not aliases to mutable caller lists.
    training[0]["label"] = 99
    evaluation[0]["label"] = 99
    platform.monitor.tick_once()
    assert platform.models.get("m").version == 2
    assert platform.drift_retrains == 1
    status = platform.health()["drift"]
    assert status["state"] == "promoted" and status["evaluation_rows"] == 12
    assert status["candidate_accuracy"] == 1.0
    assert len(status["evaluation_digest"]) == 64


@pytest.mark.parametrize("defect", ["missing_feature", "nonfinite", "one_class"])
def test_invalid_heldout_evidence_cannot_change_the_registry(defect):
    models = registry()
    evaluation = rows(True, 0.25)
    if defect == "missing_feature":
        del evaluation[0]["x"]
    elif defect == "nonfinite":
        evaluation[0]["x"] = float("nan")
    else:
        for row in evaluation:
            row["label"] = 0
    with pytest.raises(ValueError):
        models.retrain("m", rows(True), evaluation, require_evaluation=True)
    assert models.get("m").version == 1
    assert len(models._history["m"]) == 1
