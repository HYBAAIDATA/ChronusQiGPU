"""Actual Aethel owners: profile separation, disk restart and refusal gates.

Ordinary repository pytest uses the public package initializer. The separate
local source-subset bootstrap is qualification evidence, not installed acceptance.
"""

import hashlib
import json
import os
import subprocess
import sys

import pytest

from aethel.cassini import CassiniVerifier
from aethel.encoding import fold, unfold
from aethel.errors import AethelError
from aethel.fibonacci import binet_fibonacci, fibonacci
from aethel.ovid import open_ovid
from aethel.theseus import TheseusError, open_theseus
from aethel.triad import LEGACY_OVID_PROFILE, THESEUS_CUSTODY_PROFILE, open_triad


def test_enterprise_is_single_writer(tmp_path):
    triad = open_triad(durable_dir=tmp_path / "custody", bind_chronus=False)
    record = triad.put(b"enterprise payload")
    assert triad.get(record.uuid) == b"enterprise payload"
    assert triad.ovid_authority is None
    assert not list(tmp_path.rglob("ovid_index.json"))
    health = triad.health()
    assert health["storage_profile"] == THESEUS_CUSTODY_PROFILE
    assert health["custody"]["authority"] == "theseus"
    assert health["custody"]["disk_bound"] is True
    assert health["production_qualified"] is False
    with pytest.raises(RuntimeError):
        triad.ovid_put(b"not a second writer")


def test_memory_only_is_not_disk_custody():
    health = open_triad(durable=True, bind_chronus=False).health()
    assert health["status"] == "memory_only"
    assert health["custody"]["disk_bound"] is False


@pytest.mark.parametrize(
    "settings",
    [
        {"storage_profile": "unknown"},
        {"ovid_root": "legacy"},
        {"theseus_projection_root": "projection"},
        {"storage_profile": LEGACY_OVID_PROFILE},
        {
            "storage_profile": LEGACY_OVID_PROFILE,
            "ovid_root": "legacy",
            "durable_dir": "custody",
        },
    ],
)
def test_ambiguous_profile_refused_before_io(tmp_path, monkeypatch, settings):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        open_triad(bind_chronus=False, **settings)
    assert list(tmp_path.iterdir()) == []


def test_legacy_is_explicit_and_not_dual_written(tmp_path):
    triad = open_triad(
        storage_profile=LEGACY_OVID_PROFILE,
        ovid_root=tmp_path / "legacy",
        bind_chronus=False,
    )
    obj = triad.ovid_put(b"legacy bytes")
    triad.delete_theseus_projection()
    assert triad.ovid_get(obj.object_id) == b"legacy bytes"
    triad.rebuild_theseus()
    assert triad.verify()
    assert not triad.theseus._records
    with pytest.raises(RuntimeError):
        triad.put(b"ambiguous")
    with pytest.raises(RuntimeError):
        triad.get(obj.object_id)
    with pytest.raises(RuntimeError):
        triad.snapshot(str(tmp_path / "wrong-backup"))


def test_fresh_process_restart(tmp_path):
    root = tmp_path / "custody"
    record = open_triad(durable_dir=root, bind_chronus=False).put(bytes(range(256)))
    # The local subset runner declares its initializer bypass explicitly;
    # a complete checkout uses ordinary package imports in this child.
    bootstrap = os.environ.get("AETHEL_SUBSET_BOOTSTRAP", "")
    code = (
        bootstrap
        + "\nfrom aethel.triad import open_triad\n"
        + (
            f"t=open_triad(durable_dir={str(root)!r},bind_chronus=False)\n"
            f"p=t.get({record.uuid!r})\n"
            'if p != bytes(range(256)) or not t.verify(): raise RuntimeError("restart failed")\n'
            'print("ACTUAL_THESEUS_CROSS_PROCESS_PASS")\n'
        )
    )
    child = subprocess.run(
        [sys.executable, "-O" if not __debug__ else "-B", "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert child.returncode == 0, child.stderr
    assert "ACTUAL_THESEUS_CROSS_PROCESS_PASS" in child.stdout


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_len", 900),
        ("folded_units", 900),
        ("anchor", 999),
        ("prime_key", 0),
        ("durable_index", True),
        ("lane", -1),
        ("curvature", "invented"),
    ],
)
def test_tampered_metadata_refused(tmp_path, field, value):
    t = open_theseus(durable_dir=tmp_path)
    record = t.put(b"tamper target")
    path = tmp_path / "theseus_index.json"
    doc = json.loads(path.read_text())
    doc["records"][record.uuid][field] = value
    path.write_text(json.dumps(doc))
    with pytest.raises(TheseusError):
        open_theseus(durable_dir=tmp_path)


