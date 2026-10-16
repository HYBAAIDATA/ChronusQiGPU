"""Exact gate algebra for the existing M5 GHZ/cluster formulation.

One logical qubit per pad, explicitly bounded to 10 pads. This executes finite
quantum mathematics on the host, not the model's entire 64-bit-per-subunit
register, a QPU, physical entanglement or a mining nonce shortcut.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import time

import sympy as sp
from ..adapters.base import BackendAbsent
from ..m5_ultra import PadFabric
from .exact_quantum import encode_expression, decode_expression
from .resident import canonical

ALGORITHMS = ("exact_m5_ghz", "exact_m5_cluster")
MAX_PADS = 10


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def topology(model):
    if not isinstance(model, PadFabric):
        raise TypeError("canonical PadFabric required")
    n = model.n_pads
    if not 1 <= n <= MAX_PADS:
        raise BackendAbsent("exact M5 gate-algebra pad quota exceeded")
    if any(type(p.index) is not int for p in model.pads) or tuple(p.index for p in model.pads) != tuple(range(n)):
        raise ValueError("canonical contiguous pad identity required")
    edges = tuple((link.source, link.target) for link in model.links)
    if any(type(i) is not int or type(j) is not int or not (0 <= i < n and 0 <= j < n and i != j) for i, j in edges):
        raise ValueError("canonical undirected M5 edge identity required")
    edges = tuple((min(i, j), max(i, j)) for i, j in edges)
    if len(set(edges)) != len(edges):
        raise ValueError("duplicate M5 edges cannot cancel silently")
    return n, tuple(sorted(edges))


def _hadamard(state, bit):
    # Every pair is transformed by H=(1/sqrt(2))*[[1,1],[1,-1]].
    result = list(state)
    for i in range(len(state)):
        if not i & (1 << bit):
            j = i | (1 << bit)
            result[i] = sp.simplify((state[i] + state[j]) / sp.sqrt(2))
            result[j] = sp.simplify((state[i] - state[j]) / sp.sqrt(2))
    return result


def _cnot(state, control, target):
    result = [sp.Integer(0)] * len(state)
    for i, amplitude in enumerate(state):
        j = i ^ (1 << target) if i & (1 << control) else i
        result[j] = amplitude
    return result


def _cz(state, left, right):
    return [-a if i & (1 << left) and i & (1 << right) else a
            for i, a in enumerate(state)]


def _request(model, algorithm):
    n, edges = topology(model)
    if algorithm not in ALGORITHMS:
        raise ValueError("explicit exact M5 algorithm required")
    return {"algorithm": algorithm, "model_digest": digest(model.as_dict()),
            "pad_count": n, "edges": [list(e) for e in edges],
            "encoding": "one_logical_qubit_per_pad_lsb_pad0/1",
            "full_model_register_executed": False}


def execute_quantum(model, algorithm):
    request = _request(model, algorithm)
    started = time.perf_counter()
    n = request["pad_count"]
    state = [sp.Integer(0)] * (1 << n)
    state[0] = sp.Integer(1)
    gates = []
    if algorithm == "exact_m5_ghz":
        state = _hadamard(state, 0)
        gates.append(["H", 0])
        for bit in range(1, n):
            state = _cnot(state, 0, bit)
            gates.append(["CX", 0, bit])
    else:
        for bit in range(n):
            state = _hadamard(state, bit)
            gates.append(["H", bit])
        for left, right in request["edges"]:
            state = _cz(state, left, right)
            gates.append(["CZ", left, right])
    amplitudes = [encode_expression(a) for a in state]
    probabilities = [encode_expression(sp.simplify(sp.conjugate(a) * a)) for a in state]
    receipt = {
        "schema": "chronos.m5_exact_gate_algebra/1", "request": request,
        "requested_algorithm": algorithm, "planned_algorithm": algorithm,
        "executed_algorithm": algorithm,
        "implementation_module": __name__,
        "implementation_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "execution_mode": "exact_gate_algebra",
        "substrate": {"kind": "cpu", "arithmetic": "exact_sympy"},
        "plan_digest": digest(request),
        "geometry_digest": digest({"pad_count": n, "edges": request["edges"]}),
        "iterations_work_performed": {"gate_applications": len(gates), "state_dimension": len(state)},
        "gates": gates, "amplitudes": amplitudes, "probabilities": probabilities,
        "norm_squared": "1", "elapsed_seconds": time.perf_counter() - started,
        "sha256d_evaluations": 0, "sha256d_verification": "NOT_APPLICABLE",
        "physical_quantum_execution": False,
        "fallback_used": False, "fallback_reason": None,
    }
    receipt["receipt_digest"] = digest(receipt)
    verify_quantum(receipt, model, algorithm)
    return receipt


def verify_quantum(receipt, model, algorithm):
    """Independent closed-form state verifier, not re-running the gate loop."""
    request = _request(model, algorithm)
    if not isinstance(receipt, dict) or len(canonical(receipt)) > 4 * 1024 * 1024:
        raise ValueError("bounded M5 quantum receipt required")
    body = dict(receipt)
    claimed = body.pop("receipt_digest", None)
    if digest(body) != claimed or receipt["request"] != request:
        raise ValueError("M5 quantum custody/request mismatch")
    n = request["pad_count"]
    expected_gates = ([["H", 0]] + [["CX", 0, bit] for bit in range(1, n)]
        if algorithm == "exact_m5_ghz" else
        [["H", bit] for bit in range(n)] + [["CZ", i, j] for i, j in request["edges"]])
    expected = {
        "schema": "chronos.m5_exact_gate_algebra/1", "request": request,
        "requested_algorithm": algorithm, "planned_algorithm": algorithm,
        "executed_algorithm": algorithm,
        "implementation_module": __name__,
        "implementation_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "execution_mode": "exact_gate_algebra",
        "substrate": {"kind": "cpu", "arithmetic": "exact_sympy"},
        "plan_digest": digest(request),
        "geometry_digest": digest({"pad_count": n, "edges": request["edges"]}),
        "iterations_work_performed": {"gate_applications": len(expected_gates), "state_dimension": 1 << n},
        "gates": expected_gates, "norm_squared": "1", "sha256d_evaluations": 0,
        "sha256d_verification": "NOT_APPLICABLE", "physical_quantum_execution": False,
        "fallback_used": False, "fallback_reason": None,
    }
    if set(receipt) != set(expected) | {"amplitudes", "probabilities", "elapsed_seconds", "receipt_digest"}:
        raise ValueError("M5 quantum receipt fields mismatch")
    if any(receipt[k] != value for k, value in expected.items()):
        raise ValueError("M5 quantum algorithm/implementation identity mismatch")
    if type(receipt["elapsed_seconds"]) not in (int, float) or receipt["elapsed_seconds"] < 0:
        raise ValueError("invalid executed duration")
    if len(receipt["amplitudes"]) != 1 << n or len(receipt["probabilities"]) != 1 << n:
        raise ValueError("M5 quantum dimension mismatch")
    norm = sp.Integer(0)
    for i, (amplitude, probability) in enumerate(zip(receipt["amplitudes"], receipt["probabilities"])):
        a = decode_expression(amplitude)
        p = decode_expression(probability)
        if algorithm == "exact_m5_ghz":
            reference = 1 / sp.sqrt(2) if i in (0, (1 << n) - 1) else sp.Integer(0)
            # A single-qubit GHZ is |+>, matching the same expression.
        else:
            parity = sum(bool(i & (1 << left) and i & (1 << right)) for left, right in request["edges"]) % 2
            reference = (-1 if parity else 1) / sp.sqrt(1 << n)
        if sp.simplify(a - reference) != 0 or sp.simplify(p - sp.conjugate(a) * a) != 0:
            raise ValueError("M5 quantum amplitude/Born verification failed")
        norm += p
    if sp.simplify(norm - 1) != 0:
        raise ValueError("M5 quantum normalisation failed")
    return True
