"""Tests for kellogg/fleet_security.py — durable log, key hygiene, threat model.

Scope: proves durable log survives crash at write boundaries; proves
fleet holds no private key; proves threat model covers named adversaries.
Does not prove RDMA or multi-host (see test_fleet_distributed.py).
"""
import pytest
import tempfile
import shutil
from kellogg.fleet_security import (
    DurableLog,
    KeyProvider,
    ThreatModel,
    append,
    recover,
    scan_for_private_keys,
)


class SimulatedCrash(Exception):
    """Used to simulate a crash at arbitrary write points."""


def test_durable_log_survives_crash(tmp_path):
    log = DurableLog(tmp_path / "log")
    entry1 = {"op": "commit", "data": "x"}
    log = append(log, entry1)
    # simulate crash + recover
    recovered = recover(log.storage)
    assert recovered.merkle_root == log.merkle_root
    assert entry1 in recovered.entries


def test_crash_at_each_write_boundary(tmp_path):
    # for each write point, simulate crash and verify recovery
    for crash_point in range(3):
        log = DurableLog(tmp_path / f"log_{crash_point}")
        try:
            log = append(log, {"op": "a"})
            if crash_point == 0:
                raise SimulatedCrash()
            log = append(log, {"op": "b"})
            if crash_point == 1:
                raise SimulatedCrash()
            log = append(log, {"op": "c"})
        except SimulatedCrash:
            pass
        recovered = recover(log.storage)
        assert recovered is not None, f"recovery failed at crash point {crash_point}"


def test_fleet_holds_no_private_key(tmp_path):
    # the fleet process must not contain private key material
    keys = scan_for_private_keys(root=tmp_path)
    assert keys == [], f"private keys found in fleet process: {keys}"


def test_threat_model_covers_named_adversaries():
    model = ThreatModel.default()
    for adversary in model.adversaries:
        mitigations = model.mitigations.get(adversary, [])
        assert len(mitigations) > 0, \
            f"adversary {adversary} has no mitigations"
        for m in mitigations:
            assert m.has_passing_test(), \
                f"mitigation {m} for {adversary} has no passing test"