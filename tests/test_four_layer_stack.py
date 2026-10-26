"""Tests for the four-layer mining stack (Aethel → Tensor → TURING → iGPU).

Validates the Wiring role map end to end with honesty laws enforced:
measured fold ratios (never asserted multipliers), lossless fold roundtrips,
Cassini integrity, amplitude (Schmidt) spectrum, the Grover analogue as
probe-order reordering, and the real double-SHA256 consensus as the sole
accept authority.
"""

import hashlib
import os
import struct
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_DIR = os.path.dirname(_THIS_DIR)

for p in (_PYTHIA_DIR, os.path.abspath(".")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from Intelligence.four_layer_stack import (
    AethelStore,
    FourLayerMiningStack,
    TensorFoldEngine,
    TuringLayer,
    _double_sha256,
)

HEADER = bytes(range(80))
TARGET = b"\xff" * 31 + b"\x7f"  # near-max: early winner


# ---------------------------------------------------------------------------
# Layer 1 — Aethel: folded storage, measured ratio, lossless retrieval
# ---------------------------------------------------------------------------


def test_aethel_store_retrieve_lossless():
    aethel = AethelStore()
    payload = os.urandom(256)
    aethel.store("payload", payload)
    assert aethel.retrieve("payload") == payload


def test_aethel_measures_ratio_dont_assert_multiplier():
    aethel = AethelStore()
    rec = aethel.store("payload", os.urandom(256))
    # The ratio is measured, present, and never a hardcoded 20x claim.
    assert rec["measured_ratio"] > 0.0
    assert rec["truth_class"] == "measured"
    assert aethel.capacity_multiplier() == pytest.approx(1.0 / rec["measured_ratio"])


def test_aethel_cassini_fingerprint_alternates():
    aethel = AethelStore()
    r1 = aethel.store("a", b"1")
    r2 = aethel.store("b", b"2")
    assert r1["cassini_fingerprint"] == -r2["cassini_fingerprint"]


def test_aethel_missing_address_returns_none():
    assert AethelStore().retrieve("nope") is None


# ---------------------------------------------------------------------------
# Layer 2 — Tensor: golden-basis fold + Schmidt spectrum
# ---------------------------------------------------------------------------


def test_tensor_fold_roundtrip_lossless():
    tensor = TensorFoldEngine()
    raw = os.urandom(64)
    folded, _ = tensor.compress(raw)
    assert tensor.decompress(folded) == raw


def test_tensor_schmidt_spectrum_normalized():
    tensor = TensorFoldEngine()
    spec = tensor.schmidt_spectrum([3.0, 1.0, 1.0])
    assert spec["truth_class"] == "computed"
    assert spec["schmidt_values_sq"][0] >= spec["schmidt_values_sq"][-1]
    assert spec["bond_dimension_effective"] > 0.0
    assert spec["entropy_bits"] > 0.0


def test_tensor_schmidt_uniform_maximizes_bond_dimension():
    tensor = TensorFoldEngine()
    uniform = tensor.schmidt_spectrum([1.0] * 16)
    peaked = tensor.schmidt_spectrum([100.0] + [0.001] * 15)
    assert uniform["bond_dimension_effective"] > peaked["bond_dimension_effective"]


def test_tensor_schmidt_empty_input():
    spec = TensorFoldEngine().schmidt_spectrum([])
    assert spec["bond_dimension_effective"] == 0.0


# ---------------------------------------------------------------------------
# Layer 3 — TURING: symbolic Hilbert space, exact schedule, Cassini
# ---------------------------------------------------------------------------


def test_turing_hilbert_space_symbolic_not_materialized():
    layer = TuringLayer(n_qubits=10000)
    assert layer.hilbert_dim_symbolic == "2^10000"
    status = layer.status()
    assert status["materialized"] is False
    assert status["truth_class"] == "symbolic_exact"


def test_turing_schedule_deterministic():
    layer = TuringLayer()
    s1 = layer.prepare(HEADER, cap=64)
    s2 = layer.prepare(HEADER, cap=64)
    assert s1 == s2
    assert len(s1) == 64


def test_turing_cassini_holds():
    layer = TuringLayer()
    assert layer.cassini_holds(7) is True
    assert layer.cassini_holds(15) is True


# ---------------------------------------------------------------------------
# Layers 1-4 wired: mine_block end to end
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def stack_result():
    stack = FourLayerMiningStack(n_qubits=10000)
    return stack, stack.mine_block(HEADER, TARGET, n_candidates=64)


def test_mine_block_accepted(stack_result):
    _stack, result = stack_result
    assert result["accepted"] is True, result


def test_mine_block_consensus_bit_exact(stack_result):
    _stack, result = stack_result
    igpu = result["layers"]["igpu"]
    nonce = igpu["winning_nonce"]
    blob = HEADER[:76] + struct.pack("<I", nonce)
    digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
    assert digest[::-1] < TARGET
    assert igpu["recheck_bit_exact"] is True


def test_mine_block_cassini_and_fold(stack_result):
    _stack, result = stack_result
    assert result["cassini_holds"] is True
    assert result["fold_roundtrip_lossless"] is True


def test_mine_block_all_four_layers_reported(stack_result):
    _stack, result = stack_result
    assert set(result["layers"]) == {"aethel", "tensor", "turing", "igpu"}


def test_mine_block_turing_stays_symbolic(stack_result):
    _stack, result = stack_result
    assert result["layers"]["turing"]["hilbert_dim"] == "2^10000"
    assert result["layers"]["turing"]["materialized"] is False


def test_mine_block_theorem_proven_false(stack_result):
    _stack, result = stack_result
    assert result["theorem_proven"] is False


def test_mine_block_evidence_chain_stored(stack_result):
    stack, result = stack_result
    assert result["evidence_store"]["address"] == "evidence:latest"
    assert "evidence:latest" in stack.aethel


def test_double_sha256_reference():
    blob = b"abc"
    once = hashlib.sha256(blob).digest()
    assert _double_sha256(blob) == hashlib.sha256(once).digest()
