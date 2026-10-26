"""Bounded JSON bridge to TURING's canonical exact execution boundary.

Chronus owns delivery, tenancy, routing and custody. TURING owns quantum
semantics, representation admission and computation certificates. This bridge
never selects a physical provider or converts an amplitude to floating point.
"""

from __future__ import annotations

from typing import Any, Mapping

MAX_QUBITS = 1024
MAX_OPERATIONS = 4096
MAX_AMPLITUDES = 4096
MAX_SHOTS = 4096
ARITIES = {
    **dict.fromkeys(("i", "id", "h", "x", "y", "z", "s", "sdg", "t", "tdg"), 1),
    **dict.fromkeys(("cx", "cnot", "cz", "swap"), 2),
    **dict.fromkeys(("ccx", "toffoli"), 3),
}
BACKENDS = ("exact_algebraic", "stabilizer", "mps_exact", "exact_cyclotomic")


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def prepare_request(value: Mapping[str, Any]) -> tuple[Any, Any, str | None, int, dict]:
    """Validate before allocating any quantum state; lower via TURING identities."""
    from turing_universal_quantum_computer.backends import Operation, Program
    from turing_universal_quantum_computer.software_stack import decompose_to_basis
    from turing_universal_quantum_computer.backends.cyclotomic import phase_turns

    allowed = {"program", "backend", "max_amplitudes", "shots", "seed"}
    if set(value) - allowed or "program" not in value:
        raise ValueError("quantum_program requires program and only declared options")
    raw = value["program"]
    if not isinstance(raw, dict) or set(raw) != {"n_qubits", "operations"}:
        raise ValueError("program requires n_qubits and operations")
    width = _integer(raw["n_qubits"], "n_qubits", 1, MAX_QUBITS)
    operations = raw["operations"]
    if not isinstance(operations, list) or len(operations) > MAX_OPERATIONS:
        raise ValueError(f"operations must be a list of at most {MAX_OPERATIONS} gates")
    parsed = []
    for op in operations:
        if not isinstance(op, dict) or set(op) != {"gate", "qubits"}:
            raise ValueError("each operation requires gate and qubits")
        gate, qubits = op["gate"], op["qubits"]
        if not isinstance(gate, str) or (
            gate not in ARITIES and gate != "magic_t" and phase_turns(gate) is None
        ):
            raise ValueError(f"unsupported exact gate {gate!r}")
        if not isinstance(qubits, list) or len(qubits) != ARITIES.get(gate, 1):
            raise ValueError(f"wrong arity for {gate}")
        for q in qubits:
            _integer(q, "qubit", 0, width - 1)
        if len(set(qubits)) != len(qubits):
            raise ValueError("gate operands must be distinct")
        parsed.append(
            Operation({"id": "i", "cnot": "cx", "toffoli": "ccx"}.get(gate, gate), tuple(qubits))
        )
    original = Program(width, tuple(parsed))
    # Preserve the Clifford lane: do not expand S into non-Clifford T gates.
    extended = any(o.gate == "magic_t" or phase_turns(o.gate) for o in original.operations)
    executable = (
        original
        if extended
        else decompose_to_basis(
            original,
            basis_gates=("i", "h", "x", "y", "z", "s", "sdg", "t", "tdg", "cx", "cz", "swap"),
        )
    )
    if len(executable.operations) > MAX_OPERATIONS:
        raise ValueError("lowered circuit exceeds operation budget")
    backend = value.get("backend", "exact_cyclotomic" if extended else None)
    if backend is not None and backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}")
    budget = _integer(
        value.get("max_amplitudes", MAX_AMPLITUDES), "max_amplitudes", 1, MAX_AMPLITUDES
    )
    options = {"exact_payload": True}
    if "shots" in value:
        options["shots"] = _integer(value["shots"], "shots", 1, MAX_SHOTS)
        options["seed"] = _integer(value.get("seed", 0), "seed", 0, (1 << 64) - 1)
    elif "seed" in value:
        raise ValueError("seed requires shots")
    return original, executable, backend, budget, options


def _contains_float_token(value: Any) -> bool:
    if isinstance(value, dict):
        return "$float_hex" in value or any(_contains_float_token(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float_token(v) for v in value)
    return False


def execute_quantum_program(value: Mapping[str, Any]) -> dict[str, Any]:
    """Execute certified exact algebra, tableau or bounded-rank MPS."""
    from turing_universal_quantum_computer.backends import TruthClass, execute_certified
    from turing_universal_quantum_computer.certificates import canonicalize_certificate_value
    from turing_universal_quantum_computer.quantum_library import audit_exactness

    original, executable, backend, budget, options = prepare_request(value)
    run = execute_certified(executable, prefer=backend, max_amplitudes=budget, **options)
    result = canonicalize_certificate_value(run.result.as_dict())
    report = audit_exactness(result)
    if (
        not report.exact
        or _contains_float_token(result)
        or run.result.truth_class != TruthClass.EXACT
        or run.result.measured_qpu
    ):
        raise ValueError("quantum_program violated its exact software execution contract")
    return {
        "source_program_digest": original.digest(),
        "executable_program": executable.to_dict(),
        "execution": result,
        "witness_digest": run.witness.digest(),
        "arithmetic": "exact",
        "semantic_authority": "turing_universal_quantum_computer",
    }


def verify_quantum_program(value: Mapping[str, Any], output: Mapping[str, Any]) -> list[str]:
    """Replay the canonical engine outside the adapter; compare all result bytes.

    A sealed digest alone is insufficient: an incorrect producer can seal an
    incorrect answer. Replay is bounded by the same admission as execution.
    """
    expected = execute_quantum_program(value)
    return [] if output == expected else ["exact TURING execution/certificate replay mismatch"]
