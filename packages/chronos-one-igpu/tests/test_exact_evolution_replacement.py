"""Positive migration and fail-closed attacks on exact evolution and ABI replay."""

import copy
import hashlib
import pytest
import sympy as s
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.igpu.exact_quantum import (
    ExactQuantumState,
    exact_hamiltonian_evolution,
    encode_expression,
    decode_expression,
)
from chronos_one_igpu.igpu.virtual_abi import VirtualRuntime, Workload, canonical


@pytest.mark.parametrize(
    "matrix,expected",
    [
        ([[0, 1], [1, 0]], (0, -s.I)),
        ([[0, -s.I], [s.I, 0]], (0, 1)),
        ([[1, 0], [0, -1]], (-s.I, 0)),
    ],
)
def test_exact_pauli(matrix, expected):
    result = exact_hamiltonian_evolution([1, 0], matrix, s.pi / 2)
    assert result.amplitudes == expected
    assert result.probabilities.sum() == 1
    assert not any(x.has(s.Float) for x in result.amplitudes)
    assert result.evidence["fallback_used"] is False
    assert (
        result.evidence["requested_algorithm"] == result.evidence["executed_algorithm"]
    )


def test_old_facade_reaches_exact_replacement():
    result = OneIGPU().evolve([1.0, 0.0], [[0.0, 1.0], [1.0, 0.0]], s.pi / 2)
    assert result.amplitudes == (0, -s.I)
    assert result.evidence["implementation_module"].endswith(".exact_quantum")
    assert result.amplitudes.shape == (2,)


@pytest.mark.parametrize(
    "a,h,t",
    [
        ([1, 0], [[0, 1], [0, 0]], 1),
        ([1, 0], [[0]], 1),
        ([1, 0], [[0, 1], [1, 0]], s.I),
        ([s.Float(1), 0], [[0, 1], [1, 0]], 1),
    ],
)
def test_invalid_exact_request_has_no_numerical_repair(a, h, t):
    with pytest.raises(ValueError):
        exact_hamiltonian_evolution(a, h, t)


def test_no_output_renormalisation():
    with pytest.raises(ValueError):
        ExactQuantumState((1, 1))


def test_unsupported_materialisation_is_unavailable():
    n = 9
    h = s.zeros(n)
    for i in range(n - 1):
        h[i, i + 1] = h[i + 1, i] = 1
    with pytest.raises(BackendAbsent):
        exact_hamiltonian_evolution([1] + [0] * 8, h.tolist(), 1)


@pytest.mark.parametrize(
    "value",
    [s.Rational(7, 11), s.sqrt(5), s.I, s.pi, s.exp(s.I * s.pi / 7), s.cos(s.sqrt(5))],
)
def test_exact_expression_transport(value):
    assert s.simplify(decode_expression(encode_expression(value)) - value) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"rational": [2, 4]},
        {"rational": [1, 0]},
        {"rational": [1 << 5000, 1]},
        {"operator": "pow", "args": [{"rational": [2, 1]}, {"rational": [1000000, 1]}]},
        {"operator": "eval", "args": [{"atom": "pi"}]},
        {"atom": "__import__"},
    ],
)
def test_transport_attacks(payload):
    with pytest.raises(ValueError):
        decode_expression(payload)


def test_abi_exact_receipt_and_independent_replay():
    runtime = VirtualRuntime(OneIGPU())
    workload = Workload(
        "exact-evolution",
        "tenant",
        "evolve",
        {"amplitudes": [1, 0], "hamiltonian": [[0, 1], [1, 0]], "time": 0},
        quota=2,
    )
    receipt = runtime.execute(workload)
    assert receipt["backend"] == "cpu_exact_symbolic"
    assert runtime.verify_receipt(receipt, workload)
    tampered = copy.deepcopy(receipt)
    tampered["output"]["execution_receipt"]["implementation_digest"] = "0" * 64
    tampered["result_digest"] = hashlib.sha256(
        canonical(tampered["output"])
    ).hexdigest()
    body = {k: v for k, v in tampered.items() if k != "receipt_digest"}
    tampered["receipt_digest"] = hashlib.sha256(canonical(body)).hexdigest()
    with pytest.raises(ValueError, match="replay"):
        runtime.verify_receipt(tampered, workload)


def test_exact_tree_input_reaches_exact_evolution():
    runtime = VirtualRuntime(OneIGPU())
    workload = Workload(
        "exact-pi",
        "tenant",
        "evolve",
        {
            "amplitudes": [1, 0],
            "hamiltonian": [[0, 1], [1, 0]],
            "time": encode_expression(s.pi / 2),
        },
        quota=2,
    )
    receipt = runtime.execute(workload)
    assert [decode_expression(x) for x in receipt["output"]["imag"]] == [0, -1]
    assert runtime.verify_receipt(receipt, workload)


def test_abi_rejects_relabelled_substrate():
    runtime = VirtualRuntime(OneIGPU())
    workload = Workload(
        "substrate",
        "tenant",
        "evolve",
        {"amplitudes": [1], "hamiltonian": [[0]]},
        quota=1,
    )
    receipt = runtime.execute(workload)
    receipt["backend"] = "physical_qpu"
    receipt["receipt_digest"] = hashlib.sha256(
        canonical({k: v for k, v in receipt.items() if k != "receipt_digest"})
    ).hexdigest()
    with pytest.raises(ValueError, match="substrate"):
        runtime.verify_receipt(receipt, workload)
