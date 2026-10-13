"""Exact finite Hamiltonian evolution; no numerical diagonalisation or fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import numbers
from pathlib import Path

import sympy as sp

from ..adapters.base import BackendAbsent
from ..family_algebra import PhiElement

PHI = (1 + sp.sqrt(5)) / 2
MAX_STATE_DIMENSION = 4096
MAX_OPERATOR_DIMENSION = 512
MAX_TRANSPORT_NODES = 4096
MAX_TRANSPORT_BITS = 4096
MAX_TRANSPORT_EXPONENT = 64


def scalar(value, *, legacy_encoding=False):
    """Legacy floats are exact binary input values, never ideal constants."""
    if isinstance(value, PhiElement):
        return (
            sp.Rational(value.a.numerator, value.a.denominator)
            + sp.Rational(value.b.numerator, value.b.denominator) * PHI
        )
    if isinstance(value, Fraction):
        return sp.Rational(value.numerator, value.denominator)
    if type(value) is bool:
        raise ValueError("boolean is not a quantum amplitude")
    if isinstance(value, numbers.Integral):
        return sp.Integer(int(value))
    if isinstance(value, sp.Basic):
        if value.free_symbols or value.has(sp.Float) or value.is_finite is not True:
            raise ValueError("closed finite exact expression required")
        return value
    if legacy_encoding and isinstance(value, numbers.Real):
        try:
            a, b = value.as_integer_ratio()
        except (AttributeError, OverflowError, ValueError) as exc:
            raise ValueError("finite lossless binary input required") from exc
        return sp.Rational(a, b)
    if legacy_encoding and isinstance(value, numbers.Complex):
        return scalar(value.real, legacy_encoding=True) + sp.I * scalar(
            value.imag, legacy_encoding=True
        )
    raise ValueError("exact scalar required; no implicit numerical fallback")


def _zero(value):
    return sp.simplify(value) == 0


def _manifest(values):
    return [sp.srepr(x) for x in values]


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ExactVector(tuple):
    """Compatibility shape/accessors without converting results to floats."""

    @property
    def real(self):
        return ExactVector(sp.simplify(sp.re(x)) for x in self)

    @property
    def imag(self):
        return ExactVector(sp.simplify(sp.im(x)) for x in self)

    @property
    def shape(self):
        return (len(self),)

    def tolist(self):
        return list(self)

    def sum(self):
        return sp.simplify(sum(self, sp.Integer(0)))


def encode_expression(value):
    value = scalar(value)
    if value == sp.I:
        return {"atom": "I"}
    if value == sp.pi:
        return {"atom": "pi"}
    if value == sp.E:
        return {"atom": "E"}
    if isinstance(value, sp.Rational):
        return {"rational": [int(value.p), int(value.q)]}
    functions = {
        sp.Add: "add",
        sp.Mul: "mul",
        sp.Pow: "pow",
        sp.exp: "exp",
        sp.sin: "sin",
        sp.cos: "cos",
    }
    if value.func not in functions:
        raise BackendAbsent("exact expression transport UNAVAILABLE for this function")
    return {
        "operator": functions[value.func],
        "args": [encode_expression(x) for x in value.args],
    }


def decode_expression(value, *, _depth=0, _budget=None):
    if _budget is None:
        _budget = [MAX_TRANSPORT_NODES]
    _budget[0] -= 1
    if _budget[0] < 0:
        raise ValueError("exact expression node quota")
    if _depth > 64 or not isinstance(value, dict):
        raise ValueError("bounded exact expression required")
    if set(value) == {"atom"}:
        if value["atom"] not in ("I", "pi", "E"):
            raise ValueError("unknown exact atom")
        return {"I": sp.I, "pi": sp.pi, "E": sp.E}[value["atom"]]
    if set(value) == {"rational"}:
        data = value["rational"]
        if (
            not isinstance(data, list)
            or len(data) != 2
            or any(type(x) is not int for x in data)
            or data[1] <= 0
        ):
            raise ValueError("canonical rational transport required")
        if any(abs(x).bit_length() > MAX_TRANSPORT_BITS for x in data):
            raise ValueError("exact expression rational bit quota")
        result = sp.Rational(*data)
        if [int(result.p), int(result.q)] != data:
            raise ValueError("noncanonical rational transport")
        return result
    if set(value) != {"operator", "args"}:
        raise ValueError("unknown exact expression fields")
    functions = {
        "add": sp.Add,
        "mul": sp.Mul,
        "pow": sp.Pow,
        "exp": sp.exp,
        "sin": sp.sin,
        "cos": sp.cos,
    }
    args = value["args"]
    if (
        value["operator"] not in functions
        or not isinstance(args, list)
        or not 1 <= len(args) <= 4096
    ):
        raise ValueError("unsupported expression constructor")
    if value["operator"] in ("pow",) and len(args) != 2:
        raise ValueError("power arity")
    if value["operator"] in ("exp", "sin", "cos") and len(args) != 1:
        raise ValueError("function arity")
    decoded = [decode_expression(x, _depth=_depth + 1, _budget=_budget) for x in args]
    if value["operator"] == "pow":
        exponent = decoded[1]
        if (
            not isinstance(exponent, sp.Rational)
            or abs(exponent) > MAX_TRANSPORT_EXPONENT
            or exponent.q > MAX_TRANSPORT_EXPONENT
        ):
            raise ValueError("exact power exponent quota")
        if decoded[0].count_ops() > 64:
            raise ValueError("exact power base quota")
    result = scalar(functions[value["operator"]](*decoded))
    if len(sp.srepr(result)) > 65536:
        raise ValueError("exact expression result quota")
    return result


@dataclass(frozen=True)
class ExactQuantumState:
    amplitudes: tuple
    evidence: dict = field(default_factory=dict, compare=False)

    def __post_init__(self):
        if not 0 < len(self.amplitudes) <= MAX_STATE_DIMENSION:
            raise ValueError("bounded exact state required")
        values = tuple(scalar(x) for x in self.amplitudes)
        norm = sp.simplify(sum(sp.conjugate(x) * x for x in values))
        if not _zero(norm - 1):
            raise ValueError(
                "exact state must have unit norm; no output renormalisation"
            )
        object.__setattr__(self, "amplitudes", ExactVector(values))

    @classmethod
    def prepare(cls, values, *, legacy_encoding=False):
        values = tuple(scalar(x, legacy_encoding=legacy_encoding) for x in values)
        if not 0 < len(values) <= MAX_STATE_DIMENSION:
            raise ValueError("bounded nonempty state required")
        norm = sp.simplify(sum(sp.conjugate(x) * x for x in values))
        if norm.is_positive is not True:
            raise BackendAbsent("exact state normalisation proof UNAVAILABLE")
        return cls(tuple(sp.simplify(x / sp.sqrt(norm)) for x in values))

    @property
    def probabilities(self):
        return ExactVector(sp.simplify(sp.conjugate(x) * x) for x in self.amplitudes)


def exact_hamiltonian_evolution(
    amplitudes, hamiltonian, time_value=1, *, legacy_encoding=False
):
    """Construct and apply e^(-iHt), then verify unitarity and state norm exactly.

    Diagonal and scalar-square-centred Hamiltonians execute at the full public
    dimension quota. General exact spectral/Jordan evolution is admitted only
    when its exact result can be materialised and verified within the bounded
    operator contract. Unsupported cases report UNAVAILABLE, not a float solve.
    """
    state = ExactQuantumState.prepare(amplitudes, legacy_encoding=legacy_encoding)
    n = len(state.amplitudes)
    if n > MAX_OPERATOR_DIMENSION:
        raise BackendAbsent("exact materialised operator dimension UNAVAILABLE")
    try:
        rows = [list(row) for row in hamiltonian]
    except TypeError as exc:
        raise ValueError("square Hamiltonian required") from exc
    if len(rows) != n or any(len(row) != n for row in rows):
        raise ValueError("dimension-matched square Hamiltonian required")
    h = sp.ImmutableMatrix(
        [[scalar(x, legacy_encoding=legacy_encoding) for x in row] for row in rows]
    )
    if any(not _zero(x) for x in h - h.H):
        raise ValueError("Hamiltonian must be exactly Hermitian; no symmetrisation")
    t = scalar(time_value, legacy_encoding=legacy_encoding)
    if t.is_real is not True:
        raise ValueError("exact real time required")
    eye = sp.eye(n)
    if h.is_diagonal():
        phases = tuple(sp.exp(-sp.I * h[i, i] * t) for i in range(n))
        if any(not _zero(sp.conjugate(p) * p - 1) for p in phases):
            raise BackendAbsent("exact diagonal unitary proof UNAVAILABLE")
        values = tuple(sp.simplify(p * x) for p, x in zip(phases, state.amplitudes))
        branch = "exact_diagonal_spectral"
    else:
        shift = sp.trace(h) / n
        centred = h - shift * eye
        square = centred * centred
        alpha = sp.simplify(square[0, 0])
        if all(_zero(x) for x in square - alpha * eye):
            if _zero(alpha):
                unitary = sp.exp(-sp.I * shift * t) * (eye - sp.I * t * centred)
            else:
                if alpha.is_positive is not True:
                    raise BackendAbsent(
                        "exact scalar-square positivity proof UNAVAILABLE"
                    )
                radius = sp.sqrt(alpha)
                unitary = sp.exp(-sp.I * shift * t) * (
                    sp.cos(radius * t) * eye
                    - sp.I * sp.sin(radius * t) * centred / radius
                )
            branch = "exact_scalar_square_spectral"
        else:
            if n > 8:
                raise BackendAbsent(
                    "general exact Jordan materialisation UNAVAILABLE beyond the declared quota"
                )
            try:
                unitary = (-sp.I * h * t).exp()
            except (NotImplementedError, ValueError) as exc:
                raise BackendAbsent(
                    "general exact Hamiltonian evolution UNAVAILABLE"
                ) from exc
            branch = "exact_jordan_spectral"
        if unitary.has(sp.Float) or any(
            not _zero(x) for x in unitary.H * unitary - eye
        ):
            raise BackendAbsent("exact unitary certificate UNAVAILABLE")
        values = tuple(
            sp.simplify(x) for x in unitary * sp.ImmutableMatrix(state.amplitudes)
        )
    result = ExactQuantumState(values)
    request = {
        "algorithm": "exact_hamiltonian_evolution",
        "input": _manifest(state.amplitudes),
        "hamiltonian": _manifest(h),
        "dimension": n,
        "time": sp.srepr(t),
    }
    request_digest = _digest(request)
    receipt = {
        "schema": "chronos.exact_hamiltonian_evolution/1",
        "requested_algorithm": request["algorithm"],
        "planned_algorithm": request["algorithm"],
        "executed_algorithm": request["algorithm"],
        "implementation_module": __name__,
        "implementation_digest": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "execution_mode": "exact_symbolic",
        "substrate": {"kind": "cpu", "arithmetic": "exact_sympy"},
        "plan_digest": request_digest,
        "geometry_digest": None,
        "iterations_work_performed": {"unitary_applications": 1, "state_dimension": n},
        "sha256d_verification": "NOT_APPLICABLE",
        "fallback_used": False,
        "fallback_reason": None,
        "input_encoding": (
            "exact_scalars_with_lossless_legacy_input_decoder"
            if legacy_encoding
            else "exact_scalars"
        ),
        "unitary_proof": True,
        "norm_squared": "1",
        "spectral_method": branch,
        "output_digest": _digest(_manifest(result.amplitudes)),
    }
    receipt["receipt_digest"] = _digest(receipt)
    return ExactQuantumState(result.amplitudes, receipt)


def decode_evolution_payload(payload):
    """Versioned exact tree input; legacy scalars are decoded losslessly."""

    def decode(value):
        return (
            decode_expression(value)
            if isinstance(value, dict)
            else scalar(value, legacy_encoding=True)
        )

    return (
        [decode(x) for x in payload["amplitudes"]],
        [[decode(x) for x in row] for row in payload["hamiltonian"]],
        decode(payload.get("time", 1)),
    )
