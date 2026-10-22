"""Gap closure for Chronus · Theseus · Ovid against the transfer notes.

Locks:
  - the transfer notes exist in the repository in their entirety
  - OVID is the durable authority and survives THESEUS deletion
  - THESEUS is rebuildable from OVID
  - Chronus is optional and is ONE iGPU
  - folded working-form verify checks digest, owner, and sparse witness
  - Chronus virtual memory cannot overwrite another tenant's handle
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aethel.ovid import FoldedWorkingForm, OWNER_ID, open_ovid
from aethel.ovid_authority import open_ovid_authority
from aethel.theseus_projection import open_theseus_projection
from aethel.triad import ONE_IGPU_DEVICE_ID, open_triad
from chronus.igpu.fabric import ComputeFabric
from chronus.igpu.host import HostGPUPlan
from chronus.virtual_igpu.memory import VirtualMemoryPlane


ROOT = Path(__file__).resolve().parents[1]
TRANSFER_NOTES = ROOT / "docs" / "MLA1517_PRIME_DB_TRANSFER_NOTES.md"


def test_transfer_notes_present_in_entirety():
    text = TRANSFER_NOTES.read_text(encoding="utf-8")
    assert text.startswith("# MLA1517 + PRIME-DB — Transfer Notes, Specifications & Build Start")
    required = [
        "## 1. Purpose",
        "## 4. 11D state model",
        "## 23. MLA1517 reference iGPU — completed test handoff",
        "## 25. Canonical product boundary: PRIME-DB + MLA1517 GPU/iGPU",
        "## 39. Complete MLA1517 iGPU integration contract v1.7",
        "## 54. Exact long4 iGPU payload and PRIME-DB tensor persistence v3.4",
        "## 62. Consolidated product architecture — HYBA Assembly",
        "## 63. Evidence-gated sprint build plan",
        "### Immediate next actions",
    ]
    for heading in required:
        assert heading in text, heading
    assert len(text) >= 200_000


def test_ovid_authority_survives_theseus_delete(tmp_path):
    ovid_root = tmp_path / "ovid"
    theseus_root = tmp_path / "theseus"
    authority = open_ovid_authority(ovid_root)
    projection = open_theseus_projection(theseus_root, authority)
    payload = b"ovid-authoritative-folded-state-v1"
    obj = authority.put(payload)
    generation = projection.rebuild()
    assert projection.lookup(obj.object_id).ovid_generation == generation
    assert projection.compare_to_ovid()["equal"] is True
    projection.delete()
    assert not (theseus_root / "theseus_projection.json").exists()
    assert authority.get_bytes(obj.object_id) == payload
    rebuilt = projection.rebuild()
    assert rebuilt == generation
    assert projection.query_ids() == (obj.object_id,)
    assert projection.compare_to_ovid()["equal"] is True


def test_ovid_works_with_chronus_unbound(tmp_path):
    triad = open_triad(durable=True, bind_chronus=False, ovid_root=tmp_path / "ovid")
    payload = b"no-chronus-required"
    obj = triad.ovid_put(payload)
    assert triad.ovid_get(obj.object_id) == payload
    health = triad.health()
    assert health["owners"]["ovid"]["chronus_required"] is False
    assert health["owners"]["chronus"]["bound"] is False
    assert health["owners"]["chronus"]["device_count"] == 0
    assert health["one_igpu"]["required"] is True


def test_chronus_one_igpu_contract():
    plan = HostGPUPlan(8, 4, "standalone", "cpu_reference")
    assert plan.device_count == 1
    with pytest.raises(ValueError):
        HostGPUPlan(8, 4, "standalone", "cpu_reference", device_count=2)
    fabric = ComputeFabric("standalone")
    composed = fabric.compose()
    assert composed["device_count"] == 1
    assert composed["one_igpu"] is True
    assert composed["logical_device"] == ONE_IGPU_DEVICE_ID
    assert composed["contract_device"]["device_id"] == ONE_IGPU_DEVICE_ID


def test_folded_working_form_verify_checks_digest_owner_sparse():
    ovid = open_ovid()
    payload = b"verify-digest-owner-sparse"
    form = ovid.metamorphose(payload)
    assert form.verify()
    assert form.owner == OWNER_ID
    assert form.digest == hashlib.sha256(payload).hexdigest()
    assert form.sparse is not None
    broken_owner = FoldedWorkingForm(
        vector=form.vector,
        sparse=form.sparse,
        digest=form.digest,
        raw_len=form.raw_len,
        folded_units=form.folded_units,
        owner="not-ovid",
        lineage=form.lineage,
    )
    assert broken_owner.verify() is False
    broken_digest = FoldedWorkingForm(
        vector=form.vector,
        sparse=form.sparse,
        digest="00" * 32,
        raw_len=form.raw_len,
        folded_units=form.folded_units,
        owner=OWNER_ID,
        lineage=form.lineage,
    )
    assert broken_digest.verify() is False
    broken_sparse = FoldedWorkingForm(
        vector=form.vector,
        sparse=None,  # type: ignore[arg-type]
        digest=form.digest,
        raw_len=form.raw_len,
        folded_units=form.folded_units,
        owner=OWNER_ID,
        lineage=form.lineage,
    )
    assert broken_sparse.verify() is False


def test_virtual_memory_tenant_isolation(tmp_path):
    plane = VirtualMemoryPlane(tmp_path / "mem")
    a = plane.store(b"same-bytes", tenant="alpha")
    b = plane.store(b"same-bytes", tenant="beta")
    assert a.object_id != b.object_id
    with pytest.raises(PermissionError):
        plane.lookup(a.object_id, tenant="beta")
    rec = plane.lookup(a.object_id, tenant="alpha")
    rec.tenant = "forged"
    assert plane.lookup(a.object_id, tenant="alpha").tenant == "alpha"


def test_virtual_memory_eviction_drops_host_payload(tmp_path):
    plane = VirtualMemoryPlane(tmp_path / "mem", max_host_bytes=30)
    first = plane.store({"blob": "a" * 8}, tenant="t")
    first_size = first.host_resident_bytes
    assert first_size > 0
    plane.store({"blob": "b" * 8}, tenant="t")
    rec = plane.lookup(first.object_id, tenant="t")
    assert rec.host_resident_bytes == 0
    assert rec.payload is None
