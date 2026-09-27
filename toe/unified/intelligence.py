"""Model development, deployment, retrain, and cross-domain transfer.

Training uses the Kellogg exact-tensor linear model. A retrain that loses
accuracy on the held-out set does not replace the live model.
"""

from __future__ import annotations

import threading
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


@dataclass
class TrainResult:
    record: ModelRecord
    replaced: bool
    rolled_back: bool
    live_version: int
    candidate_accuracy: float | None = None
    live_accuracy: float | None = None


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
        model = tensor_fit("exact_linear", _matrix(rows, feature_names), _labels(rows, target))
        with self._lock:
            version = len(self._history.get(name, [])) + 1
            record = ModelRecord(name, version, feature_names, target, model, len(rows), True)
            previous = self._live.get(name)
            if previous is not None:
                previous.live = False
            self._live[name] = record
            self._history.setdefault(name, []).append(record)
        return TrainResult(record, replaced=previous is not None, rolled_back=False, live_version=version)

    def retrain(self, name: str, rows: list[dict], eval_rows: list[dict] | None = None) -> TrainResult:
        current = self.get(name)
        feature_names = current.features
        candidate = tensor_fit("exact_linear", _matrix(rows, feature_names), _labels(rows, current.target))
        candidate_accuracy = None
        live_accuracy = None
        if eval_rows:
            candidate_accuracy = _accuracy(candidate, eval_rows, feature_names, current.target)
            live_accuracy = _accuracy(current.model, eval_rows, feature_names, current.target)
            if candidate_accuracy < live_accuracy:
                return TrainResult(
                    current,
                    replaced=False,
                    rolled_back=True,
                    live_version=current.version,
                    candidate_accuracy=candidate_accuracy,
                    live_accuracy=live_accuracy,
                )
        with self._lock:
            version = len(self._history[name]) + 1
            record = ModelRecord(name, version, feature_names, current.target, candidate, len(rows), True)
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
