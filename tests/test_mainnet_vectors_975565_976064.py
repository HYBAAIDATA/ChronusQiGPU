"""Offline re-verification of tests/vectors/mainnet_975565_976064.json (on-chain data, not performance evidence)."""
import hashlib
import json
from pathlib import Path

VECTOR = Path(__file__).parent / "vectors" / "mainnet_975565_976064.json"
START, END = 976064, 975565


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _target(nbits: int) -> int:
    exponent, mantissa = nbits >> 24, nbits & 0xFFFFFF
    return mantissa << (8 * (exponent - 3))


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
