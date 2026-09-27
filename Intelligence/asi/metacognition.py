# pythagoras/asi/metacognition.py — NEW

from dataclasses import dataclass


@dataclass
class MetacognitiveState:
    confidence: float  # 0-1, how confident the system is in its current approach
    self_assessment: str  # textual self-evaluation
    strategy_working: bool  # is the current strategy effective?
    should_switch: bool  # should the system switch strategies?
    uncertainty: float  # 0-1, epistemic uncertainty
    calibration_error: float  # difference between confidence and actual performance


class MetacognitiveMonitor:
    """Monitors and regulates PYTHAGORAS's own cognitive processes.

    Implements:
    - Self-monitoring: tracks performance trajectory
    - Self-evaluation: assesses whether strategies are working
    - Self-regulation: decides when to switch strategies
    - Calibration: checks if confidence matches reality
    """

    def __init__(self, calibration_window: int = 20):
        self.calibration_window = calibration_window
        self.confidence_history: list[float] = []
        self.performance_history: list[float] = []
        self.strategy_history: list[str] = []
        self.current_strategy = "standard_evolution"
        self.available_strategies = [
            "standard_evolution",
            "surrogate_guided",
            "manifold_escape",
            "novelty_search",
            "annealing",
            "causal_intervention",
        ]

    def observe(self, phi: float, delta_phi: float, strategy: str) -> MetacognitiveState:
        self.performance_history.append(delta_phi)
        self.strategy_history.append(strategy)

        # Self-monitoring: compute recent trend
        recent = self.performance_history[-self.calibration_window :]
        trend = sum(recent) / len(recent) if recent else 0.0

        # Self-evaluation: is strategy working?
        strategy_working = trend > 0.001

        # Confidence estimation
        if len(recent) >= 5:
            import math

            mean = sum(recent) / len(recent)
            std = math.sqrt(sum((r - mean) ** 2 for r in recent) / len(recent))
            confidence = 1.0 / (1.0 + std)  # low variance = high confidence
        else:
            confidence = 0.5
        self.confidence_history.append(confidence)

        # Calibration: compare confidence to actual performance
        if len(self.confidence_history) >= 5:
            recent_conf = self.confidence_history[-5:]
            recent_perf = [1.0 if p > 0 else 0.0 for p in self.performance_history[-5:]]
            avg_conf = sum(recent_conf) / len(recent_conf)
            avg_perf = sum(recent_perf) / len(recent_perf)
            calibration_error = abs(avg_conf - avg_perf)
        else:
            calibration_error = 0.5

        # Self-regulation: should we switch strategies?
        should_switch = (
            not strategy_working and len(recent) >= 10 and all(p <= 0.001 for p in recent[-10:])
        )

        if should_switch:
            self.current_strategy = self._select_new_strategy()

        # Uncertainty quantification
        uncertainty = 1.0 - confidence

        return MetacognitiveState(
            confidence=round(confidence, 4),
            self_assessment=self._self_assess(trend, strategy_working, calibration_error),
            strategy_working=strategy_working,
            should_switch=should_switch,
            uncertainty=round(uncertainty, 4),
            calibration_error=round(calibration_error, 4),
        )

    def _select_new_strategy(self) -> str:
        """Select a strategy that hasn't been tried recently."""
        recent = self.strategy_history[-len(self.available_strategies) :]
        for s in self.available_strategies:
            if s not in recent:
                return s
        return self.available_strategies[0]

    def _self_assess(self, trend: float, working: bool, calibration: float) -> str:
        if working and calibration < 0.2:
            return f"Strategy effective (trend={trend:.4f}), well-calibrated"
        elif working and calibration >= 0.2:
            return f"Strategy effective but poorly calibrated (error={calibration:.2f}) — confidence may not match reality"
        elif not working and calibration < 0.2:
            return f"Strategy ineffective (trend={trend:.4f}), well-calibrated — should switch"
        return "Strategy ineffective and poorly calibrated — high uncertainty"

    def is_well_calibrated(self) -> bool:
        """A well-calibrated system's confidence matches its actual success rate."""
        if len(self.confidence_history) < 10:
            return True
        recent_conf = self.confidence_history[-10:]
        recent_perf = [1.0 if p > 0 else 0.0 for p in self.performance_history[-10:]]
        return abs(sum(recent_conf) / 10 - sum(recent_perf) / 10) < 0.15