def test_orphaned_journal_is_not_empty_owner(tmp_path):
    t = open_theseus(durable_dir=tmp_path)
    t.put(b"orphaned but retained")
    (tmp_path / "theseus_index.json").unlink()
    journal = tmp_path / "durable/ledger.jsonl"
    before = journal.read_bytes()
    with pytest.raises(TheseusError, match="reconciliation"):
        open_theseus(durable_dir=tmp_path)
    assert journal.read_bytes() == before


def test_stale_index_fails_closed(tmp_path):
    t = open_theseus(durable_dir=tmp_path)
    t.put(b"first")
    path = tmp_path / "theseus_index.json"
    old = path.read_bytes()
    t.put(b"second")
    path.write_bytes(old)
    with pytest.raises(TheseusError, match="index/journal mismatch"):
        open_theseus(durable_dir=tmp_path)


def test_failed_publication_latches_owner(tmp_path, monkeypatch):
    t = open_theseus(durable_dir=tmp_path)
    t.put(b"first")
    monkeypatch.setattr(
        t,
        "_write_index",
        lambda *_: (_ for _ in ()).throw(OSError("injected publication failure")),
    )
    with pytest.raises(OSError):
        t.put(b"interrupted")
    with pytest.raises(TheseusError, match="uncertain"):
        t.put(b"unsafe continuation")
    with pytest.raises(TheseusError, match="uncertain"):
        t.get(next(iter(t._records)))
    with pytest.raises(TheseusError, match="index/journal mismatch"):
        open_theseus(durable_dir=tmp_path)


def test_corrupt_block_refused_on_restart(tmp_path):
    t = open_theseus(durable_dir=tmp_path)
    r = t.put(b"payload")
    (tmp_path / f"durable/blocks/{r.durable_index}.blk").write_bytes(b"changed")
    with pytest.raises(AethelError):
        open_theseus(durable_dir=tmp_path)


def test_real_heal_then_failed_heal(tmp_path):
    t = open_theseus(durable_dir=tmp_path)
    r = t.put(b"heal payload")
    t._payloads[r.uuid] = b"bad"
    assert t.get(r.uuid) == b"heal payload"
    t._payloads[r.uuid] = t._replicas[r.uuid] = b"bad"
    t.durable._blocks[r.durable_index] = b"bad"
    t.primes.uuid_index.clear()
    with pytest.raises(TheseusError):
        t.get(r.uuid)


