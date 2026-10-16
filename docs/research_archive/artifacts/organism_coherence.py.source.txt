"""Operational organism-level coherence measurement.

Agreement alone is insufficient: an integrated system must add measurable
value beyond its best isolated component, propagate perturbations consistently,
recover after disturbance, and retain meta-cognitive trust.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class OrganismCoherenceSnapshot:
    module_agreement: float
    temporal_stability: float
    integration_gain: float
    perturbation_consistency: float
    recovery_score: float
    meta_trust: float
    aggregate_coherence: float
    synergy_present: bool
    coherence_gate_passed: bool


class OrganismCoherenceEvaluator:
    def __init__(self, threshold: float = 0.7, min_integration_gain: float = 0.01):
        if not 0 <= threshold <= 1 or min_integration_gain < 0:
            raise ValueError("invalid coherence thresholds")
        self.threshold = float(threshold)
        self.min_integration_gain = float(min_integration_gain)
        self.history: list[OrganismCoherenceSnapshot] = []

    @staticmethod
    def _series(values: Sequence[float], name: str) -> np.ndarray:
        array = np.asarray(values, float).reshape(-1)
        if not len(array) or not np.all(np.isfinite(array)) or np.any((array < 0) | (array > 1)):
            raise ValueError(f"{name} must be non-empty finite [0,1] values")
        return array

    def evaluate(
        self,
        module_series: Mapping[str, Sequence[float]],
        integrated_series: Sequence[float],
        isolated_component_series: Mapping[str, Sequence[float]],
        perturbation_deltas: Mapping[str, Sequence[float]],
        *,
        recovery_before: float,
        recovery_after: float,
        meta_trust: float,
    ) -> OrganismCoherenceSnapshot:
        if len(module_series) < 2 or not isolated_component_series or len(perturbation_deltas) < 2:
            raise ValueError("multiple modules, components, and perturbation traces required")
        integrated = self._series(integrated_series, "integrated_series")
        n = len(integrated)
        modules = {k: self._series(v, f"module:{k}") for k, v in module_series.items()}
        isolated = {k: self._series(v, f"isolated:{k}") for k, v in isolated_component_series.items()}
        perturb = {k: self._series(v, f"perturbation:{k}") for k, v in perturbation_deltas.items()}
        if any(len(v) != n for v in (*modules.values(), *isolated.values(), *perturb.values())):
            raise ValueError("all series must have equal length")
        for name, value in (("recovery_before", recovery_before), ("recovery_after", recovery_after), ("meta_trust", meta_trust)):
            if not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
                raise ValueError(f"{name} must be in [0,1]")

        matrix = np.vstack(list(modules.values()))
        agreement = float(np.clip(1 - 2 * np.mean(np.std(matrix, axis=0)), 0, 1))
        stability = float(np.clip(1 - np.mean(np.abs(np.diff(integrated))) if n > 1 else 1, 0, 1))
        best_isolated = max(float(np.mean(v)) for v in isolated.values())
        gain = float(np.mean(integrated) - best_isolated)
        synergy = gain >= self.min_integration_gain
        perturbation_matrix = np.vstack(list(perturb.values()))
        scale = max(float(np.mean(np.abs(perturbation_matrix))), 1e-12)
        consistency = float(np.clip(1 - float(np.mean(np.std(perturbation_matrix, axis=0))) / scale, 0, 1))
        recovery = float(recovery_after)
        trust = float(meta_trust)
        aggregate = float(np.mean([agreement, stability, max(0.0, min(1.0, gain)), consistency, recovery, trust]))
        gate = bool(
            synergy
            and agreement >= self.threshold
            and stability >= self.threshold
            and consistency >= self.threshold
            and recovery >= self.threshold
            and trust >= self.threshold
        )
        snapshot = OrganismCoherenceSnapshot(
            agreement, stability, gain, consistency, recovery, trust,
            aggregate, synergy, gate,
        )
        self.history.append(snapshot)
        return snapshot


__all__ = ["OrganismCoherenceSnapshot", "OrganismCoherenceEvaluator"]
