"""Model development, deployment, retrain, and cross-domain transfer.

Training uses the Kellogg exact-tensor linear model. A retrain that loses
accuracy on the held-out set does not replace the live model.
"""

from __future__ import annotations

import threading
import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass

from kellogg.tensor_ml import fit as tensor_fit
from kellogg.tensor_ml import predict as tensor_predict


@dataclass
class ModelRecord:
    name: str
    version: int
    features: tuple[str, ...]
    target: str
    model: object
    rows: int
    live: bool = True
    training_fingerprints: frozenset[str] = frozenset()


@dataclass
class TrainResult:
    record: ModelRecord
    replaced: bool
    rolled_back: bool
    live_version: int
    candidate_accuracy: float | None = None
    live_accuracy: float | None = None
    reason: str | None = None
    evaluation_digest: str | None = None
    evaluation_rows: int = 0
    evaluated_version: int | None = None


def _matrix(rows: list[dict], features: tuple[str, ...]) -> list[list[float]]:
    matrix = []
    for row in rows:
        matrix.append([float(row.get(feature, 0.0) or 0.0) for feature in features])
    return matrix


def _labels(rows: list[dict], target: str) -> list[int]:
    labels = []
    for row in rows:
        value = row[target]
        if value not in (0, 1, "0", "1", False, True):
            raise ValueError(f"{target} must be binary, got {value!r}")
        labels.append(int(value))
    return labels


def _accuracy(model: object, rows: list[dict], features: tuple[str, ...], target: str) -> float:
    if not rows:
        return 0.0
    predicted = tensor_predict(model, _matrix(rows, features))
    actual = _labels(rows, target)
    hits = sum(int(left) == int(right) for left, right in zip(predicted, actual))
    return hits / len(actual)


