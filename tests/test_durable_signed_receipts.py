"""THESEUS custody regression for AL HARAS signed receipt streams."""
from __future__ import annotations

import json
import sqlite3

import pytest

from chronus.crypto.signers import Ed25519Signer
from chronus.security.canonical import canonical_bytes
from chronus.security.durable_receipts import DurableReceiptLog, ReceiptCustodyError
from chronus.security.receipts import Receipt
from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError

pytestmark = pytest.mark.simulated


def receipt(log: DurableReceiptLog, key: Ed25519Signer, *, tenant="tenant-a") -> Receipt:
    return Receipt(
        "workload",
        tenant,
        "0" * 64,
        "execution-node",
        len(log),
        "2026-11-16T00:00:00Z",
        key.key_id,
        prev_digest=log.head_digest,
    )


def test_signed_receipts_survive_restart_and_verify_against_trusted_key(tmp_path):
    path = str(tmp_path / "custody.sqlite3")
    signer = Ed25519Signer.generate("control-key")
    custody = DurableTheseusService(path)
    first = DurableReceiptLog(custody, "tenant-a", "execution", signer.public_bytes())
    for _ in range(3):
        first.append(receipt(first, signer), signer)
    assert first.verify_chain(signer.public_bytes()) == (True, "3 receipts verified")
    assert first.evidence_class == "THESEUS_DURABLE_SIGNED_RECEIPT_LOCAL"
    assert custody.verify_journal_continuity("tenant-a")

    reopened_custody = DurableTheseusService(path)
    reopened = DurableReceiptLog(
        reopened_custody, "tenant-a", "execution", signer.public_bytes()
    )
    assert len(reopened) == 3
    assert reopened.head_digest == first.head_digest
    assert reopened.verify_chain(signer.public_bytes())[0]
    reopened.append(receipt(reopened, signer), signer)
    assert len(DurableReceiptLog(
        DurableTheseusService(path), "tenant-a", "execution", signer.public_bytes()
    )) == 4


def test_signed_receipts_isolate_tenants_and_other_journal_events(tmp_path):
    store = DurableTheseusService(str(tmp_path / "custody.sqlite3"))
    signer = Ed25519Signer.generate("key")
    a = DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())
    b = DurableReceiptLog(store, "tenant-b", "run", signer.public_bytes())
    store.append_journal_event("tenant-a", "UNRELATED_EVENT", b"still valid")
    a.append(receipt(a, signer), signer)
    assert len(b) == 0
    assert len(DurableReceiptLog(store, "tenant-a", "another-run", signer.public_bytes())) == 0
    with pytest.raises(ValueError, match="different tenant"):
        a.append(receipt(a, signer, tenant="tenant-b"), signer)
    assert len(a) == 1
    assert store.verify_journal_continuity("tenant-a")


def test_signed_receipts_reject_wrong_key_and_stale_stream(tmp_path):
    store = DurableTheseusService(str(tmp_path / "custody.sqlite3"))
    signer = Ed25519Signer.generate("key")
    attacker = Ed25519Signer.generate("key")
    a = DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())
    stale = DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())
    with pytest.raises(ValueError, match="pinned trusted key"):
        a.append(receipt(a, attacker), attacker)
    a.append(receipt(a, signer), signer)
    with pytest.raises(ReceiptCustodyError, match="changed"):
        stale.append(receipt(stale, signer), signer)
    assert not a.verify_chain(attacker.public_bytes())[0]


def test_signed_receipts_reject_spoofed_event_and_bad_signature(tmp_path):
    store = DurableTheseusService(str(tmp_path / "custody.sqlite3"))
    signer = Ed25519Signer.generate("key")
    baseline = DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())
    baseline.append(receipt(baseline, signer), signer)
    signed = baseline._entries[0]
    # Even a journal-valid, content-addressed payload is not automatically
    # an AL HARAS-valid receipt. Signed content must verify independently.
    forged = {
        "schema": "chronus.signed-receipt-custody/1",
        "stream_id": "run",
        "signing_key_sha256": baseline.public_key_sha256,
        "receipt": {**signed.receipt.unsigned(), "sequence": 1, "prev_digest": signed.digest},
        "digest": signed.digest,
        "signature": signed.signature.hex(),
    }
    store.append_journal_event("tenant-a", "AL_HARAS_SIGNED_RECEIPT_V1", canonical_bytes(forged))
    with pytest.raises(ReceiptCustodyError):
        DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())
    assert baseline.verify_chain(signer.public_bytes())[0] is False


def test_signed_receipts_reject_tampered_durable_content(tmp_path):
    path = str(tmp_path / "custody.sqlite3")
    store = DurableTheseusService(path)
    signer = Ed25519Signer.generate("key")
    stream = DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())
    stream.append(receipt(stream, signer), signer)
    object_id = store.get_journal("tenant-a")[0].object_id
    with sqlite3.connect(path) as db:
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (b"forged", object_id))
    with pytest.raises(StorageIntegrityError):
        DurableTheseusService(path)


def test_signed_receipts_do_not_advance_on_failed_custody_write(tmp_path, monkeypatch):
    store = DurableTheseusService(str(tmp_path / "custody.sqlite3"))
    signer = Ed25519Signer.generate("key")
    stream = DurableReceiptLog(store, "tenant-a", "run", signer.public_bytes())

    def unavailable(*args, **kwargs):
        raise OSError("durable path unavailable")

    monkeypatch.setattr(store, "append_journal_event", unavailable)
    with pytest.raises(OSError, match="unavailable"):
        stream.append(receipt(stream, signer), signer)
    assert len(stream) == 0
    assert stream.head_digest is None


def test_signed_envelope_cannot_be_replayed_into_another_stream(tmp_path):
    store = DurableTheseusService(str(tmp_path / "custody.sqlite3"))
    signer = Ed25519Signer.generate("key")
    source = DurableReceiptLog(store, "tenant-a", "source-stream", signer.public_bytes())
    source.append(receipt(source, signer), signer)
    original = store.get_journal("tenant-a")[0]
    forged_envelope = json.loads(store.reconstruct("tenant-a", original.object_id))
    forged_envelope["stream_id"] = "other-stream"
    store.append_journal_event(
        "tenant-a",
        "AL_HARAS_SIGNED_RECEIPT_V1",
        canonical_bytes(forged_envelope),
    )
    assert store.verify_journal_continuity("tenant-a")
    with pytest.raises(ReceiptCustodyError, match="invalid stored"):
        DurableReceiptLog(store, "tenant-a", "other-stream", signer.public_bytes())


def test_signed_envelope_requires_stream_binding_signature(tmp_path):
    store = DurableTheseusService(str(tmp_path / "custody.sqlite3"))
    signer = Ed25519Signer.generate("key")
    first = DurableReceiptLog(store, "tenant-a", "stream", signer.public_bytes())
    signed = first.append(receipt(first, signer), signer)
    data = json.loads(
        store.reconstruct("tenant-a", store.get_journal("tenant-a")[0].object_id)
    )
    assert data["digest"] == signed.digest
    data.pop("stream_binding_signature")
    store.append_journal_event("tenant-a", "AL_HARAS_SIGNED_RECEIPT_V1", canonical_bytes(data))
    with pytest.raises(ReceiptCustodyError):
        DurableReceiptLog(store, "tenant-a", "stream", signer.public_bytes())
