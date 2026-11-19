"""PULVINI complete-state replay, including retained kernels, through THESEUS.

Only the integration test using ProductionTriad establishes local SQLite
custody. Test data are deterministic fixtures, not customer runtime evidence.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from chronus.pulvini.custody import (
    PulviniCustodyAdapter, decode_complete_fold,
    encode_complete_fold,
)
from chronus.tensor.folded_compute import FoldedTensorExecutor
from chronus.triad import ProductionTriad

pytestmark = pytest.mark.simulated


@pytest.mark.parametrize("shape", [(17,), (2, 7), (), (3, 4, 2)])
def test_complete_fold_retains_all_kernels(shape):
    array = np.arange(np.prod(shape), dtype=float).reshape(shape)
    executor = FoldedTensorExecutor(depth=3)
    encoded = encode_complete_fold(executor.fold(array))
    decoded = decode_complete_fold(encoded)
    np.testing.assert_allclose(executor.materialise(decoded), array,
                               rtol=1e-12, atol=1e-12)
    assert decoded.evidence.retained_bytes == (
        decoded.evidence.folded_bytes + decoded.evidence.kernel_bytes
    )


@pytest.mark.parametrize("failure", ["header", "trailing", "payload"])
def test_corrupt_fold_record_fails_closed(failure):
    executor = FoldedTensorExecutor(depth=3)
    encoded = bytearray(encode_complete_fold(executor.fold(np.arange(20, dtype=float))))
    if failure == "header":
        encoded[4:8] = b"\xff\xff\xff\xff"
    elif failure == "trailing":
        encoded.extend(b"x")
    else:
        encoded[-1] ^= 1
    with pytest.raises((ValueError, TypeError)):
        decode_complete_fold(bytes(encoded))


def test_restarted_canonical_triad_reconstructs_complete_fold(tmp_path):
    database = tmp_path / "theseus.sqlite3"
    array = np.arange(42, dtype=float).reshape(6, 7)
    adapter = PulviniCustodyAdapter(ProductionTriad(str(database)), depth=3)
    receipt = adapter.put("tenant-a", array)
    restarted = PulviniCustodyAdapter(ProductionTriad(str(database)), depth=3)
    operand = restarted.read(receipt)
    np.testing.assert_allclose(restarted.executor.materialise(operand), array,
                               rtol=1e-12, atol=1e-12)
    tampered = replace(receipt, artifact_sha256="0" * 64)
    with pytest.raises(ValueError, match="hash mismatch"):
        restarted.read(tampered)


def test_bad_tenant_fails_before_custody(tmp_path):
    adapter = PulviniCustodyAdapter(ProductionTriad(str(tmp_path / "triad.sqlite3")))
    with pytest.raises(ValueError, match="tenant_id"):
        adapter.put("", np.arange(14, dtype=float))


def test_over_limit_fold_rejected_before_custody(tmp_path):
    adapter = PulviniCustodyAdapter(ProductionTriad(str(tmp_path / "triad.sqlite3")))
    with pytest.raises(ValueError, match="payload bound"):
        adapter.put("a", np.ones((1_000, 120), dtype=float))


def test_reject_unsupported_tensor_rank_before_custody(tmp_path):
    adapter = PulviniCustodyAdapter(ProductionTriad(str(tmp_path / "rank.sqlite3")), depth=1)
    with pytest.raises(ValueError, match="rank"):
        adapter.put("tenant", np.ones((1,) * 9, dtype=float))


def test_fold_replay_does_not_attest_unsigned_origin():
    executor = FoldedTensorExecutor(depth=3)
    payload = encode_complete_fold(executor.fold(np.arange(12, dtype=float)))
    decoded = decode_complete_fold(payload)
    assert decoded.source_digest_authentication == "UNVERIFIED_UNSIGNED_ORIGIN"
    assert decoded.evidence.input_sha256
    assert "source" not in decoded.source_digest_authentication.lower() or "UNVERIFIED" in decoded.source_digest_authentication


def test_forged_source_attestation_rejected_before_read(tmp_path):
    adapter = PulviniCustodyAdapter(ProductionTriad(str(tmp_path / "origin.sqlite3")))
    record = adapter.put("tenant", np.arange(12, dtype=float))
    forged = replace(record, source_attestation="SIGNED_INDEPENDENTLY")
    with pytest.raises(ValueError, match="source provenance"):
        adapter.read(forged)
