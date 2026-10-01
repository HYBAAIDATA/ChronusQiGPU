"""Geodesic ordering seam for the canonical production mining coordinator.

The planner is deliberately downstream of real solver coverage and upstream of
chooser ordering. It can only return a permutation of the candidate window
already produced by the canonical solver. On any error the exact baseline
window is returned unchanged.
"""
from __future__ import annotations

import os
from typing import Any

from python_backend.core_modules.geodesic_tensor_engine import GeodesicNoncePlanner
from .euclid_support import EuclidProductionMiningCoordinator


class GeodesicProductionMiningCoordinator(EuclidProductionMiningCoordinator):
    """EUCLID production coordinator with exact-PULVINI geodesic ordering."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.geodesic_enabled = os.getenv("PYTHIA_GEODESIC_ORDERING", "1").strip() not in {
            "0", "false", "False", "off", "OFF"
        }
        try:
            depth = int(os.getenv("PYTHIA_GEODESIC_FOLD_DEPTH", "3"))
        except ValueError:
            depth = 3
        self.geodesic_planner = GeodesicNoncePlanner(fold_depth=max(0, min(depth, 32)))
        self._geodesic_state: dict[str, Any] = {
            "state": "ENABLED" if self.geodesic_enabled else "DISABLED",
            "consensus_authority": False,
            "claim_boundary": "candidate ordering only",
            "last_error": None,
            "last_report": None,
        }

    def _observed_candidate_window(self) -> list[int]:
        baseline = super()._observed_candidate_window()
        if not self.geodesic_enabled or len(baseline) < 2:
            return baseline
        try:
            ordered = self.geodesic_planner.order_window(baseline, anchor=self._base_step)
        except Exception as exc:
            self._geodesic_state = {
                **self._geodesic_state,
                "state": "DEGRADED_BASELINE",
                "last_error": f"{type(exc).__name__}: {exc}",
                "last_report": None,
            }
            return baseline
        if len(ordered) != len(baseline) or sorted(ordered) != sorted(baseline):
            self._geodesic_state = {
                **self._geodesic_state,
                "state": "DEGRADED_BASELINE",
                "last_error": "planner did not preserve candidate membership",
                "last_report": None,
            }
            return baseline
        self._geodesic_state = {
            **self._geodesic_state,
            "state": "ACTIVE",
            "last_error": None,
            "last_report": self.geodesic_planner.last_report,
        }
        return ordered

    def evidence_snapshot(self) -> dict[str, Any]:
        snapshot = super().evidence_snapshot()
        snapshot["geodesic_ordering"] = dict(self._geodesic_state)
        return snapshot


__all__ = ["GeodesicProductionMiningCoordinator"]