@pytest.mark.parametrize("n", [0, 1, 2, 63, 90, 512, 2048])
def test_exact_math_and_fold_invariants(n):
    assert binet_fibonacci(n) == fibonacci(n)
    assert CassiniVerifier.verify(n)
    payload = bytes(range(256)) * (n // 256) + bytes(range(n % 256))
    vector = fold(payload)
    assert vector.verify()
    assert unfold(vector) == payload
    form = open_ovid().metamorphose(payload)
    assert form.digest == hashlib.sha256(payload).hexdigest()
    assert form.verify()


def test_euclid_adapter_requires_persistent_custody(tmp_path):
    from euclid.organ_adapters.specialists import TriadCustodyOrgan

    organ = TriadCustodyOrgan()
    status = organ.execute({"operation": "verify"})
    assert status["custody"]["disk_bound"] is False
    with pytest.raises(RuntimeError, match="put refused"):
        organ.execute({"operation": "put", "payload_utf8": "not durable"})
    organ = TriadCustodyOrgan(durable_dir=tmp_path / "custody")
    out = organ.execute({"operation": "put", "payload_utf8": "actual adapter"})
    assert out["custody"]["authority"] == "theseus"
    assert out["custody"]["integrity_verified"] is True
    restored = TriadCustodyOrgan(durable_dir=tmp_path / "custody")
    assert (
        restored.execute({"operation": "get", "uuid": out["uuid"]})["sha256"]
        == out["sha256"]
    )


def test_euclid_adapter_refuses_legacy_authority(tmp_path):
    from euclid.organ_adapters.specialists import TriadCustodyOrgan

    triad = open_triad(
        storage_profile=LEGACY_OVID_PROFILE,
        ovid_root=tmp_path / "legacy",
        bind_chronus=False,
    )
    with pytest.raises(ValueError, match="requires theseus-custody"):
        TriadCustodyOrgan(triad)


def test_foreign_directory_not_adopted(tmp_path):
    (tmp_path / "ovid_index.json").write_text("{}")
    with pytest.raises(TheseusError, match="reconciliation"):
        open_theseus(durable_dir=tmp_path)
    assert (tmp_path / "ovid_index.json").read_text() == "{}"


def test_hard_exit_after_journal_preserves_uncertain_evidence(tmp_path):
    root = tmp_path / "custody"
    t = open_theseus(durable_dir=root)
    t.put(b"original")
    index_before = (root / "theseus_index.json").read_bytes()
    bootstrap = os.environ.get("AETHEL_SUBSET_BOOTSTRAP", "")
    code = (
        bootstrap
        + "\nfrom aethel.theseus import open_theseus\nimport os\n"
        + (
            f"t=open_theseus(durable_dir={str(root)!r})\n"
            "t._write_index=lambda *_: os._exit(73)\n"
            't.put(b"interrupted process mutation")\n'
        )
    )
    child = subprocess.run(
        [sys.executable, "-O" if not __debug__ else "-B", "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert child.returncode == 73, child.stderr
    assert (root / "theseus_index.json").read_bytes() == index_before
    journal = root / "durable/ledger.jsonl"
    before = journal.read_bytes()
    assert len(before.splitlines()) == 2
    with pytest.raises(TheseusError, match="reconciliation"):
        open_theseus(durable_dir=root)
    assert journal.read_bytes() == before


def test_legacy_form_preserves_stored_lineage(tmp_path):
    from aethel.ovid_authority import open_ovid_authority

    store = open_ovid_authority(tmp_path)
    obj = store.put(b"original lineage", parents=("parent:known",))
    restored = open_ovid_authority(tmp_path).get_form(obj.object_id)
    assert restored.lineage == obj.lineage
    assert restored.lineage.parent_ids == ("parent:known",)


def test_legacy_stored_fold_tamper_rejected(tmp_path):
    from aethel.ovid_authority import OvidAuthorityError, open_ovid_authority

    store = open_ovid_authority(tmp_path)
    obj = store.put(b"fold tamper")
    path = tmp_path / "objects" / f"{obj.object_id}.json"
    doc = json.loads(path.read_text())
    doc["working_form"]["blocks"][0][1] = 0
    path.write_text(json.dumps(doc))
    with pytest.raises(OvidAuthorityError, match="stored folded representation"):
        store.get_bytes(obj.object_id)
    assert store.verify() is False


def test_legacy_projection_metadata_tamper_not_equal(tmp_path):
    from aethel.ovid_authority import open_ovid_authority
    from aethel.theseus_projection import open_theseus_projection

    store = open_ovid_authority(tmp_path / "legacy")
    obj = store.put(b"projection integrity")
    projection = open_theseus_projection(tmp_path / "projection", store)
    generation = projection.rebuild()
    assert projection.compare_to_ovid()["equal"] is True
    projection._rows[obj.object_id]["raw_len"] += 1
    assert projection.compare_to_ovid()["equal"] is False
    assert projection.rebuild() == generation
    projection.generation = "fabricated"
    assert projection.compare_to_ovid()["equal"] is False
