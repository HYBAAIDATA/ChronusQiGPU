"""
PYTHAGORAS — AUTO-PRIMITIVE DISCOVERY
Promotes recurring structural patterns to named primitives.

Theoretical Foundation:
- Dynamic operator-space expansion: Instead of searching only across a static basis,
  the system identifies recurring AST motifs that yield consistent φ-gains and
  synthesizes them into first-class transformation primitives.
- Microcosm of biological and mathematical insight creation (Deutsch constructor theory /
  DeepMind AlphaEvo meta-adaptation).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional
import numpy as np


class AutoPrimitiveDiscovery:
    """
    Discovers new transformation primitives autonomously.

    When an AST transformation pattern produces consistent φ-gains across
    multiple mutations, AutoPrimitiveDiscovery promotes it to a named
    primitive with an empirically learned weight.
    """

    def __init__(
        self,
        gain_threshold: float = 0.05,
        consistency_threshold: int = 3,
    ):
        self.gain_threshold = float(gain_threshold)
        self.consistency_threshold = int(consistency_threshold)

        self.patterns: Dict[str, List[float]] = defaultdict(list)
        self.discovered: Dict[str, Dict[str, Any]] = {}
        self.discovery_history: List[Dict[str, Any]] = []

    def observe(
        self,
        pattern: str,
        gain: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record the observed φ-gain for a candidate AST pattern.
        """
        self.patterns[pattern].append(float(gain))

    def discover(self) -> List[Dict[str, Any]]:
        """
        Evaluate observed patterns and promote qualifying candidates
        to named primitives.
        """
        newly_discovered: List[Dict[str, Any]] = []

        for pattern, gains in list(self.patterns.items()):
            if pattern in self.discovered:
                continue

            if len(gains) < self.consistency_threshold:
                continue

            avg_gain = float(np.mean(gains))
            if avg_gain < self.gain_threshold:
                continue

            # Promote pattern to named primitive
            learned_weight = float(np.clip(avg_gain * 10.0, 0.1, 1.0))
            primitive_record = {
                "name": pattern,
                "avg_gain": avg_gain,
                "weight": learned_weight,
                "n_observations": len(gains),
                "discovered_at": len(self.discovered),
                "variance": float(np.var(gains)),
            }

            self.discovered[pattern] = primitive_record
            self.discovery_history.append(primitive_record)
            newly_discovered.append(primitive_record)

        return newly_discovered

    def get_discovered(self) -> Dict[str, Dict[str, Any]]:
        """Return all discovered primitives and their metadata."""
        return dict(self.discovered)

    def export_state(self) -> Dict[str, Any]:
        """Export discovery state for multi-session memory."""
        return {
            "patterns": {k: list(v) for k, v in self.patterns.items()},
            "discovered": dict(self.discovered),
            "discovery_history": list(self.discovery_history),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load discovery state from prior session."""
        for k, v in state.get("patterns", {}).items():
            self.patterns[k] = list(v)
        self.discovered = dict(state.get("discovered", {}))
        self.discovery_history = list(state.get("discovery_history", []))
