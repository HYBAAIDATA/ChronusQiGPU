"""
PYTHAGORAS — META-EVOLUTION CONTROLLER
Adaptive tuning of mutation rate, primitive weights, and operator distribution.

Features:
- Real-time adaptive mutation rate (exploit on progress, explore on stall)
- Exponential moving average primitive weight tracking
- ENH-04: Simulated annealing escape from degenerate fitness manifolds
- ENH-09: Phase-transition tagging telemetry for discontinuous fitness leaps
- ENH-10: Primitive provenance tracking across the evolutionary trajectory
"""

from __future__ import annotations

import math
import random
import hashlib
import json
from typing import Any, Dict, List, Optional
import numpy as np


class MetaEvolutionController:
    """
    Adaptive layer that dynamically tunes the evolutionary strategy:
    - Mutation rate
    - Primitive weights
    - Operator probability distribution
    - Simulated annealing escape mechanism (ENH-04)
    - Phase-transition detection & tagging (ENH-09)
    - Provenance tracking (ENH-10)
    """

    def __init__(
        self,
        initial_mutation_rate: float = 0.15,
        phase_transition_threshold: float = 0.05,
        stall_threshold: int = 3,
        initial_temperature: float = 0.5,
        cooling_rate: float = 0.85,
        random_seed: int = 0,
    ):
        self.mutation_rate = float(initial_mutation_rate)
        self.primitive_weights: Dict[str, float] = {}
        self.operator_distribution: Dict[str, float] = {}
        self.history: List[Dict[str, Any]] = []

        # ENH-04: Simulated Annealing Escape
        self.stall_threshold = stall_threshold
        self.stall_count = 0
        self.temperature = float(initial_temperature)
        self.cooling_rate = float(cooling_rate)
        self.in_annealing_mode = False

        # ENH-09: Phase-Transition Tagging
        self.phase_transition_threshold = float(phase_transition_threshold)
        self.phase_transitions: List[Dict[str, Any]] = []

        # ENH-10: Primitive Provenance Tracking
        self.provenance_log: List[Dict[str, Any]] = []
        self._rng = random.Random(int(random_seed))

    def update(
        self,
        generation: int,
        fitness_history: List[float],
        primitive_gains: Dict[str, float],
        file_id: str = "default",
        geometry_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update meta-parameters based on observed performance in the current generation.
        """
        recent_gain = 0.0
        if len(fitness_history) >= 2:
            recent_gain = fitness_history[-1] - fitness_history[-2]

            if recent_gain > 0.01:
                # Progress observed: exploit by reducing mutation rate slightly
                self.mutation_rate *= 0.95
                self.stall_count = 0
                self.in_annealing_mode = False
            else:
                # Progress stalled: explore by increasing mutation rate
                self.mutation_rate *= 1.05
                self.stall_count += 1

        self.mutation_rate = float(np.clip(self.mutation_rate, 0.01, 0.50))

        # Check for simulated annealing activation (ENH-04)
        if self.stall_count >= self.stall_threshold:
            self.in_annealing_mode = True
            self.temperature = max(0.01, self.temperature * self.cooling_rate)

        # ENH-09: Phase-Transition Detection
        is_phase_trans = False
        triggering_primitive = None
        if recent_gain >= self.phase_transition_threshold:
            is_phase_trans = True
            # Determine which primitive contributed most
            if primitive_gains:
                triggering_primitive = max(primitive_gains, key=primitive_gains.get)

            transition_record = {
                "generation": generation,
                "delta_phi": recent_gain,
                "file_id": file_id,
                "triggering_primitive": triggering_primitive,
                "mutation_rate": self.mutation_rate,
                "geometry": dict(geometry_state) if geometry_state else {},
            }
            self.phase_transitions.append(transition_record)

        # ENH-10: Record Provenance for all observed gains
        for prim, gain in primitive_gains.items():
            prov_record = {
                "file_id": file_id,
                "generation": generation,
                "primitive": prim,
                "gain": gain,
                "is_phase_transition": (
                    is_phase_trans and prim == triggering_primitive
                ),
            }
            self._append_provenance(prov_record)

            # Update primitive weights (EMA)
            if prim not in self.primitive_weights:
                self.primitive_weights[prim] = 0.5
            self.primitive_weights[prim] = float(
                0.9 * self.primitive_weights[prim] + 0.1 * max(0.0, gain * 10.0)
            )

        # Update operator distribution
        total_w = sum(self.primitive_weights.values())
        if total_w > 0:
            self.operator_distribution = {
                k: float(v / total_w) for k, v in self.primitive_weights.items()
            }

        record = {
            "generation": generation,
            "mutation_rate": self.mutation_rate,
            "primitive_weights": dict(self.primitive_weights),
            "operator_distribution": dict(self.operator_distribution),
            "stall_count": self.stall_count,
            "in_annealing_mode": self.in_annealing_mode,
            "temperature": self.temperature,
            "phase_transition": is_phase_trans,
        }
        self.history.append(record)
        return record

    def should_accept(self, delta_phi: float) -> bool:
        """
        ENH-04: Simulated annealing acceptance check.
        Strict improvement is always accepted.
        Worse solutions are accepted with probability exp(delta_phi / T)
        when in simulated annealing mode.
        """
        if delta_phi >= 0.0:
            return True
        if not self.in_annealing_mode:
            return False

        acceptance_prob = math.exp(delta_phi / max(1e-4, self.temperature))
        return self._rng.random() < acceptance_prob

    def _append_provenance(self, record: Dict[str, Any]) -> None:
        """Append a tamper-evident provenance event."""
        previous_hash = (
            self.provenance_log[-1].get("event_hash", "LEGACY")
            if self.provenance_log
            else "GENESIS"
        )
        payload = {
            "sequence": len(self.provenance_log) + 1,
            **record,
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payload["event_hash"] = hashlib.sha256(canonical).hexdigest()
        self.provenance_log.append(payload)

    def get_state(self) -> Dict[str, Any]:
        """Return snapshot of current meta-evolutionary state."""
        return {
            "mutation_rate": self.mutation_rate,
            "primitive_weights": dict(self.primitive_weights),
            "operator_distribution": dict(self.operator_distribution),
            "stall_count": self.stall_count,
            "in_annealing_mode": self.in_annealing_mode,
            "temperature": self.temperature,
            "phase_transition_count": len(self.phase_transitions),
            "phase_transition_threshold": self.phase_transition_threshold,
            "stall_threshold": self.stall_threshold,
            "cooling_rate": self.cooling_rate,
            "primitive_weights": dict(self.primitive_weights),
            "operator_distribution": dict(self.operator_distribution),
        }

    def load_state(
        self,
        state: Dict[str, Any],
        phase_transitions: Optional[List[Dict[str, Any]]] = None,
        provenance_log: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Restore all adaptive state required for a true multi-session continuation."""
        self.mutation_rate = float(state.get("mutation_rate", self.mutation_rate))
        self.stall_count = int(state.get("stall_count", self.stall_count))
        self.in_annealing_mode = bool(
            state.get("in_annealing_mode", self.in_annealing_mode)
        )
        self.temperature = float(state.get("temperature", self.temperature))
        self.phase_transition_threshold = float(
            state.get("phase_transition_threshold", self.phase_transition_threshold)
        )
        self.stall_threshold = int(state.get("stall_threshold", self.stall_threshold))
        self.cooling_rate = float(state.get("cooling_rate", self.cooling_rate))
        self.primitive_weights = {
            str(k): float(v) for k, v in state.get("primitive_weights", {}).items()
        }
        self.operator_distribution = {
            str(k): float(v) for k, v in state.get("operator_distribution", {}).items()
        }
        self.phase_transitions = list(phase_transitions or [])
        self.provenance_log = list(provenance_log or [])
