"""Independent re-verification on the production execute route.

The audit's first broken transition was ``execution → verification``: a
receipt certified the path taken but nothing recomputed the answer. These
tests pin the closure — every TensorRuntime execution re-derives its
output on an alternate path, binds the verdict to the receipt, and
refuses publication on divergence.
"""

import dataclasses

import numpy as np
import pytest

from aethel.phi_fold import phi_fold
from tensor import TensorRuntime
from tensor.errors import TensorVerificationError
from tensor.folded import FOLDED_OPERATOR_CATALOGUE
from tensor.verification import (
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_UNVERIFIED,
    verify_backend_output,
    verify_folded_output,
)


# ---- verified verdicts on the real route ----------------------------------


def test_folded_lifted_op_is_independently_verified():
    rt = TensorRuntime()
    a = np.linspace(-1, 1, 64)
    b = np.linspace(0.5, 1.5, 64)
    rt.store_tensor("a", a)
    rt.store_tensor("b", b)
    record = rt.execute("add", ["a", "b"], out="c")
    assert record["path"] == "lifted"
    assert record["verification"]["recomputed"] is True
    assert record["verification"]["method"] == "unfolded_numpy_reference"
    assert record["verification"]["verdict"] == VERDICT_PASS
    assert record["verification"]["max_residual"] == 0.0
    assert (
        record["verification"]["output_digest"]
        == record["verification"]["reference_digest"]
    )
    # The receipt promotes correctness only on a passing re-check.
    assert record["receipt"]["correctness"] == "verified"
    np.testing.assert_array_equal(rt.read_tensor("c"), a + b)


def test_committed_kron_is_bit_identical_verified():
    rt = TensorRuntime()
    a = np.arange(16, dtype=np.float64).reshape(4, 4)
    b = np.arange(4, dtype=np.float64).reshape(2, 2) + 0.5
    rt.store_tensor("a", a)
    rt.store_tensor("b", b)
    record = rt.execute("kron", ["a", "b"])
    assert record["path"] == "committed"
    verdict = record["verification"]
    assert verdict["verdict"] == VERDICT_PASS
    assert verdict["tolerance"] is None  # kron is declared bit-identical
    assert verdict["max_residual"] == 0.0
    np.testing.assert_array_equal(
        rt.read_tensor(record["output"]), np.kron(a, b)
    )


def test_committed_matmul_verified_within_declared_reassociation():
    rt = TensorRuntime()
    rng = np.random.default_rng(7)
    a = rng.normal(size=(8, 8))
    b = rng.normal(size=(8, 8))
    rt.store_tensor("a", a)
    rt.store_tensor("b", b)
    record = rt.execute("matmul", ["a", "b"])
    assert record["path"] == "committed"
    verdict = record["verification"]
    # matmul declares float reassociation — verified, not bit-identical.
    assert verdict["verdict"] == VERDICT_PASS
    assert verdict["tolerance"] == pytest.approx(1e-12)
    assert verdict["max_residual"] <= 1e-12
    np.testing.assert_allclose(
        rt.read_tensor(record["output"]), a @ b, rtol=1e-12, atol=1e-12
    )


def test_backend_execute_recomputed_via_folded_resident_path():
    rt = TensorRuntime()
    a = np.arange(12, dtype=np.float64).reshape(3, 4)
    b = np.arange(8, dtype=np.float64).reshape(4, 2)
    record = rt.execute("matmul", [a, b])
    assert record["path"] == "backend"
    verdict = record["verification"]
    assert verdict["recomputed"] is True
    assert verdict["method"] == "folded_resident_recompute"
    assert verdict["verdict"] == VERDICT_PASS
    assert record["receipt"]["correctness"] == "verified"


@pytest.mark.parametrize("op", ["add", "hadamard", "scale", "fma"])
def test_folded_elementwise_ops_verify(op):
    rt = TensorRuntime()
    rng = np.random.default_rng(11)
    x = rng.normal(size=64)
    rt.store_tensor("x", x)
    operands = ["x"]
    for i in range(FOLDED_OPERATOR_CATALOGUE[op].arity - 1):
        name = f"o{i}"
        data = rng.normal(size=64)
        if op == "scale" and i == 0:
            data = np.array([2.0])  # scale's second operand is a scalar
        rt.store_tensor(name, data)
        operands.append(name)
    record = rt.execute(op, operands)
    assert record["verification"]["verdict"] == VERDICT_PASS


# ---- divergence refuses publication ---------------------------------------


def _corrupted_committed(op_name):
    """A committed implementation that returns subtly wrong output —
    the wrong-but-well-formed computation the audit described."""
    op = FOLDED_OPERATOR_CATALOGUE[op_name]
    honest = op.committed

    def bad(states):
        result = honest(states)
        if result is None:
            return None
        out, info = result
        poisoned = out.retained.copy()
        poisoned.flat[0] += 1.0  # one wrong element, well-formed shape
        out = dataclasses.replace(
            out,
            retained=poisoned,
            content_hash="",  # recomputed below
        )
        object.__setattr__(out, "content_hash", out.compute_content_hash())
        return out, info

    return dataclasses.replace(op, committed=bad)


