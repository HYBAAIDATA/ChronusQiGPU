"""EmergenceAnalyzer module for phase-transition and criticality analysis."""

from __future__ import annotations
import math
from typing import Sequence, Dict, Any, List, Union
from collections import Counter

from ..models.telemetry import TelemetryRecord
from ..models.substrate import SubstrateExecutionResult
from .discontinuity import detect_discontinuities
from .criticality import criticality_indicators
from .information import integrated_information_proxy
from .complexity import neural_complexity_measure


class EmergenceAnalyzer:
    """Adapts computational-neuroscience and complex-systems methods to agent telemetry."""

    def __init__(self, target_records: Optional[Sequence[TelemetryRecord]] = None) -> None:
        self.verbatim_audit_logs: List[Dict[str, Any]] = []
        self._target_records = target_records or []

    @staticmethod
    def novel_repeatable_count(
        telemetry_records: Sequence[TelemetryRecord],
        min_repetitions: int = 2,
    ) -> int:
        counts: Counter[str] = Counter()
        for rec in telemetry_records:
            for b in rec.novel_elements.unattributed:
                counts[b] += 1
        return sum(1 for b, cnt in counts.items() if cnt >= min_repetitions)

    @property
    def novelty_entropy(self) -> float:
        """Compute Shannon entropy of unattributed novel behaviors across records."""
        if not self._target_records:
            return 0.0
        novel_counts: Counter[str] = Counter()
        for rec in self._target_records:
            for act in rec.novel_elements.unattributed:
                novel_counts[act] += 1
        total = sum(novel_counts.values())
        if total == 0:
            return 0.0
        ent = 0.0
        for cnt in novel_counts.values():
            p = cnt / total
            if p > 0:
                ent -= p * math.log2(p)
        return round(ent, 4)

    def phase_transition_scan(
        self,
        runs: Sequence[Union[SubstrateExecutionResult, Sequence[TelemetryRecord]]],
    ) -> Dict[str, Any]:
        """Perform phase-transition scan looking for nonlinear signatures rather than anecdotes."""
        all_stats = []

        for run_idx, run_item in enumerate(runs):
            records: Sequence[TelemetryRecord] = (
                run_item.telemetry_records if isinstance(run_item, SubstrateExecutionResult)
                else run_item
            )

            curve = []
            accumulated_records = []
            for i, rec in enumerate(records):
                accumulated_records.append(rec)
                rep_count = self.novel_repeatable_count(accumulated_records)
                curve.append({"iteration": rec.iteration_index, "count": rep_count})

            jump_points = detect_discontinuities(curve)
            criticality = criticality_indicators(records)
            integration = integrated_information_proxy(list(records))
            complexity = neural_complexity_measure(records, adapted=True)

            # Sustained jump points check: whether jump points maintain accelerated emergence rate
            sustained_jumps = len(jump_points) >= 2 or (
                len(jump_points) == 1 and jump_points[0].get("threshold_exceeded_by", 0) > 5.0
            )

            stats = {
                "run_index": run_idx,
                "total_iterations": len(records),
                "final_repeatable_count": self.novel_repeatable_count(records),
                "jump_points": {
                    "points": jump_points,
                    "sustained": sustained_jumps,
                },
                "criticality": criticality,
                "integration": integration,
                "complexity": complexity,
                "raw_curve": curve,  # Logged verbatim; never smoothed into a narrative
                "smoothing_applied": False,
            }

            self.verbatim_audit_logs.append(stats)
            all_stats.append(stats)

        overall_transitions = any(s["jump_points"]["sustained"] for s in all_stats)
        overall_criticality = any(s["criticality"].get("has_criticality_signature", False) for s in all_stats)

        return {
            "runs_analyzed": len(all_stats),
            "run_statistics": all_stats,
            "overall_phase_transitions_detected": overall_transitions,
            "criticality_detected": overall_criticality,
            "jump_points": {
                "sustained": overall_transitions,
                "count": sum(len(s["jump_points"]["points"]) for s in all_stats),
            },
            "criticality": all_stats[0]["criticality"] if all_stats else {},
        }
