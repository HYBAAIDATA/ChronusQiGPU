"""Offline re-verification of tests/vectors/mainnet_975565_976064.json (on-chain data, not performance evidence)."""
import hashlib
import json
from pathlib import Path

import pytest

VECTOR = Path(__file__).parent / "vectors" / "mainnet_975565_976064.json"
START, END = 976064, 975565
# Bitcoin mainnet consensus powLimit (not the rounded difficulty-1 target).
MAINNET_POW_LIMIT = (1 << 224) - 1


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _target(nbits: int) -> int:
    if type(nbits) is not int or not 0 <= nbits <= 0xFFFFFFFF:
        raise ValueError("nBits must be an unsigned 32-bit integer")
    if nbits & 0x00800000:
        raise ValueError("Negative compact target")
    exponent, mantissa = nbits >> 24, nbits & 0x007FFFFF
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    if not 0 < target < (1 << 256):
        raise ValueError("Compact target must be positive and fit uint256")
    if target > MAINNET_POW_LIMIT:
        raise ValueError("Compact target exceeds mainnet proof-of-work limit")
    return target


@pytest.mark.parametrize(("nbits", "expected"), [
    (0x01123456, 0x12),
    (0x02012345, 0x123),
    (0x03012345, 0x12345),
    (0x04012345, 0x1234500),
    (0x1D00FFFF, 0xFFFF << 208),
    (0x17021673, 0x021673 << 160),
    (0x1701E5AC, 0x01E5AC << 160),
])
def test_target_decodes_valid_compact_values(nbits, expected):
    assert _target(nbits) == expected


@pytest.mark.parametrize("nbits", [
    -1, 1 << 32,
    0x1D80FFFF,  # negative
    0, 0x1D000000, 0x01000001,  # zero, including after right shift
    0x23000001, 0x22000100, 0x21010000,  # uint256 overflow boundaries
    0x1D010000, 0x207FFFFF,  # above mainnet limit, including regtest limit
])
def test_target_rejects_invalid_compact_values(nbits):
    with pytest.raises(ValueError):
        _target(nbits)


def _load():
    return json.loads(VECTOR.read_text(encoding="utf-8"))


def test_contract_count_and_uniqueness():
    doc = _load()
    assert START - END + 1 == 500
    assert len(doc["blocks"]) == 500 and len(doc["nonces"]) == 500
    assert len(set(doc["nonces"])) == 500
    assert all(0 <= n < 2**32 for n in doc["nonces"])
    assert [b["height"] for b in doc["blocks"]] == [START - i for i in range(500)]


def test_every_header_hashes_to_block_hash_under_target():
    doc = _load()
    for i, block in enumerate(doc["blocks"]):
        header = bytes.fromhex(block["header_hex"])
        assert len(header) == 80
        digest = _sha256d(header)
        assert digest[::-1].hex() == block["block_hash_be"], block["height"]
        fields = block["fields"]
        assert int.from_bytes(header[72:76], "little") == fields["nbits"]
        assert fields["nbits_hex"] == f"{fields['nbits']:08x}"
        assert int.from_bytes(digest, "little") <= _target(fields["nbits"]), block["height"]
        assert int.from_bytes(header[76:80], "little") == fields["nonce"] == doc["nonces"][i]
        assert int.from_bytes(header[0:4], "little") == fields["version"]
        assert header[4:36][::-1].hex() == fields["prevhash"]
        assert header[36:68][::-1].hex() == fields["merkle_root"]
        assert int.from_bytes(header[68:72], "little") == fields["ntime"]


def test_headers_chain_by_prevhash():
    blocks = _load()["blocks"]
    for newer, older in zip(blocks, blocks[1:]):
        assert newer["fields"]["prevhash"] == older["block_hash_be"]
