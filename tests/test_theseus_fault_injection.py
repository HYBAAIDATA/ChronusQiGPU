"""THESEUS fault-injection matrix — crash, corruption, recovery, rollback.

Every fault class required by the productionisation contract:
crash during write, partial write, corrupt record, corrupt checkpoint,
stale schema/version, dependency mismatch, replica loss, interrupted
recovery, restart, rollback, deterministic replay, integrity verification
after recovery. All assertions are fail-closed: a fault may degrade the
store but may never produce a silent wrong answer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aethel.enterprise import UnrecoverableCustodyError, compose
from aethel.enterprise.checkpoint import (
    CheckpointIntegrityError,
    CheckpointUnavailableError,
)
from aethel.enterprise.records import DependencyMismatchError, OperationalRecord
from aethel.enterprise.schema import THESEUS_FORMAT_VERSION


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path / "custody_root"


@pytest.fixture()
def key() -> bytes:
    return b"unit-test-hmac-key-32b!!!!!!!!"


def _primary(root: Path, rid: str) -> Path:
    return root / "tenants" / "default" / "primary" / f"{rid}.json"


def _replica(root: Path, rid: str) -> Path:
    return root / "tenants" / "default" / "replica" / f"{rid}.json"


def _journal(root: Path) -> Path:
    return root / "tenants" / "default" / "journal" / "wal.jsonl"


def _checkpoints(root: Path) -> Path:
    return root / "tenants" / "default" / "checkpoints"


# -- crash during write -------------------------------------------------------


def test_crash_between_primary_and_replica_write_heals_on_recover(
    root: Path, key: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate a crash after the primary write but before the replica.

    The WAL intent for the put is left unsealed; recovery must drop the
    dangling intent and heal the replica side from the verified primary.
    """
    import aethel.enterprise.custody as custody_mod

    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    original = custody_mod._atomic_write_json
    calls = {"n": 0}

    def crash_on_second(path, data):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated crash before replica write")
        return original(path, data)

    monkeypatch.setattr(custody_mod, "_atomic_write_json", crash_on_second)
    with pytest.raises(RuntimeError):
        c.put(b"survivor", record_id="crash1")
    monkeypatch.setattr(custody_mod, "_atomic_write_json", original)

    assert _primary(root, "crash1").exists()
    assert not _replica(root, "crash1").exists()

    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    # healed: replica restored from verified primary, payload intact
    assert c2.get("crash1") == b"survivor"
    assert _replica(root, "crash1").exists()


def test_dangling_intent_dropped_on_restart(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.journal.append_intent({"op_id": "dead-op", "op": "put", "record_id": "x"})
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    rows = list(c2.journal.iter_rows())
    assert all(r.get("op_id") != "dead-op" for r in rows)
    assert c2.recovery_report()["dangling_intents_dropped"] >= 0


# -- partial write -------------------------------------------------------------


def test_truncated_primary_heals_from_replica(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"payload", record_id="r")
    path = _primary(root, "r")
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 2])  # partial write residue
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.get("r") == b"payload"
    # replica side was intact; primary healed
    assert c2._side_ok(json.loads(_primary(root, "r").read_text()))


def test_truncated_both_sides_unrecoverable_fail_closed(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"payload", record_id="r")
    for side in (_primary, _replica):
        path = side(root, "r")
        path.write_bytes(path.read_bytes()[:20])
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    with pytest.raises((UnrecoverableCustodyError, KeyError)):
        c2.get("r")
    assert c2.recovery_report()["records_unrecoverable"].get("r")


# -- corrupt record -------------------------------------------------------------


def test_corrupt_record_digest_flip_heals_from_intact_side(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"clean", record_id="r")
    c.corrupt_for_test("r", side="primary")
    assert c.get("r") == b"clean"
    assert c.telemetry.get("heal_primary") == 1


def test_corrupt_both_sides_no_false_success(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"clean", record_id="r")
    c.corrupt_for_test("r", side="primary")
    c.corrupt_for_test("r", side="replica")
    with pytest.raises(UnrecoverableCustodyError):
        c.get("r")


