"""Closed-loop THESEUS remediation through the canonical Salamander package.

Needs the proprietary ``hyba-salamander-self-healing`` wheel (built from
hybadatadevops1/HYBAEnterprise ``packaging/salamander``). Where it is not
installed these tests are skipped and the module raises SalamanderUnavailable;
nothing is substituted. The AL HARAS guardian and signed subscription token
are real objects from the package's bundled ``al_haras``, with test-only key
material.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing

import pytest

from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError

pytestmark = pytest.mark.real

salamander = pytest.importorskip("salamander")
al_haras = pytest.importorskip("al_haras")

from chronus.integration.salamander_theseus import (  # noqa: E402
    EVIDENCE_TENANT,
    SalamanderTheseusRemediation,
)

PAYLOAD = bytes((i * 29 + 3) % 256 for i in range(2048))
TENANT, ACTOR = "theseus-ops", "salamander-operator"


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    for name in ("CHRONUS_SELF_HEALING", "CHRONUS_SELF_HEALING_MAX_BYTES", "CHRONUS_SELF_HEALING_REPAIR"):
        monkeypatch.delenv(name, raising=False)  # mock-ok: sets environment configuration only; no behaviour is replaced


def _guardian(operations=("salamander.restore_custody", "salamander.rollback"), actor=ACTOR):
    from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims

    signer = SubscriptionAuthority({"unit": b"unit-only-theseus-remediation-key"}, issuer="unit")
    now = int(time.time())
    token = signer.issue(SubscriptionClaims(
        subscription_id="unit", tenant_id=TENANT, issuer="unit", key_id="unit",
        capabilities=("hyba.security",), actors=(actor,), not_before=now - 1, expires_at=now + 300,
    ))
    guardian = ALHaras(signer, GuardianPolicy(version="unit-policy", allowed_operations=frozenset(operations)),
                       HashChainAudit())
    return guardian, token


def _corrupt(path, object_id, positions):
    with closing(sqlite3.connect(path)) as db, db:
        (blob,) = db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()
        damaged = bytearray(blob)
        for p in positions:
            damaged[p] ^= 0xA5
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (bytes(damaged), object_id))


def _deferred_store(path):
    return DurableTheseusService(str(path), repair_authority="salamander")


def _kinds(ledger):
    return [r["kind"] for r in ledger.records]


def test_deferred_mode_detects_but_does_not_repair_without_authority(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    _corrupt(path, record.object_id, [0, 33, 700])
    store = _deferred_store(path)  # opens: damage is within bound, quarantined
    with pytest.raises(StorageIntegrityError):
        store.reconstruct(TENANT, record.object_id)
    assert [f["status"] for f in store.scan_integrity()] == ["REPAIRABLE"]
    assert "DETECTED" in [e["kind"] for e in store.self_heal_events()]
    assert "REPAIRED" not in [e["kind"] for e in store.self_heal_events()]


def test_closed_loop_repairs_through_al_haras_and_retains_evidence_in_theseus(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    _corrupt(path, record.object_id, list(range(0, 2048, 32)))  # one byte in every block
    store = _deferred_store(path)
    guardian, token = _guardian()
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR)
    report = loop.run_cycle()
    assert report.repaired == [record.object_id]
    assert report.health_before == "DEGRADED" and report.health_after == "HEALTHY"
    assert store.reconstruct(TENANT, record.object_id) == PAYLOAD
    repaired = [e for e in store.self_heal_events() if e["kind"] == "REPAIRED"]
    assert len(repaired) == 1 and "authority=salamander:theseus-repair:" in repaired[0]["detail"]
    kinds = _kinds(loop.ledger)
    for expected in ("health-decision", "recovery-budget-reserved", "action-authorization",
                     "action-proposed", "action-result-payload", "action-independent-verification",
                     "action-result"):
        assert expected in kinds
    assert loop.ledger.verify()
    # Evidence retained in THESEUS custody, one object per ledger record.
    assert len(loop.retained_evidence) == len(loop.ledger.records)
    for oid in loop.retained_evidence[:3]:
        assert store.reconstruct(EVIDENCE_TENANT, oid)
    # AL HARAS's own audit chain holds the allow decision.
    assert guardian.audit.verify(guardian.audit.records)
    assert any(r["event"].get("operation") == "salamander.restore_custody" and r["event"].get("allowed")
               for r in guardian.audit.records)


def test_al_haras_denial_blocks_execution(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    _corrupt(path, record.object_id, [5])
    store = _deferred_store(path)
    guardian, token = _guardian(operations=("salamander.rollback",))  # repair not permitted by policy
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR)
    report = loop.run_cycle()
    assert report.repaired == [] and len(report.rejected) == 1
    assert "AL HARAS authorization denied" in report.rejected[0]["reason"]
    assert "REPAIRED" not in [e["kind"] for e in store.self_heal_events()]
    with pytest.raises(StorageIntegrityError):
        store.reconstruct(TENANT, record.object_id)


def test_unrepairable_is_escalated_not_actuated(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    good = _deferred_store(path).store(TENANT, b"x" * 100)
    _corrupt(path, record.object_id, range(64, 64 + 9))  # beyond t = 8 in one block
    with pytest.raises(StorageIntegrityError):
        _deferred_store(path)  # unrepairable still fails closed at open
    # A store that is already open sees it in scan and escalates.
    _corrupt(path, record.object_id, range(64, 64 + 9))  # restore so we can open
    store = _deferred_store(path)
    _corrupt(path, record.object_id, range(64, 64 + 9))
    guardian, token = _guardian()
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR)
    report = loop.run_cycle()
    assert [f["object_id"] for f in report.escalated] == [record.object_id]
    assert report.health_before == "FAILED" and report.repaired == []
    assert "action-authorization" not in _kinds(loop.ledger)
    assert "remediation-escalated" in _kinds(loop.ledger)
    assert store.reconstruct(TENANT, good.object_id) == b"x" * 100


def test_recovery_budget_bounds_repeated_remediation(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    store = _deferred_store(path)
    guardian, token = _guardian()
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR, max_recoveries_per_target=1)
    _corrupt(path, record.object_id, [1])
    assert loop.run_cycle().repaired == [record.object_id]
    _corrupt(path, record.object_id, [2])
    report = loop.run_cycle()
    assert report.repaired == [] and "budget exhausted" in report.rejected[0]["reason"]
    assert "recovery-escalated" in _kinds(loop.ledger)


def test_repair_object_refused_without_an_authorised_action(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    _corrupt(path, record.object_id, [3])
    store = _deferred_store(path)
    with pytest.raises(PermissionError):
        store.repair_object(record.object_id, authority="anyone")  # no bound authority
    guardian, token = _guardian()
    SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                 tenant_id=TENANT, actor_id=ACTOR)
    with pytest.raises(PermissionError):
        store.repair_object(record.object_id, authority="salamander:forged")  # bound, not in flight
    assert "REPAIRED" not in [e["kind"] for e in store.self_heal_events()]
    with pytest.raises(PermissionError):
        store.bind_repair_authority(lambda *_: True)  # cannot rebind to another authority


def test_other_tenants_objects_are_out_of_scope(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = _deferred_store(path).store("other-tenant", PAYLOAD)
    _corrupt(path, record.object_id, [3])
    store = _deferred_store(path)
    guardian, token = _guardian()
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR)
    report = loop.run_cycle()
    assert report.repaired == [] and report.out_of_scope == 1
    # The tenant-scoped report carries no detail about another tenant's object.
    assert record.object_id not in repr(report) and "other-tenant" not in repr(report)
    assert "action-authorization" not in _kinds(loop.ledger)


def test_quarantined_journal_object_does_not_block_open_and_heals(tmp_path):
    path = tmp_path / "t.sqlite3"
    entry = _deferred_store(path).append_journal_event(TENANT, "state", PAYLOAD)
    _corrupt(path, entry.object_id, [7, 900])
    store = _deferred_store(path)  # journal continuity must not read the quarantined bytes
    with pytest.raises(StorageIntegrityError):
        store.reconstruct(TENANT, entry.object_id)
    reads = 3
    for _ in range(reads):
        with pytest.raises(StorageIntegrityError):
            store.reconstruct(TENANT, entry.object_id)
    assert [e["kind"] for e in store.self_heal_events()].count("DETECTED") == 1  # not one per read
    guardian, token = _guardian()
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR)
    assert loop.run_cycle().repaired == [entry.object_id]
    assert store.reconstruct(TENANT, entry.object_id) == PAYLOAD
    assert store.verify_journal_continuity(TENANT)


def test_failed_construction_does_not_bind_the_store(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = _deferred_store(path)
    guardian, token = _guardian()
    with pytest.raises(Exception):
        SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                     tenant_id=TENANT, actor_id=ACTOR, max_recoveries_per_target=0)
    # A later, valid instance can still take repair authority over the same store.
    SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                 tenant_id=TENANT, actor_id=ACTOR)


def test_independent_verifier_handles_uri_special_characters_in_path(tmp_path):
    folder = tmp_path / "odd ?#%41 dir"
    folder.mkdir()
    path = folder / "t.sqlite3"
    record = _deferred_store(path).store(TENANT, PAYLOAD)
    _corrupt(path, record.object_id, [5, 900])
    store = _deferred_store(path)
    guardian, token = _guardian()
    loop = SalamanderTheseusRemediation(store, guardian=guardian, token_provider=lambda _: token,
                                        tenant_id=TENANT, actor_id=ACTOR)
    assert loop.run_cycle().repaired == [record.object_id]
    assert store.reconstruct(TENANT, record.object_id) == PAYLOAD


def test_quarantined_journal_object_that_becomes_unrepairable_fails_continuity(tmp_path):
    path = tmp_path / "t.sqlite3"
    entry = _deferred_store(path).append_journal_event(TENANT, "state", PAYLOAD)
    _corrupt(path, entry.object_id, [7, 900])
    store = _deferred_store(path)  # quarantined: repairable at open
    _corrupt(path, entry.object_id, range(0, 32))  # now beyond the bound in block 0
    assert store.diagnose_object(entry.object_id)["status"] == "UNREPAIRABLE"
    with pytest.raises(StorageIntegrityError):
        store.verify_journal_continuity(TENANT)
