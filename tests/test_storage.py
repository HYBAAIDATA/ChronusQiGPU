"""Phyllotaxis storage and Theseus reconstruction tests."""

import hashlib

import pytest

from chronus.security.ovid import OVIDStorage
from chronus.storage import (
    GOLDEN_RATIO_CONJUGATE_64,
    PhyllotaxisMesh,
    TheseusService,
    golden_angle_hash,
    golden_lane,
    metallic_conjugate_64,
    metallic_lane,
    phyllotaxis_coordinate,
)
from chronus.storage.theseus import StorageIntegrityError


def test_golden_lane_uses_golden_ratio_constant():
    # 0x9E3779B97F4A7C15 is floor(2**64 * (phi - 1)); compare at fixed-point
    # precision because 2**64 * (phi - 1) exceeds float53 exactness.
    assert abs(GOLDEN_RATIO_CONJUGATE_64 / 2**64 - (5**0.5 - 1) / 2) < 2**-60
    digest = hashlib.sha256(b"chronus").digest()
    lane = golden_lane(digest, 32)
    assert 0 <= lane < 32
    key = int.from_bytes(digest[:8], "big")
    assert lane == ((key * GOLDEN_RATIO_CONJUGATE_64) % 2**64 * 32) >> 64


def test_golden_lane_distributes_uniformly_over_32_lanes():
    lanes = [
        golden_lane(hashlib.sha256(i.to_bytes(4, "big")).digest(), 32)
        for i in range(3200)
    ]
    counts = [lanes.count(lane) for lane in range(32)]
    assert all(counts)  # every lane used
    assert max(counts) - min(counts) <= 50  # no lane dominates


def test_phyllotaxis_coordinate_uses_golden_turns():
    coordinate = phyllotaxis_coordinate(1, b"\x00" * 32, 32)
    # F64 / F66 approximates 1/phi**2; sequence 1 turns by that fraction.
    fibs = [0, 1]
    while len(fibs) < 68:
        fibs.append(fibs[-1] + fibs[-2])
    assert coordinate.golden_turns_numerator == fibs[64]
    assert coordinate.golden_turns_denominator == fibs[66]
    ratio = fibs[64] / fibs[66]
    assert abs(ratio - (1 / ((1 + 5**0.5) / 2) ** 2)) < 1e-15


@pytest.mark.parametrize("bad", [-1, True, 1.5, "1"])
def test_phyllotaxis_rejects_invalid_sequence(bad):
    with pytest.raises(ValueError):
        phyllotaxis_coordinate(bad, b"\x00" * 32, 32)


def test_mesh_map_key_is_deterministic_and_in_range():
    mesh = PhyllotaxisMesh(lanes=32)
    lane, coords = mesh.map_key("test_payload_vector")
    assert lane == 4  # regression vector: sha256("test_payload_vector") golden hash
    assert coords["lane"] == lane
    assert 0 <= coords["golden_angle_position"] < 2**64
    assert coords["turn_fraction"][1] == 2**64
    assert mesh.map_key("test_payload_vector") == (lane, coords)
    assert mesh.map_key(b"test_payload_vector") == (lane, coords)


def test_mesh_distributes_keys_and_validates():
    mesh = PhyllotaxisMesh(lanes=32)
    lanes = [mesh.map_key(f"key-{i}")[0] for i in range(3200)]
    assert len(set(lanes)) == 32
    assert (
        abs(
            golden_angle_hash("k") / 2**64
            - (
                int.from_bytes(hashlib.sha256(b"k").digest(), "big")
                * GOLDEN_RATIO_CONJUGATE_64
                % 2**64
            )
            / 2**64
        )
        == 0
    )
    for bad in ("", b"", None, 5):
        with pytest.raises(ValueError):
            mesh.map_key(bad)
    with pytest.raises(ValueError):
        PhyllotaxisMesh(lanes=0)


def test_metallic_conjugates_are_exactly_derived():
    assert metallic_conjugate_64(1) == GOLDEN_RATIO_CONJUGATE_64
    # frac(sigma_2) = sqrt(2) - 1 (float64 reference: tolerance covers float rounding)
    assert abs(metallic_conjugate_64(2) / 2**64 - (2**0.5 - 1)) < 2**-50
    # Silver constant is the fractional part of 1 + sqrt(2), not the SHA IV.
    assert metallic_conjugate_64(2) == 0x6A09E667F3BCC908
    with pytest.raises(ValueError):
        metallic_conjugate_64(0)


def test_multiscale_mesh_uses_independent_metallic_lenses():
    mesh = PhyllotaxisMesh(lanes=32)
    mapping = mesh.map_key_multiscale("vector-embedding-7")
    assert 0 <= mapping["golden_lane"] < 32
    assert 0 <= mapping["silver_partition"] < 8
    assert 0 <= mapping["bronze_route"] < 4
    digest = hashlib.sha256(b"vector-embedding-7").digest()
    assert mapping["silver_partition"] == metallic_lane(digest, 8, 2)
    assert mapping["bronze_route"] == metallic_lane(digest, 4, 3)
    # Tiers are independent: changing lanes changes only that tier.
    assert mesh.map_key_multiscale("vector-embedding-7") == mapping


def test_theseus_store_query_reconstruct_round_trip():
    service = TheseusService(OVIDStorage())
    record = service.store("tenant-a", b"folded-state")
    assert record.size_bytes == 12
    assert record.object_id == hashlib.sha256(b"folded-state").hexdigest()
    assert service.query("tenant-a") == [record.object_id]
    assert service.query("tenant-b") == []
    assert service.reconstruct("tenant-a", record.object_id) == b"folded-state"
    with pytest.raises(KeyError):
        service.reconstruct("tenant-b", record.object_id)


def test_theseus_assigns_distinct_spiral_coordinates():
    service = TheseusService(OVIDStorage())
    first = service.store("t", b"one")
    second = service.store("t", b"two")
    assert first.coordinate.sequence == 0
    assert second.coordinate.sequence == 1
    assert first.coordinate != second.coordinate


def test_theseus_deduplicates_identical_content_for_same_tenant():
    service = TheseusService(OVIDStorage())
    first = service.store("t", b"same")
    second = service.store("t", b"same")
    assert first == second
    assert len(service.query("t")) == 1


def test_theseus_fails_closed_on_content_mismatch():
    ovid = OVIDStorage()
    service = TheseusService(ovid)
    record = service.store("t", b"original")
    ovid._store[record.object_id] = b"tampered"
    with pytest.raises(StorageIntegrityError):
        service.reconstruct("t", record.object_id)


def test_theseus_validates_inputs():
    service = TheseusService(OVIDStorage())
    for bad_payload in (b"", "", None, b"x" * (1024 * 1024 + 1)):
        with pytest.raises(ValueError):
            service.store("t", bad_payload)
    with pytest.raises(ValueError):
        service.store("", b"x")
    with pytest.raises(ValueError):
        TheseusService(OVIDStorage(), lane_count=0)