def test_divergent_committed_output_refuses_publication(monkeypatch):
    rt = TensorRuntime()
    a = np.arange(16, dtype=np.float64).reshape(4, 4)
    b = np.ones((4, 4), dtype=np.float64)
    rt.store_tensor("a", a)
    rt.store_tensor("b", b)
    monkeypatch.setitem(
        FOLDED_OPERATOR_CATALOGUE, "kron", _corrupted_committed("kron")
    )
    with pytest.raises(TensorVerificationError, match="diverged"):
        rt.execute("kron", ["a", "b"], request_id="req-corrupt")
    # Nothing was published: no custody write, no result record, no receipt.
    assert rt.result("req-corrupt") is None
    assert "req-corrupt:out" not in rt.tensor_names()


def test_divergent_lifted_output_refuses_publication(monkeypatch):
    op = FOLDED_OPERATOR_CATALOGUE["add"]

    def bad(states):
        out = op.lifted(states)
        poisoned = out.retained.copy()
        poisoned.flat[0] += 1e-9
        out = dataclasses.replace(out, retained=poisoned)
        object.__setattr__(out, "content_hash", out.compute_content_hash())
        return out

    monkeypatch.setitem(
        FOLDED_OPERATOR_CATALOGUE, "add", dataclasses.replace(op, lifted=bad)
    )
    rt = TensorRuntime()
    rt.store_tensor("a", np.ones(16))
    rt.store_tensor("b", np.ones(16))
    with pytest.raises(TensorVerificationError):
        rt.execute("add", ["a", "b"], request_id="req-bad-lift")
    assert rt.result("req-bad-lift") is None


def test_backend_divergence_refuses_result(monkeypatch):
    # A backend that returns a well-formed but wrong array must fail the
    # folded-resident re-check and never publish.
    from tensor.backends.numpy_backend import NumpyBackend

    class CorruptBackend(NumpyBackend):
        @property
        def name(self):
            return "numpy-cpu"

        def execute(self, operation, inputs, *, deterministic):
            result = super().execute(operation, inputs, deterministic=deterministic)
            result = np.asarray(result).copy()
            result.flat[0] += 1.0
            return result

    from tensor.router import default_registry

    registry = default_registry()
    # The registry stores zero-arg factories; swap numpy-cpu's for the
    # corrupt implementation.
    monkeypatch.setitem(
        registry._factories, "numpy-cpu", CorruptBackend
    )
    rt = TensorRuntime(registry=registry)
    with pytest.raises(TensorVerificationError, match="diverged"):
        rt.execute(
            "matmul",
            [np.eye(4), np.ones((4, 4))],
            request_id="req-bad-backend",
        )
    assert rt.result("req-bad-backend") is None


# ---- custody-layer integrity ------------------------------------------------


def test_corrupted_folded_block_fails_integrity_and_verdict():
    """A tampered resident block is caught two ways: its stored
    content_hash no longer matches its bytes, and a verdict computed
    over a corrupted output diverges from the reference."""
    a = np.arange(16, dtype=np.float64)
    b = np.ones(16, dtype=np.float64)
    state_a, state_b = phi_fold(a, 2), phi_fold(b, 2)

    # Corrupt the output's retained segment post-commit.
    from tensor.folded import folded_execute

    good_out, _receipt = folded_execute("add", (state_a, state_b))
    tampered = dataclasses.replace(
        good_out, retained=good_out.retained.copy()
    )
    tampered.retained.flat[0] += 5.0
    assert tampered.verify_content_hash() is False  # integrity layer fires

    verdict = verify_folded_output("add", (state_a, state_b), tampered)
    assert verdict.verdict == VERDICT_FAIL
    assert verdict.recomputed is True


def test_uncheckable_op_reports_unverified_not_fake_pass():
    state = phi_fold(np.ones(8), 2)
    out = phi_fold(np.ones(8), 2)
    verdict = verify_folded_output("no_such_op", (state,), out)
    assert verdict.recomputed is False
    assert verdict.verdict == VERDICT_UNVERIFIED
    verdict2 = verify_backend_output("no_such_op", [np.ones(4)], np.ones(4))
    assert verdict2.recomputed is False
    assert verdict2.verdict == VERDICT_UNVERIFIED


def test_verdict_is_bound_into_receipt_schema():
    rt = TensorRuntime()
    rt.store_tensor("a", np.ones(8))
    rt.store_tensor("b", np.ones(8))
    record = rt.execute("add", ["a", "b"])
    receipt_verification = record["receipt"]["verification"]
    assert receipt_verification["verdict"] == VERDICT_PASS
    assert receipt_verification["method"] == "unfolded_numpy_reference"
    assert receipt_verification["recomputed"] is True
    # Same verdict at record and receipt level.
    assert receipt_verification == record["verification"]
