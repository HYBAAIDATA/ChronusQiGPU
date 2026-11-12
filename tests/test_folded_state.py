"""Parity and round-trip tests for the period-516 folded F_257[phi] state.

CPU buffer/layout invariants run unconditionally; physical device dispatch is
guarded by pytest.importorskip("pyopencl") plus platform probing.
"""

import hashlib
import re
import struct
import sys
from array import array

import pytest

from chronus.backends.lattice import (
    HardwareUnavailableError,
    ParityVerificationError,
)
from chronus.opencl_folded_adapter import (
    FOLDED_KERNEL_SHA256,
    FOLDED_STATE_SIZE,
    FOLDED_STATE_STRUCT,
    LUT_2064_BYTES,
    LUT_SHA256,
    LUT_TUPLE,
    MAX_FOLDABLE_SCALE,
    MOD,
    PISANO_PERIOD,
    ChronusOpenCLFoldedAdapter,
    build_canonical_2064b_lut,
    f257_phi_mul,
    fold_scale_index,
    iter_folded_batch,
    kernel_source,
    pack_folded_batch,
    step_folded_record,
    unfold_scale_record,
    verify_step_parity,
)

#: Digest of the canonical 2,064-byte uint16 LUT payload (single source of truth).
EXPECTED_LUT_SHA256 = (
    "d2636d5112632065c6cf059d1a49ca5c27e1135b58ff82da025c36a16d0d5a6d"
)

REFERENCE_VECTORS = [10**4, 10**5, 10**12, 10**15, 10**18, 10**20]


def _reference_pairs():
    """Independent recomputation of phi^r in F_257[phi] for cross-checking."""
    pairs = []
    a, b = 1, 0
    for _ in range(PISANO_PERIOD + 1):
        pairs.append((a, b))
        a, b = b, (a + b) % MOD
    return pairs


def test_lut_is_2064_bytes_of_uint16_pairs():
    assert len(LUT_2064_BYTES) == 2064
    assert len(LUT_TUPLE) == PISANO_PERIOD
    flat = array("H")
    flat.frombytes(LUT_2064_BYTES)
    assert flat.itemsize == 2  # uint16 storage, never uint8
    assert len(flat) == 2 * PISANO_PERIOD
    for r, (a, b) in enumerate(LUT_TUPLE):
        assert (flat[2 * r], flat[2 * r + 1]) == (a, b)


def test_lut_digest_is_pinned():
    assert LUT_SHA256 == EXPECTED_LUT_SHA256
    assert hashlib.sha256(LUT_2064_BYTES).hexdigest() == EXPECTED_LUT_SHA256


def test_period_516_is_minimal_and_closed():
    reference = _reference_pairs()
    assert reference[:PISANO_PERIOD] == list(LUT_TUPLE)
    assert reference[PISANO_PERIOD] == (1, 0)  # phi^516 == 1 in F_257[phi]
    assert (1, 0) not in LUT_TUPLE[1:]  # no premature closure: period is minimal
    payload, pairs = build_canonical_2064b_lut()
    assert payload == LUT_2064_BYTES and pairs == LUT_TUPLE


def test_uint16_boundary_at_indices_257_and_258():
    # Residue 256 requires 9 bits: guards against any uint8/uchar downgrade.
    assert LUT_TUPLE[257] == (1, 256)
    assert LUT_TUPLE[258] == (256, 0)
    assert max(max(pair) for pair in LUT_TUPLE) == 256
    for a, b in LUT_TUPLE:
        assert 0 <= a <= 256 and 0 <= b <= 256


def test_folded_state_struct_is_16_bytes():
    assert FOLDED_STATE_SIZE == 16
    assert struct.calcsize("<QHHHH") == 16


def test_known_answer_10_to_the_20():
    record = fold_scale_index(10**20)
    q, r, coeff_a, coeff_b, flags = FOLDED_STATE_STRUCT.unpack(record)
    assert q == 193798449612403100
    assert r == 400
    assert (coeff_a, coeff_b) == (248, 130)
    assert flags == 0


