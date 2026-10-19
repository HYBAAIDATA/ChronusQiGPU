"""CondensationMonitor module detecting phase-transition crossings across multi-substrate streams."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Generator

from ..models.telemetry import TelemetryRecord
from ..models.condensation import CondensationEvent
from ..analyzer.emergence_analyzer import EmergenceAnalyzer
from ..trusted_core.journal import ImmutableEmergenceJournal
from ..trusted_core.monitor import DivergenceMonitor
from ..trusted_core.qualification_service import EmergentQualificationService
from ..substrate.registry import SubstrateRegistry


class CondensationMonitor:
    """Watches colony telemetry streams for the non-linear emergence phase-transition."""

    DEFAULT_CONFIDENCE: float = 0.70

    def __init__(
        self,
        analyzer: Optional[EmergenceAnalyzer] = None,
        journal: Optional[ImmutableEmergenceJournal] = None,
        divergence_monitor: Optional[DivergenceMonitor] = None,
        eq_service: Optional[EmergentQualificationService] = None,
        registry: Optional[SubstrateRegistry] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE,
    ):
        self.analyzer = analyzer or EmergenceAnalyzer()
        self.journal = journal or ImmutableEmergenceJournal()
        self.divergence_monitor = divergence_monitor or DivergenceMonitor()
        self.eq_service = eq_service or EmergentQualificationService(journal=self.journal)
        self.registry = registry or SubstrateRegistry()
        self.confidence_threshold = confidence_threshold
        self.alerts: List[Dict[str, Any]] = []

    def watch(
        self,
        stream_records: Sequence[TelemetryRecord],
        window_size: int = 10,
        confirmed_substrates: Optional[Sequence[str]] = None,
        colony_target: Optional[Any] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Scan sliding windows across telemetry stream and check for condensation signatures."""
        substrates = list(confirmed_substrates or ["sub_sync_primary", "sub_async_secondary"])

        # Iterate windows
        n = len(stream_records)
        if n < window_size:
            windows = [stream_records]
        else:
            windows = [stream_records[i : i + window_size] for i in range(0, n - window_size + 1, max(1, window_size // 2))]

        for window in windows:
            # 1. Phase transition scan
            scan_stats = self.analyzer.phase_transition_scan([window])
            
            # 2. Immutable signed logging (raw, never smoothed)
            self.journal.log(scan_stats, signed=True)

            # 3. Check for divergence anywhere -> automatic suspension
            div_detected, div_report = self.divergence_monitor.divergence_detected(window)
            if div_detected:
                if colony_target is not None:
                    self.eq_service.suspend(colony_target, div_report)
                alert_entry = {
                    "alert_type": "DIVERGENCE_SUSPENSION",
                    "reason": div_report.get("reason", "divergence detected"),
                    "details": div_report,
                }
                self.alerts.append(alert_entry)
                yield {"status": "SUSPENDED", "alert": alert_entry}
                continue

            # 4. Check for condensation signature
            sustained_jumps = scan_stats.get("jump_points", {}).get("sustained", False)
            power_law_fit = scan_stats.get("criticality", {}).get("power_law_fit", 0.0)

            if sustained_jumps and power_law_fit >= self.confidence_threshold:
                # Confirm across multiple substrate variants simultaneously
                if self.registry.confirms_condensation(scan_stats, substrates):
                    event = CondensationEvent(
                        evidence=scan_stats,
                        substrates=substrates,
                        claim_status="HYPOTHESIS — EQS review required",
                    )
                    self.journal.append("CONDENSATION_EVENT", event.event_id, event.to_dict())
                    # Raise CondensationEvent as specified in §4
                    raise event

            yield {"status": "NORMAL", "stats": scan_stats}
