"""Lease authorisation bounds the O(files) physical reconciliation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chronus/mla1517_platform/python"))

import m3_mining_guard  # noqa: E402


class Recorder:
    def __init__(self, reconciliation_ok=True):
        self.calls = []
        self.reconciliation_ok = reconciliation_ok
        self.last = None

    def health(self, *, reconcile=True, full=True):
        assert full == reconcile
        self.calls.append(reconcile)
        ok = self.reconciliation_ok if reconcile else (self.last or {}).get("reconciliation_ok", False)
        self.last = {"healthy": ok, "reconciliation_ok": ok}
        return dict(self.last)


def gate(recorder):
    g = m3_mining_guard.M3MiningSubmissionGate.__new__(m3_mining_guard.M3MiningSubmissionGate)
    g.recorder = recorder
    return g


def test_reconciles_once_per_interval(monkeypatch):
    monkeypatch.setenv("PYTHIA_STORAGE_RECONCILE_INTERVAL_S", "60")
    clock = [1000.0]
    monkeypatch.setattr(m3_mining_guard.time, "monotonic", lambda: clock[0])
    rec = Recorder()
    g = gate(rec)
    for _ in range(5):
        assert g._lease_storage_health()["healthy"]
    clock[0] += 61
    g._lease_storage_health()
    assert rec.calls == [True, False, False, False, False, True]


def test_zero_interval_reconciles_every_lease(monkeypatch):
    monkeypatch.setenv("PYTHIA_STORAGE_RECONCILE_INTERVAL_S", "0")
    rec = Recorder()
    g = gate(rec)
    for _ in range(3):
        g._lease_storage_health()
    assert rec.calls == [True, True, True]


def test_failed_reconciliation_keeps_refusing_until_one_passes(monkeypatch):
    monkeypatch.setenv("PYTHIA_STORAGE_RECONCILE_INTERVAL_S", "60")
    clock = [0.0]
    monkeypatch.setattr(m3_mining_guard.time, "monotonic", lambda: clock[0])
    rec = Recorder(reconciliation_ok=False)
    g = gate(rec)
    assert not g._lease_storage_health()["healthy"]
    clock[0] += 10
    assert not g._lease_storage_health()["healthy"]  # carried forward, not re-run
    rec.reconciliation_ok = True
    clock[0] += 60
    assert g._lease_storage_health()["healthy"]


def test_unreadable_interval_fails_safe_to_every_lease(monkeypatch):
    monkeypatch.setenv("PYTHIA_STORAGE_RECONCILE_INTERVAL_S", "soon")
    rec = Recorder()
    g = gate(rec)
    g._lease_storage_health()
    g._lease_storage_health()
    assert rec.calls == [True, True]