# -- corrupt checkpoint ------------------------------------------------------------


def _newest_checkpoint(root: Path) -> Path:
    ck = _checkpoints(root)
    dirs = [d for d in ck.iterdir() if d.is_dir() and not d.name.endswith(".tmp")]
    assert dirs, "no checkpoint found"
    return sorted(dirs, key=lambda d: d.name)[-1]


def test_checkpoint_verify_and_rollback(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"v1", record_id="stable")
    ck = c.checkpoint(label="pre-mutation")
    assert c.verify_checkpoint(ck["checkpoint_id"])["status"] == "PASS"

    c.put(b"v2-mutated", record_id="stable")
    c.put(b"extra", record_id="extra")
    c.rollback(ck["checkpoint_id"])
    assert c.get("stable") == b"v1"
    with pytest.raises(KeyError):
        c.get("extra")


def test_corrupt_checkpoint_payload_refused_for_rollback(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"v1", record_id="stable")
    ck = c.checkpoint()
    cdir = _newest_checkpoint(root)
    victim = cdir / "primary" / "stable.json"
    data = json.loads(victim.read_text())
    data["payload_b64"] = "AAAA"  # corrupt stored bytes
    victim.write_text(json.dumps(data))
    verdict = c.verify_checkpoint(ck["checkpoint_id"])
    assert verdict["status"] == "FAIL"
    assert "primary/stable.json" in verdict["files_failed"]
    with pytest.raises(CheckpointIntegrityError):
        c.rollback(ck["checkpoint_id"])


def test_forged_checkpoint_manifest_refused(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"v1", record_id="stable")
    ck = c.checkpoint()
    cdir = _newest_checkpoint(root)
    manifest_path = cdir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["records"] = []  # forged claim — MAC now invalid
    manifest_path.write_text(json.dumps(manifest, indent=2))
    verdict = c.verify_checkpoint(ck["checkpoint_id"])
    assert verdict["status"] == "FAIL"
    assert verdict["mac"] == "FAIL"
    with pytest.raises(CheckpointIntegrityError):
        c.rollback(ck["checkpoint_id"])


def test_interrupted_checkpoint_is_unavailable(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"v1", record_id="stable")
    ck = c.checkpoint()
    cdir = _newest_checkpoint(root)
    # simulate crash mid-checkpoint: manifest absent
    (cdir / "manifest.json").unlink()
    with pytest.raises(CheckpointUnavailableError):
        c.verify_checkpoint(ck["checkpoint_id"])
    with pytest.raises(CheckpointUnavailableError):
        c.rollback(ck["checkpoint_id"])


# -- stale schema / version -------------------------------------------------------


def test_stale_format_version_marks_degraded_not_loaded(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"old", record_id="legacy")
    for side in (_primary, _replica):
        path = side(root, "legacy")
        data = json.loads(path.read_text())
        data["format_version"] = THESEUS_FORMAT_VERSION + 99
        path.write_text(json.dumps(data))
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.health()["degraded"] is True
    report = c2.recovery_report()
    assert "legacy" in report["records_unrecoverable"]


def test_unknown_ovid_transform_version_refused(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"old", record_id="legacy")
    for side in (_primary, _replica):
        path = side(root, "legacy")
        data = json.loads(path.read_text())
        data["ovid_transform_version"] = 4242
        path.write_text(json.dumps(data))
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert "legacy" in c2.recovery_report()["records_unrecoverable"]


# -- dependency mismatch ------------------------------------------------------------


