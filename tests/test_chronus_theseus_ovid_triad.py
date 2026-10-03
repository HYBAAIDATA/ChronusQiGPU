"""Production triad locks: Chronus · Theseus · Ovid.

Locks operator axioms:
  - sunflower/Vogel phyllotaxis packing (golden angle)
  - primes store data (Galois prime keys)
  - folded form is the working form (Ovid)
  - self-heal custody (Theseus)
  - geodesic handoff-only search
  - fail-closed claim boundaries
"""
from __future__ import annotations

import hashlib
import math

import pytest

from aethel.phyllotaxis import (
    GOLDEN_ANGLE,
    GOLDEN_ANGLE_REF,
    pack_from_anchor,
    pack_indices,
    verify_golden_angle_constant,
    vogel_site,
)
from aethel.ovid import CLAIM_BOUNDARY as OVID_CLAIM
from aethel.ovid import open_ovid
from aethel.theseus import CLAIM_BOUNDARY as THESEUS_CLAIM
from aethel.theseus import TheseusError, open_theseus
from aethel.triad import TRIAD_CLAIM_BOUNDARY, open_triad


def test_golden_angle_first_principles():
    assert verify_golden_angle_constant()
    assert abs(GOLDEN_ANGLE - GOLDEN_ANGLE_REF) < 1e-12
    phi = (1 + math.sqrt(5)) / 2
    assert abs(GOLDEN_ANGLE - (2 * math.pi / (phi ** 2))) < 1e-12


def test_phyllotaxis_sunflower_packing_sectors_cover_m32():
    sites = pack_indices(90, buckets=32)
    assert len(sites) == 90
    sectors = {s.sector for s in sites}
    # Dense packing should touch many of the 32 lanes
    assert len(sectors) >= 16
    site0 = vogel_site(0)
    assert site0.radius == 0.0
    site1 = pack_from_anchor(1)
    assert site1.index == 1
    assert 0 <= site1.sector < 32


def test_ovid_fold_is_working_form_roundtrip():
    ovid = open_ovid()
    payload = b"folded-working-form-axiom-" + bytes(range(64))
    form = ovid.metamorphose(payload)
    assert form.verify()
    assert form.raw_len == len(payload)
    assert form.digest == hashlib.sha256(payload).hexdigest()
    assert ovid.materialise(form) == payload
    health = ovid.health()
    assert health["status"] == "ok"
    assert "fold" in OVID_CLAIM.lower() or "working form" in OVID_CLAIM.lower()


def test_ovid_rejects_oversized_payload():
    ovid = open_ovid(max_fold_len=32)
    with pytest.raises(Exception):
        ovid.metamorphose(b"x" * 64)


def test_theseus_put_get_prime_phyllotaxis():
    store = open_theseus(durable=True)
    payload = b"prime-phyllotaxis-custody-" + b"\x01\x02\x03"
    rec = store.put(payload, durable=True)
    assert rec.prime_key != 0 or rec.anchor >= 0
    assert 0 <= rec.phyllotaxis.sector < 32
    assert 0 <= rec.lane < 32
    assert store.get(rec.uuid) == payload
    assert store.verify()
    assert "self-healing" in THESEUS_CLAIM.lower() or "prime" in THESEUS_CLAIM.lower()


def test_theseus_self_heal_from_replica():
    store = open_theseus(durable=True)
    payload = b"heal-me-theseus-ship"
    rec = store.put(payload, durable=True)
    store.corrupt_for_test(rec.uuid, b"BROKEN-PRIMARY")
    assert store.get(rec.uuid) == payload


def test_theseus_unknown_uuid_fail_closed():
    store = open_theseus(durable=False)
    with pytest.raises(TheseusError):
        store.get("no-such-uuid")


def test_theseus_geodesic_handoff_only():
    store = open_theseus(durable=True)
    payload = b"geodesic-point"
    rec = store.put(payload, durable=True)
    point = store.to_manifold_point(rec.uuid)
    assert point.index >= 1
    handoff = store.geodesic()
    # Handoff must not be the search engine itself — adapter surface only
    assert hasattr(handoff, "to_manifold")
    assert hasattr(handoff, "from_manifold") or hasattr(handoff, "retrieve")


def test_triad_open_put_get_health():
    triad = open_triad(durable=True, bind_chronus=False)
    payload = b"triad-db-surface-v1"
    form, back = triad.ovid.round_trip(payload)
    assert back == payload and form.verify()
    rec = triad.put(payload, durable=True)
    assert triad.get(rec.uuid) == payload
    health = triad.health()
    assert health["production_surface"] is True
    assert health["owners"]["theseus"]["status"] == "ok"
    assert health["owners"]["ovid"]["status"] == "ok"
    assert "infinite" not in TRIAD_CLAIM_BOUNDARY.lower()
    assert "preimage" not in TRIAD_CLAIM_BOUNDARY.lower() or "does not" in TRIAD_CLAIM_BOUNDARY.lower()


def test_package_exports_triad_owners():
    import aethel

    assert aethel.open_triad is open_triad
    assert aethel.open_theseus is open_theseus
    assert aethel.open_ovid is open_ovid
    assert aethel.verify_golden_angle_constant()
