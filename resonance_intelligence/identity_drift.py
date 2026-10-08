"""Identity persistence, component drift, and distributed fragmentation control.

Component similarity is a Hadamard-test Born probability on the quantum
substrate: each normalized parameter vector is encoded as a quantum state and
the measured quantity is P(0) = (1 + Re<left|right>)/2, the |0> ancilla
outcome of a Hadamard test between the two states. Unlike a swap test
(|<a|b>|^2) this resolves sign, so an inverted value vector still registers
as drift. Computed via kellogg.quantum_tensor.QuantumState — no classical
vector algebra and no invented constants in the measured quantity itself.
"""
from __future__ import annotations

import copy
import math
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

import numpy as np

from hyba_substrate.memory_preservation import canonical_json_bytes, sha256_bytes
from kellogg.quantum_tensor import QuantumState


class DriftType(str, Enum):
    STRATEGY_DRIFT = "strategy_drift"
    PERSONALITY_DRIFT = "personality_drift"
    VALUE_DRIFT = "value_drift"
    BEHAVIORAL_DRIFT = "behavioral_drift"
    FRAGMENTATION_DRIFT = "fragmentation_drift"


class DriftSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _vector(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if not len(array) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a non-empty finite vector")
    norm = float(np.linalg.norm(array))
    if norm <= 1e-12:
        raise ValueError(f"{name} must have non-zero norm")
    result = array / norm
    result.setflags(write=False)
    return result


def _hadamard_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Born probability P(0) of the Hadamard-test ancilla: (1 + Re<l|r>)/2."""
    if left.shape != right.shape:
        raise ValueError("identity vector dimensions differ")
    lstate = QuantumState.from_real_vector(left.tolist())
    rstate = QuantumState.from_real_vector(right.tolist())
    return float(min(1.0, max(0.0, (1.0 + lstate.inner(rstate).re) / 2.0)))


@dataclass(frozen=True)
class IdentitySignature:
    signature_hash: str
    behavioral_vector: np.ndarray
    strategic_vector: np.ndarray
    value_vector: np.ndarray
    timestamp: float
    version: int = 1

    def __post_init__(self) -> None:
        if not self.signature_hash or not math.isfinite(float(self.timestamp)) or self.version <= 0:
            raise ValueError("invalid identity signature metadata")

    def component_similarities(self, other: "IdentitySignature") -> dict[str, float]:
        return {
            "behavioral": _hadamard_similarity(self.behavioral_vector, other.behavioral_vector),
            "strategic": _hadamard_similarity(self.strategic_vector, other.strategic_vector),
            "value": _hadamard_similarity(self.value_vector, other.value_vector),
        }

    def compute_similarity(self, other: "IdentitySignature", weights: Mapping[str, float] | None = None) -> float:
        scores = self.component_similarities(other)
        raw = dict(weights or {"behavioral": 1.0, "strategic": 1.0, "value": 1.0})
        if any(name not in scores or not math.isfinite(float(value)) or float(value) < 0 for name, value in raw.items()):
            raise ValueError("identity weights must be finite, nonnegative, and known")
        total = sum(float(v) for v in raw.values())
        if total <= 0: raise ValueError("identity weights must have positive total")
        return sum(scores[name] * float(weight) for name, weight in raw.items()) / total


@dataclass(frozen=True)
class DriftDetection:
    drift_id: str
    drift_type: DriftType
    severity: DriftSeverity
    detection_time: float
    baseline_hash: str
    current_hash: str
    similarity_score: float
    drift_threshold: float
    component_similarities: Mapping[str, float]
    description: str
    recommended_action: str

    def needs_rollback(self) -> bool:
        return self.severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)


class IdentityDriftControl:
    """Detects identity drift without autonomously rewriting the baseline."""

    def __init__(self, drift_threshold: float = 0.8, rollback_threshold: float = 0.6,
                 signature_window: int = 100) -> None:
        if not 0 < rollback_threshold < drift_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 < rollback < drift <= 1")
        if signature_window <= 0: raise ValueError("signature_window must be positive")
        self.drift_threshold = float(drift_threshold)
        self.rollback_threshold = float(rollback_threshold)
        self.signature_window = int(signature_window)
        self.baseline_signature: IdentitySignature | None = None
        self.signature_history: list[IdentitySignature] = []
        self.drift_detections: list[DriftDetection] = []

    def compute_identity_signature(self, behavioral_params: Sequence[float],
                                   strategic_params: Sequence[float], value_params: Sequence[float],
                                   *, version: int = 1) -> IdentitySignature:
        behavioral = _vector(behavioral_params, "behavioral_params")
        strategic = _vector(strategic_params, "strategic_params")
        values = _vector(value_params, "value_params")
        payload = {"behavioral": behavioral.tolist(), "strategic": strategic.tolist(),
                   "values": values.tolist(), "version": int(version)}
        signature = IdentitySignature(sha256_bytes(canonical_json_bytes(payload)), behavioral,
                                      strategic, values, time.time(), int(version))
        self.signature_history.append(signature)
        self.signature_history = self.signature_history[-self.signature_window:]
        return signature

    def set_baseline(self, signature: IdentitySignature, *, operator_approved: bool = False) -> None:
        if self.baseline_signature is not None and not operator_approved:
            raise PermissionError("replacing an identity baseline requires operator approval")
        self.baseline_signature = copy.deepcopy(signature)

    def check_drift(self, current_signature: IdentitySignature) -> DriftDetection | None:
        if self.baseline_signature is None:
            raise RuntimeError("identity baseline has not been set")
        components = current_signature.component_similarities(self.baseline_signature)
        similarity = current_signature.compute_similarity(self.baseline_signature)
        if similarity >= self.drift_threshold: return None
        if similarity < self.rollback_threshold: severity = DriftSeverity.CRITICAL
        elif similarity < max(self.rollback_threshold, self.drift_threshold - .15): severity = DriftSeverity.HIGH
        elif similarity < self.drift_threshold - .05: severity = DriftSeverity.MEDIUM
        else: severity = DriftSeverity.LOW
        weakest = min(components, key=components.get)
        kind = {"behavioral": DriftType.BEHAVIORAL_DRIFT, "strategic": DriftType.STRATEGY_DRIFT,
                "value": DriftType.VALUE_DRIFT}[weakest]
        action = "operator_review_and_restore_candidate" if severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL) else "monitor"
        detection = DriftDetection("drift-" + uuid.uuid4().hex, kind, severity, time.time(),
            self.baseline_signature.signature_hash, current_signature.signature_hash, similarity,
            self.drift_threshold, components, f"identity similarity {similarity:.6f} below {self.drift_threshold:.6f}; weakest={weakest}", action)
        self.drift_detections.append(detection)
        return detection

    def check_fragmentation(self, node_signatures: Mapping[str, IdentitySignature]) -> dict[str, float]:
        if self.baseline_signature is None: raise RuntimeError("identity baseline has not been set")
        result: dict[str, float] = {}
        for node_id, signature in node_signatures.items():
            if not str(node_id).strip(): raise ValueError("node IDs must be non-empty")
            score = 1.0 - signature.compute_similarity(self.baseline_signature)
            result[str(node_id)] = float(np.clip(score, 0, 1))
        return result

    def baseline_restore_candidate(self, detection: DriftDetection, *, operator_approved: bool = False) -> IdentitySignature:
        if not operator_approved: raise PermissionError("identity restoration requires operator approval")
        if self.baseline_signature is None: raise RuntimeError("identity baseline has not been set")
        if detection not in self.drift_detections: raise ValueError("detection is not in this controller's ledger")
        return copy.deepcopy(self.baseline_signature)

    def get_current_drift_score(self) -> float:
        if self.baseline_signature is None or not self.signature_history: return 0.0
        return 1.0 - self.signature_history[-1].compute_similarity(self.baseline_signature)

    def update_thresholds(self, drift_threshold: float, rollback_threshold: float,
                          *, operator_approved: bool = False) -> None:
        if not operator_approved: raise PermissionError("threshold changes require operator approval")
        if not 0 < rollback_threshold < drift_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 < rollback < drift <= 1")
        self.drift_threshold = float(drift_threshold); self.rollback_threshold = float(rollback_threshold)


__all__ = ["DriftType", "DriftSeverity", "IdentitySignature", "DriftDetection", "IdentityDriftControl"]