def _fingerprints(rows: list[dict], features: tuple[str, ...]) -> frozenset[str]:
    matrix = _matrix(rows, features)
    if any(not math.isfinite(value) for row in matrix for value in row):
        raise ValueError("evaluation and training features must be finite")
    return frozenset(
        hashlib.sha256(
            json.dumps(
                [0.0 if value == 0 else value for value in row],
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        for row in matrix
    )


def _evaluation_guard(
    current: ModelRecord,
    rows: list[dict],
    eval_rows: list[dict] | None,
    min_accuracy: float,
) -> None:
    if not eval_rows:
        raise ValueError("automatic promotion requires nonempty held-out evaluation rows")
    if (
        isinstance(min_accuracy, bool)
        or not isinstance(min_accuracy, (int, float))
        or not math.isfinite(min_accuracy)
        or not 0 <= min_accuracy <= 1
    ):
        raise ValueError("min_accuracy must be finite and between zero and one")
    if not rows:
        raise ValueError("automatic promotion requires nonempty training rows")
    for row in [*rows, *eval_rows]:
        if any(feature not in row for feature in current.features):
            raise ValueError("held-out validation requires every model feature")
    if not current.training_fingerprints:
        raise ValueError("live model has no training input provenance")
    candidate_keys = _fingerprints(rows, current.features)
    evaluation_keys = _fingerprints(eval_rows, current.features)
    if evaluation_keys & (candidate_keys | current.training_fingerprints):
        raise ValueError("evaluation rows overlap training model inputs")
    if set(_labels(eval_rows, current.target)) != {0, 1}:
        raise ValueError("held-out binary evaluation requires both classes")
    _labels(rows, current.target)


class ModelRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: dict[str, ModelRecord] = {}
        self._history: dict[str, list[ModelRecord]] = {}

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._live))

    def get(self, name: str) -> ModelRecord:
        try:
            return self._live[name]
        except KeyError as exc:
            raise KeyError(f"no live model {name}") from exc

    def train(self, name: str, rows: list[dict], features: list[str], target: str) -> TrainResult:
        feature_names = tuple(features)
        rows = deepcopy(rows)
        fingerprints = _fingerprints(rows, feature_names)
        model = tensor_fit("exact_linear", _matrix(rows, feature_names), _labels(rows, target))
        with self._lock:
            version = len(self._history.get(name, [])) + 1
            record = ModelRecord(
                name, version, feature_names, target, model, len(rows), True, fingerprints
            )
            previous = self._live.get(name)
            if previous is not None:
                previous.live = False
            self._live[name] = record
            self._history.setdefault(name, []).append(record)
        return TrainResult(record, replaced=previous is not None, rolled_back=False, live_version=version)

    def validate_retrain_evidence(
        self,
        name: str,
        rows: list[dict],
        eval_rows: list[dict] | None,
        min_accuracy: float = 0.8,
    ) -> None:
        _evaluation_guard(self.get(name), rows, eval_rows, min_accuracy)

    def retrain(
        self,
        name: str,
        rows: list[dict],
        eval_rows: list[dict] | None = None,
        *,
        require_evaluation: bool = False,
        min_accuracy: float = 0.8,
    ) -> TrainResult:
        current = self.get(name)
        rows, eval_rows = deepcopy(rows), deepcopy(eval_rows)
        if require_evaluation:
            _evaluation_guard(current, rows, eval_rows, min_accuracy)
        elif eval_rows is not None and not eval_rows:
            raise ValueError("evaluation rows must not be empty")
        feature_names = current.features
        fingerprints = _fingerprints(rows, feature_names)
        candidate = tensor_fit("exact_linear", _matrix(rows, feature_names), _labels(rows, current.target))
        candidate_accuracy = live_accuracy = evaluation_digest = None
        reason = None
        evidence = {
            "evaluation_rows": len(eval_rows) if eval_rows is not None else 0,
            "evaluated_version": current.version,
        }
        if eval_rows is not None:
            candidate_accuracy = _accuracy(candidate, eval_rows, feature_names, current.target)
            live_accuracy = _accuracy(current.model, eval_rows, feature_names, current.target)
            evaluation_digest = hashlib.sha256(
                json.dumps(
                    {
                        "matrix": _matrix(eval_rows, feature_names),
                        "labels": _labels(eval_rows, current.target),
                        "features": feature_names,
                        "target": current.target,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            reason = None
            if candidate_accuracy < live_accuracy:
                reason = "candidate_regressed"
            elif require_evaluation and candidate_accuracy < min_accuracy:
                reason = "candidate_below_accuracy_floor"
        with self._lock:
            live = self._live[name]
            if live is not current:
                return TrainResult(
                    live,
                    replaced=False,
                    rolled_back=True,
                    live_version=live.version,
                    candidate_accuracy=candidate_accuracy,
                    live_accuracy=live_accuracy,
                    reason="live_model_changed_during_evaluation",
                    evaluation_digest=evaluation_digest,
                    **evidence,
                )
            if reason:
                return TrainResult(
                    current,
                    replaced=False,
                    rolled_back=True,
                    live_version=current.version,
                    candidate_accuracy=candidate_accuracy,
                    live_accuracy=live_accuracy,
                    reason=reason,
                    evaluation_digest=evaluation_digest,
                    **evidence,
                )
            version = len(self._history[name]) + 1
            record = ModelRecord(
                name,
                version,
                feature_names,
                current.target,
                candidate,
                len(rows),
                True,
                fingerprints,
            )
            current.live = False
            self._live[name] = record
            self._history[name].append(record)
        return TrainResult(
            record,
            replaced=True,
            rolled_back=False,
            live_version=version,
            candidate_accuracy=candidate_accuracy,
            live_accuracy=live_accuracy,
            evaluation_digest=evaluation_digest,
            **evidence,
        )

    def predict(self, name: str, rows: list[dict]) -> list[int]:
        record = self.get(name)
        predicted = tensor_predict(record.model, _matrix(rows, record.features))
        return [int(value) for value in predicted]

    def predict_aligned(self, name: str, rows: list[dict], features: list[str]) -> dict:
        """Score rows whose columns only partly overlap the trained features.

        Missing trained features are zero. Extra columns are ignored. The
        overlap is the transferred knowledge; it is reported, not assumed.
        """
        record = self.get(name)
        provided = set(features)
        overlap = tuple(feature for feature in record.features if feature in provided)
        missing = tuple(feature for feature in record.features if feature not in provided)
        projected = []
        for row in rows:
            projected.append({feature: row.get(feature, 0.0) for feature in record.features})
        scores = self.predict(name, projected)
        return {
            "scores": scores,
            "overlap": overlap,
            "missing": missing,
            "overlap_ratio": len(overlap) / len(record.features) if record.features else 0.0,
        }

    def importances(self, name: str) -> list[dict]:
        record = self.get(name)
        weights = getattr(record.model, "feature_importances_", None)
        if weights is None:
            return []
        return [
            {"feature": feature, "importance": float(weight)}
            for feature, weight in zip(record.features, weights)
        ]
