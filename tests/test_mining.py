import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from chronus.execution import mining
from chronus.execution.mining import partition_nonce_range, search_nonce_range
from chronus.execution.structural import (
    fold_pair,
    unfold_pair,
    zeckendorf_decode,
    zeckendorf_encode,
    zeckendorf_increment,
)
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service, service_config
from chronus.service.routers import workloads
from chronus.service.workload_store import SQLiteWorkloadStore


GENESIS_HEADER = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49ffff001d1dac2b7c"
)
GENESIS_NONCE = 2083236893
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"


@pytest.mark.parametrize("size", [1, 31, 32, 33, 1000])
def test_partition_is_disjoint_and_complete(size):
    partitions = partition_nonce_range(100, 100 + size)
    assert len(partitions) == 32
    assert partitions[0][0] == 100
    assert partitions[-1][1] == 100 + size
    assert all(left[1] == right[0] for left, right in zip(partitions, partitions[1:]))
    assert sum(stop - start for start, stop in partitions) == size


def test_genesis_hash_and_little_endian_target():
    result = search_nonce_range(
        GENESIS_HEADER, GENESIS_NONCE, GENESIS_NONCE + 1, int(GENESIS_HASH, 16)
    )
    assert result["tested"] == 1
    assert result["matches"] == [{"nonce": GENESIS_NONCE, "hash": GENESIS_HASH}]
    assert result["execution_mode"] == "SOFTWARE_EXECUTION"
    assert (
        search_nonce_range(
            GENESIS_HEADER, GENESIS_NONCE, GENESIS_NONCE + 1, int(GENESIS_HASH, 16) - 1
        )["match_count"]
        == 0
    )


def test_parallel_results_match_independent_hashlib_reference():
    start, stop = 123, 173
    result = search_nonce_range(GENESIS_HEADER, start, stop, (1 << 256) - 1, workers=2)
    assert result["tested"] == 50
    assert result["match_count"] == 50
    assert result["matches_truncated"]
    for match in result["matches"]:
        header = GENESIS_HEADER[:76] + match["nonce"].to_bytes(4, "little")
        expected = hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex()
        assert match["hash"] == expected


def test_zeckendorf_step_order_finds_identical_matches():
    header = bytes(range(80))
    target = 1 << 200  # generous target so matches exist in a small range
    binary = search_nonce_range(header, 0, 4096, target, workers=1, step_order="binary")
    folded = search_nonce_range(
        header, 0, 4096, target, workers=1, step_order="zeckendorf"
    )
    assert binary["tested"] == folded["tested"] == 4096
    assert binary["match_count"] == folded["match_count"]
    assert {m["nonce"] for m in binary["matches"]} == {
        m["nonce"] for m in folded["matches"]
    }
    assert folded["step_order"] == "zeckendorf"
    with pytest.raises(ValueError, match="step_order"):
        search_nonce_range(header, 0, 10, target, step_order="spiral")


def test_polyhedral_lane_labels_cover_12_faces_and_20_vertices():
    labels = [mining.polyhedral_lane(lane) for lane in range(32)]
    faces = [l for l in labels if l["polyhedral"] == "dodecahedron-face"]
    vertices = [l for l in labels if l["polyhedral"] == "icosahedron-vertex"]
    assert len(faces) == 12 and len(vertices) == 20
    assert [f["index"] for f in faces] == list(range(12))
    assert [v["index"] for v in vertices] == list(range(20))
    with pytest.raises(ValueError):
        mining.polyhedral_lane(32)


def test_zeckendorf_increment_is_carry_free_and_bijective():
    indices = ()
    seen = []
    for expected in range(1, 3000):
        indices = zeckendorf_increment(indices)
        # Canonicality after every step: non-adjacent descending indices.
        assert all(left - right >= 2 for left, right in zip(indices, indices[1:]))
        seen.append(zeckendorf_decode(indices))
        assert seen[-1] == expected
    assert len(set(seen)) == len(seen)  # bijective traversal, no collisions


def test_zeckendorf_increment_matches_encode_of_successor():
    for value in [0, 1, 2, 3, 10, 100, 4180, 6765, 2**40 + 12345]:
        assert (
            zeckendorf_decode(zeckendorf_increment(zeckendorf_encode(value)))
            == value + 1
        )


def test_search_store_option_records_theseus_receipt():
    from chronus.execution import NativeMathReferenceBackend

    backend = NativeMathReferenceBackend()
    payload = json.dumps(
        {
            "header_hex": bytes(range(80)).hex(),
            "target_hex": f"{1 << 200:064x}",
            "start": 0,
            "stop": 1024,
            "step": "zeckendorf",
            "store": True,
        }
    ).encode()
    result = backend.execute(payload, "SHA256D_NONCE_SEARCH")
    receipt = result["theseus_receipt"]
    assert result["step_order"] == "zeckendorf"
    assert 0 <= receipt["coordinate"]["lane"] < 32
    assert result["durable"] is False
    bad = json.dumps(
        {
            "header_hex": bytes(range(80)).hex(),
            "target_hex": f"{1:064x}",
            "start": 0,
            "stop": 10,
            "store": False,
        }
    ).encode()
    with pytest.raises(ValueError, match="store"):
        backend.execute(bad, "SHA256D_NONCE_SEARCH")


def test_canonical_zeckendorf_round_trip():
    for value in range(1000):
        encoded = zeckendorf_encode(value)
        assert zeckendorf_decode(encoded) == value
        assert all(a - b >= 2 for a, b in zip(encoded, encoded[1:]))


def test_m15_byte_map_is_bijective():
    for a in range(256):
        for b in range(256):
            assert unfold_pair(*fold_pair(a, b)) == (a, b)


def test_search_api_executes_genesis_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(service_config, "execution_backend_url", None)
    monkeypatch.setattr(
        workloads, "workload_store", SQLiteWorkloadStore(str(tmp_path / "test.sqlite3"))
    )
    auth_service.register_tenant("mining-test", "mining-test-token")
    payload = json.dumps(
        {
            "header_hex": GENESIS_HEADER.hex(),
            "start": GENESIS_NONCE,
            "stop": GENESIS_NONCE + 1,
            "target_hex": GENESIS_HASH,
        }
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer mining-test-token"},
            json={
                "tenant_id": "mining-test",
                "workload_type": "SHA256D_NONCE_SEARCH",
                "payload_bytes": payload,
            },
        )
    assert response.status_code == 202
    assert response.json()["result"]["result"]["matches"][0]["hash"] == GENESIS_HASH