def test_fold_unfold_roundtrip_reference_vectors():
    reference = _reference_pairs()
    for s in REFERENCE_VECTORS:
        record = fold_scale_index(s)
        exact_s, (coeff_a, coeff_b), _flags = unfold_scale_record(record)
        assert exact_s == s  # bijective: zero truncation of the scale index
        q, r = divmod(s, PISANO_PERIOD)
        assert q <= (1 << 64) - 1  # single 64-bit epoch lane suffices
        assert (coeff_a, coeff_b) == reference[r]


def test_roundtrip_boundaries_and_multi_limb_quotient():
    for s in (0, 1, 515, 516, PISANO_PERIOD * (1 << 64) - 1, MAX_FOLDABLE_SCALE):
        exact_s, _, _ = unfold_scale_record(fold_scale_index(s))
        assert exact_s == s
    beyond = 516 * (1 << 64) + 7  # exceeds a single 64-bit epoch lane
    record = fold_scale_index(beyond)
    low_q = (beyond // PISANO_PERIOD) & ((1 << 64) - 1)
    exact_s, _, _ = unfold_scale_record(record, high_q_limbs=(beyond // PISANO_PERIOD) >> 64)
    assert exact_s == beyond
    assert FOLDED_STATE_STRUCT.unpack(record)[0] == low_q


def test_unfold_rejects_corrupted_coefficients():
    record = bytearray(fold_scale_index(10**20))
    record[10] ^= 0xFF  # corrupt coeff_a low byte
    with pytest.raises(ValueError, match="corruption"):
        unfold_scale_record(record)
    with pytest.raises(ValueError, match="outside"):
        unfold_scale_record(fold_scale_index(0)[:8] + b"\xff\x02" + fold_scale_index(0)[10:])
    mismatched = fold_scale_index(0)[:8] + b"\x01\x00" + fold_scale_index(0)[10:]
    with pytest.raises(ValueError, match="corruption"):
        unfold_scale_record(mismatched)  # r=1 but coefficients of r=0
    with pytest.raises(struct.error):
        unfold_scale_record(b"\x00" * 15)


def test_fold_rejects_invalid_input():
    for bad in (-1, 1.5, True, "10"):
        with pytest.raises(ValueError):
            fold_scale_index(bad)  # type: ignore[arg-type]


def test_pack_and_iter_batch_roundtrip():
    scales = REFERENCE_VECTORS + [0, 515, 516]
    buf = pack_folded_batch(scales, flags=7)
    assert len(buf) == 16 * len(scales)
    rows = list(iter_folded_batch(buf))
    assert len(rows) == len(scales)
    for s, (q, r, a, b, flags) in zip(scales, rows):
        assert (q, r) == divmod(s, PISANO_PERIOD)
        assert (a, b) == LUT_TUPLE[r]
        assert flags == 7
    with pytest.raises(ValueError):
        list(iter_folded_batch(buf + b"\x00"))


def test_step_folded_record_matches_divmod_semantics():
    reference = _reference_pairs()
    deltas = [0, 1, 515, 516, 10**4, 10**12, 10**20, (1 << 64) - 1]
    for s in REFERENCE_VECTORS + [0, 515]:
        record = fold_scale_index(s)
        for delta in deltas:
            q0, _r0 = divmod(s, PISANO_PERIOD)
            if q0 + (delta // PISANO_PERIOD) + 1 > (1 << 64) - 1:
                continue  # epoch lane overflow is covered separately
            stepped = step_folded_record(record, delta)
            exact_s, (a, b), flags = unfold_scale_record(stepped)
            assert exact_s == s + delta
            assert (a, b) == reference[(s + delta) % PISANO_PERIOD]
            assert flags == 0


def test_step_epoch_overflow_is_fail_closed():
    record = fold_scale_index(MAX_FOLDABLE_SCALE)
    with pytest.raises(OverflowError):
        step_folded_record(record, 1)


def test_verify_step_parity_fail_closed():
    scales = REFERENCE_VECTORS
    delta = 10**12
    inputs = [fold_scale_index(s) for s in scales]
    outputs = [step_folded_record(record, delta) for record in inputs]
    verify_step_parity(inputs, outputs, delta)
    corrupted = list(outputs)
    corrupted[2] = outputs[2][:10] + bytes([outputs[2][10] ^ 1]) + outputs[2][11:]
    with pytest.raises(ParityVerificationError):
        verify_step_parity(inputs, corrupted, delta)
    with pytest.raises(ParityVerificationError):
        verify_step_parity(inputs, outputs[:-1], delta)


def test_f257_phi_mul_matches_lattice_and_lut():
    # phi^r * phi^t == phi^(r+t mod 516): the device bilinear form reproduces
    # the same bytes the LUT publishes.
    for r, t in ((400, 64), (257, 258), (515, 1), (0, 0), (300, 300)):
        product = f257_phi_mul(LUT_TUPLE[r], LUT_TUPLE[t])
        assert product == LUT_TUPLE[(r + t) % PISANO_PERIOD]
    assert f257_phi_mul((256, 0), (256, 0)) == LUT_TUPLE[0]  # (-1)*(-1) == 1


def test_kernel_source_is_integer_only_and_digest_pinned():
    source = kernel_source().decode("utf-8")
    assert hashlib.sha256(source.encode("utf-8")).hexdigest() == FOLDED_KERNEL_SHA256
    assert not re.search(r"\b(float|double|half)\b", source)
    assert "ushort" in source and "ulong" in source
    assert "aligned(16)" in source
    assert "PISANO_PERIOD 516U" in source


def test_adapter_raises_without_pyopencl(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyopencl", None)
    with pytest.raises(HardwareUnavailableError):
        ChronusOpenCLFoldedAdapter()


def test_opencl_device_dispatch_roundtrip():
    cl = pytest.importorskip("pyopencl")
    try:
        platforms = cl.get_platforms()
    except cl.LogicError as exc:
        if exc.code == -1001:  # PLATFORM_NOT_FOUND_KHR: driver is not installed.
            pytest.skip("No OpenCL platform is installed")
        raise
    if not any(
        device.type & cl.device_type.GPU
        for platform in platforms
        for device in platform.get_devices()
    ):
        pytest.skip("No OpenCL GPU device is available")
    adapter = ChronusOpenCLFoldedAdapter()
    scales = REFERENCE_VECTORS + [0, 515, 516]
    packed = pack_folded_batch(scales)
    delta = 10**20 + 12345
    stepped = adapter.step_batch(packed, delta)
    records_in = [bytes(packed[i:i + 16]) for i in range(0, len(packed), 16)]
    records_out = [bytes(stepped[i:i + 16]) for i in range(0, len(stepped), 16)]
    verify_step_parity(records_in, records_out, delta)
    for s, out in zip(scales, records_out):
        exact_s, (a, b), _ = unfold_scale_record(out)
        assert exact_s == s + delta
        assert (a, b) == LUT_TUPLE[(s + delta) % PISANO_PERIOD]


def test_batch_preflight_rejects_corruption_and_overflow_before_launch():
    from unittest.mock import Mock
    adapter = object.__new__(ChronusOpenCLFoldedAdapter)
    adapter._dispatch_once = Mock(side_effect=AssertionError('must not launch'))
    corrupt = bytearray(fold_scale_index(10**20));corrupt[10] ^= 255
    with pytest.raises(ValueError, match='corruption'):
        adapter.step_batch(corrupt, 1)
    with pytest.raises(OverflowError):
        adapter.step_batch(fold_scale_index(MAX_FOLDABLE_SCALE), 1)
    with pytest.raises(OverflowError):
        adapter.step_batch(fold_scale_index(0), 10**100)
    assert adapter.step_batch(b'', 10**100)==bytearray()
    adapter._dispatch_once.assert_not_called()


def test_large_jump_uses_one_launch_and_retains_exact_epoch():
    from unittest.mock import Mock
    adapter = object.__new__(ChronusOpenCLFoldedAdapter)
    source = fold_scale_index(10**12)
    expected = step_folded_record(source, 10**20)
    adapter._dispatch_once = Mock(return_value=bytearray(expected))
    assert adapter.step_batch(source, 10**20)==expected
    adapter._dispatch_once.assert_called_once_with(source, 10**20)


def test_batch_rejects_loss_of_high_quotient_limbs():
    with pytest.raises(OverflowError):pack_folded_batch([516*(1<<64)])
    assert unfold_scale_record(pack_folded_batch([MAX_FOLDABLE_SCALE]))[0]==MAX_FOLDABLE_SCALE
