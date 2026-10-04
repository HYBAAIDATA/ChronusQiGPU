"""Folded-resident operator catalogue: lifted correctness + measured promotion."""

import numpy as np
import pytest

from aethel.phi_fold import phi_fold, phi_unfold
from tensor.folded import (
    FOLDED_OPERATOR_CATALOGUE,
    FoldedOpError,
    catalogue_report,
    evaluate_operator,
    folded_execute,
)


def _fold(arr, depth):
    # Small operands cannot reach every depth — fold as deep as size permits.
    from aethel.phi_fold import PhiFoldError

    for candidate in range(depth, -1, -1):
        try:
            return phi_fold(np.atleast_1d(np.asarray(arr)), depth=candidate)
        except PhiFoldError:
            continue
    raise AssertionError("operand cannot fold at any depth")


def _states(*arrays, depth=3):
    return tuple(_fold(a, depth) for a in arrays)


def test_coordinate_ops_lift_bit_identical_zero_decode():
    a = np.linspace(-1, 1, 128).reshape(8, 16)
    b = np.linspace(0.5, 1.5, 128).reshape(8, 16)
    for name, ref in (("add", a + b), ("hadamard", a * b)):
        out, receipt = folded_execute(name, _states(a, b))
        assert receipt.path == "lifted"
        assert receipt.decoded_bytes == 0
        assert np.array_equal(phi_unfold(out), ref)  # bit-identical
        assert receipt.output_hash


def test_fma_ternary_lift():
    a = np.linspace(-1, 1, 64)
    x = np.linspace(0.25, 2.0, 64)
    b = np.full(64, 0.125)
    out, receipt = folded_execute("fma", _states(a, x, b))
    assert receipt.path == "lifted"
    np.testing.assert_array_equal(phi_unfold(out), a * x + b)


def test_scale_lift_and_domain_guard():
    a = np.arange(64, dtype=np.float64)
    out, receipt = folded_execute("scale", _states(a, np.array([2.5])))
    assert receipt.path == "lifted"
    np.testing.assert_array_equal(phi_unfold(out), a * 2.5)
    # Non-scalar second operand is a domain violation, not silent broadcast.
    with pytest.raises(FoldedOpError, match="scalar"):
        folded_execute("scale", _states(a, np.ones(4)))


def test_lifted_ops_reject_mismatched_domains():
    a = np.arange(64, dtype=np.float64)
    bad_dtype = np.arange(64, dtype=np.float32)
    bad_shape = np.arange(32, dtype=np.float64)
    bad_depth = _states(a, depth=2)[0]
    with pytest.raises(FoldedOpError, match="dtype"):
        folded_execute("add", _states(a) + _states(bad_dtype))
    with pytest.raises(FoldedOpError, match="shape"):
        folded_execute("add", _states(a) + _states(bad_shape))
    with pytest.raises(FoldedOpError, match="depth"):
        folded_execute("add", _states(a) + (bad_depth,))


def test_lifted_ops_work_on_complex():
    a = (np.arange(32) + 1j * np.arange(32)[::-1]).astype(np.complex128)
    b = (np.arange(32) * 0.5 - 2j).astype(np.complex128)
    out, receipt = folded_execute("add", _states(a, b))
    assert np.array_equal(phi_unfold(out), a + b)
    assert receipt.decoded_bytes == 0


@pytest.mark.parametrize("name", ["transpose", "matmul", "kron", "reduce_sum"])
def test_materializing_ops_are_declared_and_correct(name):
    a = np.linspace(-1, 1, 36).reshape(6, 6)
    b = np.linspace(0.5, 1.5, 36).reshape(6, 6)
    ops = {
        "transpose": ((a,), np.transpose(a)),
        "matmul": ((a, b), a @ b),
        "kron": ((a, b), np.kron(a, b)),
        "reduce_sum": ((a,), np.asarray(np.sum(a))),
    }
    arrays, ref = ops[name]
    out, receipt = folded_execute(name, _states(*arrays))
    assert receipt.path == "materialized"  # honestly declared, not faked
    assert receipt.decoded_bytes > 0
    np.testing.assert_allclose(phi_unfold(out), np.asarray(ref).reshape(phi_unfold(out).shape))


def test_unknown_op_and_arity_fail_closed():
    a = np.arange(16)
    with pytest.raises(FoldedOpError, match="no folded operator"):
        folded_execute("conv2d", _states(a))
    with pytest.raises(FoldedOpError, match="expects 2"):
        folded_execute("add", _states(a))


def test_promotion_evidence_is_measured_not_assumed():
    a = np.linspace(-1, 1, 256).reshape(16, 16)
    b = np.linspace(0.5, 1.5, 256).reshape(16, 16)
    promoted = evaluate_operator("add", (a, b))
    assert promoted.correct and promoted.promoted
    assert promoted.decoded_bytes == 0
    assert "verified vs reference" in promoted.rationale
    # Declared-materializing ops are not promoted — the record says why.
    for name, operands in (
        ("matmul", (a, b)),
        ("kron", (a[:4], b[:8, :8])),
        ("transpose", (a,)),
        ("reduce_sum", (a,)),
    ):
        ev = evaluate_operator(name, operands)
        assert ev.correct
        assert not ev.promoted
        assert ev.rationale  # the rejection records its measured evidence


def test_catalogue_report_covers_every_entry():
    report = catalogue_report(repeats=2)
    assert set(report) == set(FOLDED_OPERATOR_CATALOGUE)
    assert report["add"].promoted
    assert report["scale"].promoted
    assert report["fma"].promoted
    assert report["hadamard"].promoted
    assert all(e.correct for e in report.values())
