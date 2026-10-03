"""Rule 7 enterprise capability bridge locks."""
from __future__ import annotations

import pytest

from aethel.enterprise_bridge import (
    CapStatus,
    TruthClass,
    assert_ready,
    compute_envelope_provenance_hash,
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
    env = emit_envelope({"x": 1}, truth_class=TruthClass.MEASURED)
    assert env["truth_class"] == TruthClass.MEASURED.value
    got = env["provenance_hash"]
    assert isinstance(got, str) and len(got) == 64
    assert got == compute_envelope_provenance_hash(env)
    body = {k: v for k, v in env.items() if k != "provenance_hash"}
    assert got == provenance_hash(body)



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


def test_provenance_hash_recomputed_equality() -> None:
    """Provenance must equal recomputed SHA-256 (integrity), not merely look hex-ish."""
    from aethel.enterprise_bridge import (
        TruthClass,
        compute_envelope_provenance_hash,
        emit_envelope,
        provenance_hash,
    )

    env = emit_envelope(
        {"k": "v", "n": 1},
        truth_class=TruthClass.MEASURED,
        capability_id="E.STORE.THESEUS",
    )
    got = env["provenance_hash"]
    assert isinstance(got, str) and len(got) == 64
    assert all(c in "0123456789abcdef" for c in got)
    # Explicit recompute equality (the actual gate)
    assert got == compute_envelope_provenance_hash(env)
    body = {k: v for k, v in env.items() if k != "provenance_hash"}
    assert got == provenance_hash(body)
    # Integrity is SHA-256; authenticity (HMAC) is Theseus-side only


def test_report_never_unqualified_production_ready() -> None:
    from aethel.enterprise_bridge import report

    d = report().to_dict()
    assert d.get("production_ready") is False
    assert d.get("software_readiness_scope") == "enterprise_custody_software_single_root"
    assert d.get("catalogue_is_declarative") is True
    assert d.get("evidence_drives_readiness") is True
    assert d.get("readiness_kind") == "scoped_software"


def test_capabilities_json_no_bare_production_ready_true() -> None:
    import json
    from importlib import resources

    raw = resources.files("aethel").joinpath("capabilities.json").read_text(encoding="utf-8")
    assert '"production_ready": true' not in raw
    data = json.loads(raw)
    assert "production_ready" not in data or data.get("production_ready") is False
    assert data.get("software_readiness") == "enterprise_custody_software_single_root"
