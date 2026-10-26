"""Exact rational-turn gates and certified magic-state injection.

Gate spellings phase:p/q and rz:p/q use rational turns. Rz includes its
exp(-i theta/2) global phase. magic_t evaluates both measurement branches
of the |A> injection instrument and checks corrected branch equality.
"""

from __future__ import annotations

from fractions import Fraction
from math import lcm
import re

from kellogg.algebraic_field import Cyclotomic, cyclotomic_polynomial
from .base import Admission, Capability, ExecutionClass, ExecutionResult, TruthClass

_PHASE = re.compile(r"(phase|rz):(-?\d{1,6})/([1-9]\d{0,5})\Z")
_ARITY = dict.fromkeys(("i", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "magic_t"), 1)
_ARITY.update(cx=2, cnot=2, cz=2, swap=2, ccx=3)


def phase_turns(gate):
    match = _PHASE.fullmatch(gate)
    if match is None:
        return None
    return match[1], Fraction(int(match[2]), int(match[3]))


class CyclotomicBackend:
    name = "exact_cyclotomic"

    def __init__(self, max_amplitudes=4096):
        if type(max_amplitudes) is not int or not 1 <= max_amplitudes <= 65536:
            raise ValueError("cyclotomic amplitude budget must be in 1..65536")
        self.max_amplitudes = max_amplitudes

    def capability(self):
        return Capability(
            self.name,
            ExecutionClass.EXACT_ALGEBRAIC,
            True,
            "clifford+t+ccx+rational-turns+magic_t",
            ("arbitrary",),
            self.max_amplitudes.bit_length() - 1,
            notes="Exact polynomial residues; conductor <=256; no truncation",
        )

    def available(self):
        return True, "Kellogg rational cyclotomic arithmetic"

    def conductor(self, program):
        order = 8
        if len(program.operations) > 4096:
            raise ValueError("operation budget exceeded")
        for op in program.operations:
            phase = phase_turns(op.gate)
            arity = 1 if phase else _ARITY.get(op.gate)
            if arity is None or len(op.qubits) != arity or len(set(op.qubits)) != arity:
                raise ValueError("unsupported gate or invalid distinct operands")
            if any(type(q) is not int for q in op.qubits):
                raise ValueError("qubits must be strict integers")
            if phase:
                order = lcm(order, phase[1].denominator * (2 if phase[0] == "rz" else 1))
                cyclotomic_polynomial(order)
        degree = len(cyclotomic_polynomial(order)) - 1
        operation_cost = sum(
            6 if op.gate == "magic_t" else 1
            for op in program.operations
        )
        work = operation_cost * (1 << program.n_qubits) * degree * degree
        if work > (1 << 26):
            raise ValueError("cyclotomic arithmetic work exceeds admission budget")
        return order

    def admit(self, program):
        reason = "exact rational-turn program within conductor and amplitude bounds"
        admitted = True
        try:
            if (
                type(program.n_qubits) is not int
                or program.n_qubits > self.max_amplitudes.bit_length() - 1
            ):
                raise ValueError("cyclotomic state exceeds amplitude budget")
            self.conductor(program)
        except (ValueError, TypeError) as exc:
            admitted, reason = False, str(exc)
        return Admission(admitted, self.name, reason, ExecutionClass.EXACT_ALGEBRAIC)

    def execute(self, program, **options):
        if set(options) - {"exact_payload"}:
            raise ValueError(
                "cyclotomic execution emits exact Born probabilities; no sampling options"
            )
        if "exact_payload" in options and type(options["exact_payload"]) is not bool:
            raise ValueError("exact_payload must be boolean")
        admission = self.admit(program)
        if not admission.admitted:
            raise ValueError(admission.reason)
        order = self.conductor(program)
        zero, one = Cyclotomic(order), Cyclotomic(order, (1,))
        root = Cyclotomic.root(order)
        t = root ** (order // 8)
        imaginary = t**2
        sqrt2 = t + t.conjugate()
        state = [zero] * (1 << program.n_qubits)
        state[0] = one
        injections = []
        for index, op in enumerate(program.operations):
            gate, q = op.gate, op.qubits[0]
            phase = phase_turns(gate)
            if phase:
                family, turns = phase
                exponent = turns * order
                if exponent.denominator != 1:
                    raise ArithmeticError("rotation not closed in selected field")
                factor = root ** int(exponent)
                global_factor = root ** int(-exponent / 2) if family == "rz" else one
                for i, amplitude in enumerate(state):
                    state[i] = amplitude * global_factor * (factor if i >> q & 1 else one)
            elif gate in ("cx", "cnot", "cz", "swap", "ccx"):
                target = op.qubits[-1]
                out = [zero] * len(state)
                for i, amplitude in enumerate(state):
                    j = i
                    if gate == "swap":
                        if ((i >> q) ^ (i >> target)) & 1:
                            j ^= (1 << q) | (1 << target)
                    elif gate == "cz":
                        if i >> q & 1 and i >> target & 1:
                            amplitude = -amplitude
                    elif all(i >> control & 1 for control in op.qubits[:-1]):
                        j ^= 1 << target
                    out[j] = amplitude
                state = out
            else:
                if gate == "magic_t":
                    before = state[:]
                    branch0 = [a * (t if i >> q & 1 else one) / sqrt2 for i, a in enumerate(before)]
                    branch1 = [a * (one if i >> q & 1 else t) / sqrt2 for i, a in enumerate(before)]
                    probability = sum((a.conjugate() * a for a in branch0), zero)
                    probability1 = sum((a.conjugate() * a for a in branch1), zero)
                    corrected0 = [a * sqrt2 for a in branch0]
                    corrected1 = [
                        a * sqrt2 * (imaginary if i >> q & 1 else one) / t
                        for i, a in enumerate(branch1)
                    ]
                    if (
                        corrected0 != corrected1
                        or not probability.same_value(Fraction(1, 2))
                        or probability1 != probability
                    ):
                        raise ArithmeticError(
                            "magic injection instrument failed exact branch proof"
                        )
                    injections.append(
                        {
                            "operation": index,
                            "resource": "A",
                            "consumed": 1,
                            "branch_probabilities": [[1, 2], [1, 2]],
                            "branch1_correction": "S",
                            "branch1_global_phase": t.to_dict(),
                        }
                    )
                    state = corrected0
                    continue
                for i in range(len(state)):
                    if i >> q & 1:
                        continue
                    j = i | (1 << q)
                    a, b = state[i], state[j]
                    if gate == "h":
                        state[i], state[j] = (a + b) / sqrt2, (a - b) / sqrt2
                    elif gate == "x":
                        state[i], state[j] = b, a
                    elif gate == "y":
                        state[i], state[j] = -imaginary * b, imaginary * a
                    else:
                        exponent = {"i": 0, "z": 4, "s": 2, "sdg": -2, "t": 1, "tdg": -1}[gate]
                        state[j] = b * (t**exponent)
        probabilities = [a.conjugate() * a for a in state]
        if not sum(probabilities, zero).same_value(1):
            raise ArithmeticError("cyclotomic evolution violated exact norm")
        return ExecutionResult(
            self.name,
            ExecutionClass.EXACT_ALGEBRAIC,
            TruthClass.EXACT,
            program.n_qubits,
            program.digest(),
            True,
            payload={
                "field": f"Q(zeta_{order})",
                "conductor": order,
                "amplitudes": [a.to_dict() for a in state],
                "probabilities": [p.to_dict() for p in probabilities],
                "norm_squared": [1, 1],
                "magic_injections": injections,
            },
        )
