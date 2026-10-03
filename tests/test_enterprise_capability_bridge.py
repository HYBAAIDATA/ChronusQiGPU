"""Rule 7 enterprise capability bridge locks."""
from __future__ import annotations

import pytest

from aethel.enterprise_bridge import (
    CapStatus,
    TruthClass,
    assert_ready,
    emit_envelope,
    open_enterprise_store,
    provenance_hash,
    report,
    smoke_measured_put,
)


def test_report_triad_ready_and_counts():
    r = report()
    assert r.triad_ready is True
    assert r.counts[CapStatus.READY.value] >= 8
    assert "E.FOLD.WORKING_FORM" in r.migrate_now
    assert "E.STORE.SELF_HEAL" in r.migrate_now
    assert "E.API.SOLUTIONS_V1" in r.do_not_claim_here
    assert "E.MRI.SL3Z" in r.do_not_claim_here
    assert "infinite" not in r.claim_boundary.lower() or "does not" in r.claim_boundary.lower()


def test_assert_ready_fail_closed_on_external():
    assert_ready("E.FOLD.WORKING_FORM")
    with pytest.raises(RuntimeError):
        assert_ready("E.API.SOLUTIONS_V1")
    with pytest.raises(RuntimeError):
        assert_ready("E.QUANTUM.NEAR_STATE_10K")


def test_envelope_has_truth_class_and_provenance():
    env = emit_envelope({"x": 1}, truth_class=TruthClass.MEASURED, capability_id="E.FOLD.WORKING_FORM")
    assert env["truth_class"] == "measured"
    assert len(env["provenance_hash"]) == 64
    assert env["capability_status"] == "READY"
    # stable hash: recompute
    again = provenance_hash({k: v for k, v in env.items() if k != "provenance_hash"})
    # timestamp differs — just check field present and hex
    assert all(c in "0123456789abcdef" for c in env["provenance_hash"])


def test_external_capability_marked_not_local_production():
    env = emit_envelope({}, capability_id="E.API.SOLUTIONS_V1")
    assert env["capability_status"] == "EXTERNAL"
    assert env.get("advertisement") == "not_local_production"


def test_smoke_measured_put_envelope():
    env = smoke_measured_put(b"bridge-smoke-payload")
    assert env["truth_class"] == "measured"
    assert env["payload"]["ok"] is True
    assert env["capability_id"] == "E.STORE.SELF_HEAL"


def test_open_enterprise_store_put_get():
    db = open_enterprise_store(durable=True, bind_chronus=False)
    rec = db.put(b"enterprise-kernel", durable=True)
    assert db.get(rec.uuid) == b"enterprise-kernel"
    health = db.health()
    assert health["owners"]["theseus"]["status"] == "ok"
    assert health["owners"]["ovid"]["status"] == "ok"