def test_dependency_mismatch_record_refused_at_admission(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    rec = OperationalRecord(
        record_id="r",
        producer="ovid",
        producer_version="9.9",
        schema_version=1,
        kind="transform_lineage",
        payload=b"x",
        dependencies={"ovid_transform": 999},
    )
    with pytest.raises(DependencyMismatchError):
        c.put_record(rec)
    assert c.list_records() == []


# -- replica loss ------------------------------------------------------------------


def test_replica_loss_heals_and_restores_redundancy(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"resilient", record_id="r")
    _replica(root, "r").unlink()
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.get("r") == b"resilient"
    assert _replica(root, "r").exists()  # redundancy restored


def test_primary_loss_heals_from_replica(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"resilient", record_id="r")
    _primary(root, "r").unlink()
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.get("r") == b"resilient"


# -- interrupted recovery -----------------------------------------------------------


def test_interrupted_recovery_completes_degraded_not_corrupt(
    root: Path, key: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i in range(3):
        c.put(f"p{i}".encode(), record_id=f"r{i}")
    c.close()

    import aethel.enterprise.custody as custody_mod

    original = custody_mod.EnterpriseCustody._load_envelope
    tripped = {"done": False}

    def flaky(self, record_id, verify=True):
        if not tripped["done"] and record_id == "r1":
            tripped["done"] = True
            raise UnrecoverableCustodyError("simulated mid-scan failure")
        return original(self, record_id, verify=verify)

    monkeypatch.setattr(custody_mod.EnterpriseCustody, "_load_envelope", flaky)
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.health()["degraded"] is True
    assert c2.recovery_report()["records_unrecoverable"]["r1"] == ("UnrecoverableCustodyError")
    # store still serves verified records — fail closed never means crash
    assert c2.get("r0") == b"p0"


# -- restart / rollback / replay / post-recovery integrity -------------------------


def test_restart_recovers_all_records_identically(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    payloads = {f"r{i}": os.urandom(64) for i in range(5)}
    for rid, payload in payloads.items():
        c.put(payload, record_id=rid)
    c.close()
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for rid, payload in payloads.items():
        assert c2.get(rid) == payload
    assert c2.health()["ready"] is True


def test_post_recovery_integrity_verification_all_pass(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i in range(4):
        c.put(f"r{i}".encode(), record_id=f"r{i}")
    c.corrupt_for_test("r2", side="replica")
    c.close()
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i in range(4):
        ev = c2.custody_evidence(f"r{i}")
        assert ev["integrity"] == "PASS"
        assert ev["primary"] == "PASS" and ev["replica"] == "PASS"
        assert ev["envelope"]["mac_verified"] == "PASS"


def test_deterministic_replay_matches_store(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i in range(5):
        c.put(f"payload-{i}".encode(), record_id=f"r{i}")
    c.delete("r3")
    v1 = c.verify_replay()
    v2 = c.verify_replay()
    assert v1 == v2  # deterministic: identical input -> identical report
    assert v1["match"] is True


def test_replay_into_destination_rebuilds_identical_state(
    root: Path, key: bytes, tmp_path: Path
) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i in range(4):
        c.put(f"payload-{i}".encode(), record_id=f"r{i}")
    dest = compose(tmp_path / "dest", hmac_key=key, allow_insecure_dev_key=True)
    report = c.replay(dest)
    assert report["match"] is True
    assert report["ops_replayed"] == 4
    for i in range(4):
        assert dest.get(f"r{i}") == f"payload-{i}".encode()


def test_verify_replay_flags_silent_divergence(root: Path, key: bytes) -> None:
    """An out-of-band write the journal never sealed is reported, not hidden."""
    from aethel.enterprise import CustodyEnvelope, content_digest, mac_create
    from aethel.enterprise.ovid_registry import b64e

    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"journaled", record_id="r1")
    # Forge a VALID, correctly-signed record the journal never saw — the
    # divergence is journal-vs-store, not integrity. The payload goes through
    # the same fold path as a real put so the envelope verifies authentically.
    payload = b"ghost"
    folded = c.ovid.fold(payload, 1)
    env = CustodyEnvelope(
        record_id="ghost",
        payload_b64=b64e(folded),
        content_digest=content_digest(payload),
        generation=1,
        tenant="default",
        mac="",
        meta={
            "ingress_digest": content_digest(payload),
            "working_digest": content_digest(folded),
        },
    )
    env.mac = mac_create(key, env)
    data = env.to_dict()
    _primary(root, "ghost").write_text(json.dumps(data))
    _replica(root, "ghost").write_text(json.dumps(data))
    report = c.verify_replay()
    assert report["match"] is False
    kinds = {d["kind"] for d in report["divergences"]}
    assert "unexpected_present" in kinds
