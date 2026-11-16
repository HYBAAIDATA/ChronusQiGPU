"""Utilisation ledger for the avoided-capex true-up loop.

``admit`` returns utilisation; store it. Quarterly,
``space_bytes × utilisation`` against the client's declared baseline is the
invoice line, and utilisation below 1.0 is a credit. Symmetric, or the clause
is not one. ``no baseline, no fee``.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UtilisationRecord:
    reservation: str
    tier: str
    reserved: int
    actual: int
    space_bytes: int
    utilisation: float
    recorded_at: float
    tenant_id: str | None = None


class UtilisationLedger:
    """Process-local append-only utilisation log (pilot)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._rows: list[UtilisationRecord] = []
        if path and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                self._rows.append(UtilisationRecord(**data))

    def record(self, admission: dict[str, Any], *, tenant_id: str | None = None) -> UtilisationRecord:
        row = UtilisationRecord(
            reservation=str(admission["reservation"]),
            tier=str(admission["tier"]),
            reserved=int(admission["reserved"]),
            actual=int(admission["actual"]),
            space_bytes=int(admission["space_bytes"]),
            utilisation=float(admission["utilisation"]),
            recorded_at=time.time(),
            tenant_id=tenant_id,
        )
        with self._lock:
            self._rows.append(row)
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")
        return row

    def rows(self) -> list[UtilisationRecord]:
        with self._lock:
            return list(self._rows)

    def quarterly_line(
        self,
        *,
        baseline_accelerator_hours: float | None,
        since: float,
        until: float,
    ) -> dict[str, Any]:
        """True-up against a declared baseline. No baseline → no fee."""
        if baseline_accelerator_hours is None:
            return {
                "fee_applicable": False,
                "reason": "no_baseline_no_fee",
                "utilised_space_bytes": 0,
            }
        utilised = 0.0
        for row in self.rows():
            if since <= row.recorded_at < until:
                utilised += row.space_bytes * row.utilisation
        # Pilot accounting unit: map utilised space to avoided hours via baseline
        # provided by the client — we do not invent a conversion factor here.
        return {
            "fee_applicable": True,
            "baseline_accelerator_hours": baseline_accelerator_hours,
            "utilised_space_bytes": int(utilised),
            "credit_if_utilisation_below_one": True,
            "window": {"since": since, "until": until},
        }
