"""Real mainnet corpus integration: oracle parity and durable folded search.

Known nonce windows are correctness controls, not prediction or performance evidence.
No pool, credentials, mocked hash, or synthetic header is used.
"""
import hashlib
import json
from pathlib import Path

import pytest

from chronus.execution.sha256d_oracle import Sha256dTargetOracle, target_from_bits
from chronus.ovid.folded_custody import OvidAdapter, OvidFoldedAdapter, TheseusAdapter
from chronus.triad import open_production_triad

pytestmark = pytest.mark.real
CORPUS = Path(__file__).parent / "vectors" / "mainnet_975565_976064.json"
MASK = (1 << 32) - 1


def _rows():
    return json.loads(CORPUS.read_text(encoding="utf-8"))["blocks"]


def test_actual_oracle_against_every_mainnet_header():
    raw = CORPUS.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "3db2d4a97543f8ae786691a193eff8cf6b7e5922208beff05340c3f08413cc76"
    )
    rows = _rows()
    assert len(rows) == 500
    for block in rows:
        header = bytes.fromhex(block["header_hex"])
        oracle = Sha256dTargetOracle(header[:76], target_from_bits(block["fields"]["nbits"]))
        nonce = block["fields"]["nonce"]
        value = (oracle.ntime << 32) | nonce
        assert oracle(value), block["height"]
        assert oracle.verify(value) == (True, block["block_hash_be"])
        assert (oracle.evaluations, oracle.midstates, oracle.compressions) == (1, 1, 3)


def _reference_window(prefix, target, base, width):
    hits = {}
    for offset in range(width):
        nonce = (base + offset) & MASK
        header = prefix + nonce.to_bytes(4, "little")
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        if int.from_bytes(digest, "little") <= target:
            hits[nonce] = digest[::-1].hex()
    return hits


@pytest.mark.parametrize("row_index", [0, 124, 249, 374, 499])
def test_real_header_triad_search_and_restart(tmp_path, row_index):
    block = _rows()[row_index]
    header = bytes.fromhex(block["header_hex"])
    prefix = header[:76]
    nonce = int.from_bytes(header[76:], "little")
    target = target_from_bits(int.from_bytes(header[72:76], "little"))
    width = 32
    base = nonce & ~(width - 1)
    triad = open_production_triad(tmp_path)
    tenant = f"block-{block['height']}"
    results = []
    for start in (base, (base + width) & MASK):
        reference = _reference_window(prefix, target, start, width)
        result = triad.exact_grover_search(tenant, prefix, target, start, num_generators=5)
        search = result["result"]
        assert search.found == bool(reference)
        assert search.marked_count == len(reference)
        assert result["oracle_evaluations"] == width
        assert search.states_materialised == width
        if reference:
            assert result["verified"]
            assert result["nonce"] in reference
            assert result["digest"] == reference[result["nonce"]]
            assert result["confirm_compressions"] == 3
        else:
            assert result["nonce"] is None and not result["verified"]
            assert result["confirm_compressions"] == 0
        results.append(result)

    assert triad.theseus.verify_journal_continuity(tenant)
    reopened = open_production_triad(tmp_path)
    assert reopened.theseus.verify_journal_continuity(tenant)
    adapter = OvidFoldedAdapter(OvidAdapter(reopened.ovid), TheseusAdapter(reopened.theseus, tenant))
    for result in results:
        handle = adapter.restore_from_theseus(result["result"].artifact_id)
        if result["verified"]:
            assert handle.register.active_dimension == 0
            assert handle.register.unfold_mk().readout_winner()[1][1] == result["nonce"]
        else:
            assert handle.version == 0
            assert handle.register.active_dimension == 5
