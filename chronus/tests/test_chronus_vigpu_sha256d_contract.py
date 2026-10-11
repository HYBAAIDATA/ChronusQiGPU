"""SHA256d execution contract for the Virtual iGPU, pinned to real Bitcoin vectors."""

from __future__ import annotations

import hashlib

import pytest

from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import AdapterUnavailable, CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon

# Bitcoin mainnet genesis block header (80 bytes, little-endian fields).
GENESIS_HEADER = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)
GENESIS_NONCE = 2083236893
# Published block hash (display order); the consensus digest is its byte reversal.
GENESIS_HASH_DISPLAY = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_DIGEST_HEX = bytes.fromhex(GENESIS_HASH_DISPLAY)[::-1].hex()
GENESIS_TARGET = 0xFFFF * 2 ** (8 * (0x1D - 3))  # nBits 0x1d00ffff


@pytest.fixture()
def daemon(tmp_path):
    return RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "rt")


def _scan(daemon, wid, **fields):
    base = {
        "header80_hex": GENESIS_HEADER.hex(),
        "target_hex": f"{GENESIS_TARGET:064x}",
    }
    base.update(fields)
    return daemon.submit(
        Workload(
            id=wid,
            kind=WorkloadKind.SHA256D_SCAN,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input=base,
        )
    )


def test_known_vector_matches_published_genesis_hash() -> None:
    assert len(GENESIS_HEADER) == 80
    assert GENESIS_HEADER[76:80] == GENESIS_NONCE.to_bytes(4, "little")
    digest = hashlib.sha256(hashlib.sha256(GENESIS_HEADER).digest()).digest()
    assert digest.hex() == GENESIS_DIGEST_HEX


def test_scan_assembles_header76_plus_little_endian_nonce(daemon) -> None:
    result = _scan(daemon, "gen", start_nonce=GENESIS_NONCE, count=1)
    hit = result.output["hits"][0]
    assert hit["nonce"] == GENESIS_NONCE
    assert hit["hash_hex"] == GENESIS_DIGEST_HEX
    assert result.output["checked"] == 1


def test_scan_ignores_nonce_bytes_embedded_in_header80(daemon) -> None:
    wrong = GENESIS_HEADER[:76] + (0).to_bytes(4, "little")
    result = _scan(
        daemon, "wrong-embedded", header80_hex=wrong.hex(), start_nonce=GENESIS_NONCE, count=1
    )
    assert result.output["hits"][0]["hash_hex"] == GENESIS_DIGEST_HEX


def test_range_scan_work_count_stops_at_first_hit(daemon) -> None:
    result = _scan(daemon, "range", start_nonce=GENESIS_NONCE - 2, count=5)
    assert [h["nonce"] for h in result.output["hits"]] == [GENESIS_NONCE]
    assert result.output["checked"] == 3  # two misses, then the hit ends the scan


def test_no_hit_counts_every_nonce(daemon) -> None:
    result = _scan(daemon, "miss", target_hex="00" * 32, start_nonce=GENESIS_NONCE, count=7)
    assert result.output["hits"] == []
    assert result.output["checked"] == 7


def test_explicit_nonce_batch_preserves_submitted_order(daemon) -> None:
    batch = [5, GENESIS_NONCE, 9]
    result = _scan(daemon, "explicit", nonces=batch)
    assert result.output["hits"][0]["nonce"] == GENESIS_NONCE
    assert result.output["checked"] == 2  # [5, GENESIS] in submitted order, 9 never reached


@pytest.mark.parametrize(
    "fields",
    [
        {"start_nonce": 0xFFFFFFFF, "count": 2},  # runs past uint32
        {"start_nonce": -1, "count": 1},
        {"start_nonce": 0, "count": 0},
        {"start_nonce": 0, "count": 1_000_001},
        {"nonces": [0x1_0000_0000]},
        {"nonces": [-1]},
        {"nonces": [True]},
        {"nonces": "abc"},
        {"nonces": []},
    ],
)
def test_nonce_bounds_fail_closed(daemon, fields) -> None:
    with pytest.raises(AdapterUnavailable):
        _scan(daemon, "bounds", **fields)


def test_header_must_be_80_bytes_and_target_in_range(daemon) -> None:
    with pytest.raises(AdapterUnavailable, match="80 bytes"):
        _scan(daemon, "short", header80_hex="00" * 79, start_nonce=0, count=1)
    with pytest.raises(AdapterUnavailable, match="uint256"):
        _scan(daemon, "big", target_hex="1" + "00" * 32, start_nonce=0, count=1)


def test_host_verifier_rejects_forged_candidates() -> None:
    from chronus.virtual_igpu.host_verify import CandidateVerificationError, verify_candidate

    prefix = GENESIS_HEADER[:76]
    assert (
        verify_candidate(prefix, GENESIS_NONCE, GENESIS_DIGEST_HEX, GENESIS_TARGET).hex()
        == GENESIS_DIGEST_HEX
    )
    with pytest.raises(CandidateVerificationError, match="mismatch"):
        verify_candidate(prefix, GENESIS_NONCE + 1, GENESIS_DIGEST_HEX, GENESIS_TARGET)
    with pytest.raises(CandidateVerificationError, match="mismatch"):
        verify_candidate(prefix, GENESIS_NONCE, "00" * 32, GENESIS_TARGET)
    with pytest.raises(CandidateVerificationError, match="above target"):
        verify_candidate(prefix, GENESIS_NONCE, GENESIS_DIGEST_HEX, GENESIS_TARGET // 2**40)
    with pytest.raises(CandidateVerificationError, match="outside the admitted range"):
        verify_candidate(
            prefix, GENESIS_NONCE, GENESIS_DIGEST_HEX, GENESIS_TARGET, nonce_range=(0, 10)
        )
    with pytest.raises(CandidateVerificationError, match="outside the admitted batch"):
        verify_candidate(
            prefix, GENESIS_NONCE, GENESIS_DIGEST_HEX, GENESIS_TARGET, allowed_nonces={1, 2}
        )
