"""THESEUS recovery report, semantic-revalidation handoff, replay, evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from aethel.enterprise import (
    AlHarasEvidenceAdapter,
    compose,
)
from aethel.enterprise.records import OperationalRecord


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path / "custody_root"


@pytest.fixture()
def key() -> bytes:
    return b"unit-test-hmac-key-32b!!!!!!!!"


def _record(rid: str, producer: str, **kw) -> OperationalRecord:
    kw.setdefault("payload", rid.encode())
    return OperationalRecord(
        record_id=rid,
        producer=producer,
        producer_version="1.0",
        schema_version=1,
        kind="checkpoint",
        **kw,
    )


def test_recovery_report_groups_pending_by_producer(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put_record(_record("chronus-1", "chronus"))
    c.put_record(_record("turing-1", "turing"))
    c.put_record(_record("turing-2", "turing"))
    c.put(b"plain", record_id="anon")
    c.close()

    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    report = c2.recovery_report()
    assert report["records_verified"] == 4
    assert report["records_unrecoverable"] == {}
    pending = report["pending_revalidation"]
    assert pending["chronus"] == ["chronus-1"]
    assert pending["turing"] == ["turing-1", "turing-2"]
    assert pending["unknown"] == ["anon"]


def test_semantic_revalidated_retires_pending_and_provenances(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put_record(_record("r1", "turing"))
    c.close()

    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.pending_revalidation("turing")["turing"] == ["r1"]
    c2.semantic_revalidated("r1", verdict="PASS", producer="turing")
    assert c2.pending_revalidation("turing")["turing"] == []
    events = c2.provenance("r1")
    kinds = [e["event_type"] for e in events]
    assert "revalidation" in kinds


def test_unrecoverable_records_listed_in_report(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"good", record_id="ok")
    c.put(b"bad", record_id="bad")
    c.corrupt_for_test("bad", side="primary")
    c.corrupt_for_test("bad", side="replica")
    c.close()
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    report = c2.recovery_report()
    assert "bad" in report["records_unrecoverable"]
    assert c2.health()["degraded"] is True
    assert c2.health()["recovery"]["records_unrecoverable"] == 1


def test_replay_determinism_property(root: Path, key: bytes) -> None:
    """Same op stream -> identical fold; order matters, set order doesn't."""
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    for i in range(6):
        c.put(f"v{i}".encode(), record_id=f"k{i}")
    c.delete("k2")
    a = c.verify_replay()
    b = c.verify_replay()
    assert a == b
    assert a["match"] is True and a["expected_records"] == 5


def test_custody_evidence_is_complete_chain(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put_record(_record("ev1", "ovid", correlation_ids={"transform": "fold-9"}))
    ck = c.checkpoint()
    ev = c.custody_evidence("ev1")
    assert ev["integrity"] == "PASS"
    assert ev["primary"] == "PASS" and ev["replica"] == "PASS"
    assert ev["envelope"]["mac_verified"] == "PASS"
    assert ev["envelope"]["meta"]["op_record"]["producer"] == "ovid"
    assert any(o.get("op") == "put" for o in ev["journal_ops"])
    assert ck["checkpoint_id"] in ev["checkpoints"]
    assert ev["access_contract"] in ("hook", "callable", "none")
    # provenance includes the put event
    assert any(e["event_type"] == "put" for e in ev["provenance"])


def test_custody_evidence_missing_record_explicit(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    ev = c.custody_evidence("nope")
    assert ev["integrity"] == "MISSING"
    assert ev["primary"] == "MISSING" and ev["replica"] == "MISSING"


def test_al_haras_adapter_receives_get_evidence(root: Path, key: bytes) -> None:
    adapter = AlHarasEvidenceAdapter()
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True, hook=adapter)
    c.put(b"x", record_id="r")
    c.get("r")
    kinds = [e["kind"] for e in adapter.evidence]
    assert "after_put" in kinds and "after_get" in kinds


def test_generation_increments_on_overwrite_and_survives_restart(root: Path, key: bytes) -> None:
    c = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    c.put(b"v1", record_id="r")
    c.put(b"v2", record_id="r")
    env = c.get and c._load_envelope("r")
    assert env is not None and env.generation == 2
    c.close()
    c2 = compose(root, hmac_key=key, allow_insecure_dev_key=True)
    assert c2.get("r") == b"v2"
    assert c2._load_envelope("r").generation == 2
