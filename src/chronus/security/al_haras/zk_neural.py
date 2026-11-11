"""
AL HARAS — inference trace receipts over F_257 (the "zk-ML" frontier in the notes)
================================================================================
"Speak friend and enter or you shall not pass." (motto from the product notes)

What is computed (exactly, with integers modulo 257)
----------------------------------------------------
* A toy layer: an 8-step affine recurrence
      t_0 = sum(x) mod 257,   t_{i+1} = a * t_i + c_i (i = 0..6),   output y = t_7,
  whose parameters (a in 1..17, c_i in 0..12) are derived from SHA-256 of the
  weight commitment string. No real model weights are involved.
* The trace polynomial P (degree < 8) with P(w^i) = t_i on H = {w^i}, where
  w = 4 has order 8 in F_257, and B interpolating c_0..c_6 (and 0 at w^7).
* The transition polynomial C(X) = P(wX) - a P(X) - B(X). It vanishes on
  T = {w^0, ..., w^6} exactly when all seven transitions hold, i.e. exactly when
  Z_T(X) = prod_{i<7} (X - w^i) divides C. The quotient Q = C / Z_T comes from
  exact long division; the remainder R is zero iff every transition holds, and
  R(w^i) != 0 names each violated transition i.
* A receipt: SHA-256 commitment to (weight commitment, input, trace), a
  Fiat-Shamir point z outside H derived from that commitment, and the values
  P(z), P(wz), B(z), Q(z) and Z_T(z).

What the verifier checks (``check_inference_receipt``)
------------------------------------------------------
Everything is recomputed from the disclosed trace, the public input, the claimed
output and the weight commitment the verifier trusts: the boundary t_0 = sum(x),
the output t_7 = y, exact divisibility of C by Z_T, the commitment, the
challenge z, every claimed evaluation, and C(z) = Q(z) Z_T(z). Tampering is
detected by these computations; no flag in a receipt or package is trusted.

What this is not
----------------
It is not zero-knowledge (the whole trace is disclosed), not succinct (the
verifier re-interpolates the trace, so its work grows with the trace length),
and it has no FRI or other low-degree test and no opening proofs binding the
evaluations to a commitment. The out-of-domain evaluation is a consistency
check of the receipt: on its own, one point over F_257 would accept a false
identity of degree 7 with probability up to 7/249. No timing claim is made;
measured wall-clock times are reported in nanoseconds where useful.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

FIELD_P = 257  # Fermat prime
TRACE_LEN = 8
OMEGA_8 = 4  # 4^4 = 256 = -1 and 4^8 = 1 (mod 257): a primitive 8th root of unity
DOMAIN_H = tuple(pow(OMEGA_8, i, FIELD_P) for i in range(TRACE_LEN))
TRANSITIONS = TRACE_LEN - 1
MAX_INPUT_VALUES = 4096
RECEIPT_VERSION = "al-haras-trace-receipt/1"
PROOF_TYPE = "AIR_TRACE_RECEIPT_F257"

# The identity C - Q * Z_T has degree at most TRACE_LEN - 1; z is drawn outside H.
SINGLE_POINT_ERROR_BOUND = Fraction(TRACE_LEN - 1, FIELD_P - TRACE_LEN)

RECEIPT_PROPERTIES: Dict[str, Any] = {
    "zero_knowledge": False,
    "succinct": False,
    "fri_low_degree_test": False,
    "opening_proofs": False,
    "trace_disclosed": True,
    "verification": "exact recomputation of the trace polynomial, quotient and evaluations from the disclosed trace",
    "single_point_check_error_bound": f"{SINGLE_POINT_ERROR_BOUND.numerator}/{SINGLE_POINT_ERROR_BOUND.denominator}",
}

# Placeholder commitments registered by default for the demo endpoint. They are
# arbitrary strings, not hashes of real model weights.
DEMO_WEIGHT_COMMITMENTS: Dict[str, str] = {
    "layer_dense_0": "a" * 64,
    "layer_dense_1": "b" * 64,
}


# ------------------------------------------------------------------------------
# Polynomials over F_p (coefficient lists, lowest degree first)
# ------------------------------------------------------------------------------


def _trim(poly: Sequence[int], modulus: int = FIELD_P) -> List[int]:
    out = [c % modulus for c in poly]
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return out or [0]


def _degree(poly: Sequence[int]) -> int:
    """Degree of a polynomial; -1 for the zero polynomial."""
    t = _trim(poly)
    return -1 if t == [0] else len(t) - 1


def poly_eval(poly: List[int], x: int, modulus: int = FIELD_P) -> int:
    """Evaluate sum(c_i * x^i) mod p with Horner's rule."""
    res = 0
    for coeff in reversed(poly):
        res = (res * x + coeff) % modulus
    return res


def poly_add(a: List[int], b: List[int], modulus: int = FIELD_P) -> List[int]:
    """Polynomial addition in F_p[X]."""
    length = max(len(a), len(b))
    return _trim([(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(length)], modulus)


def poly_sub(a: List[int], b: List[int], modulus: int = FIELD_P) -> List[int]:
    """Polynomial subtraction in F_p[X]."""
    return poly_add(a, [-c for c in b], modulus)


def poly_mul(a: List[int], b: List[int], modulus: int = FIELD_P) -> List[int]:
    """Polynomial multiplication in F_p[X]."""
    res = [0] * (len(a) + len(b) - 1)
    for i, c1 in enumerate(a):
        for j, c2 in enumerate(b):
            res[i + j] = (res[i + j] + c1 * c2) % modulus
    return res


def poly_divmod(
    numerator: List[int],
    denominator: List[int],
    modulus: int = FIELD_P,
) -> Tuple[List[int], List[int]]:
    """Exact long division over F_p (p prime): returns (quotient, remainder)."""
    num = _trim(numerator, modulus)
    den = _trim(denominator, modulus)
    if den == [0]:
        raise ZeroDivisionError("Polynomial division by zero polynomial.")
    if len(num) < len(den):
        return [0], num
    inv_lead = pow(den[-1], -1, modulus)
    quot = [0] * (len(num) - len(den) + 1)
    rem = list(num)
    for i in range(len(quot) - 1, -1, -1):
        coeff = rem[i + len(den) - 1] * inv_lead % modulus
        quot[i] = coeff
        if coeff:
            for j, d in enumerate(den):
                rem[i + j] = (rem[i + j] - coeff * d) % modulus
    return _trim(quot, modulus), _trim(rem[: len(den) - 1], modulus)


def polynomial_divide_exact(
    numerator: List[int],
    denominator: List[int],
    modulus: int = FIELD_P,
) -> List[int]:
    """Quotient of an exact division over F_p; ValueError if the remainder is non-zero."""
    quot, rem = poly_divmod(numerator, denominator, modulus)
    if rem != [0]:
        raise ValueError("Polynomial division leaves a non-zero remainder.")
    return quot


def _scale_argument(poly: Sequence[int], factor: int) -> List[int]:
    """Coefficients of P(factor * X)."""
    return [c * pow(factor, j, FIELD_P) % FIELD_P for j, c in enumerate(poly)]


def interpolate_trace_polynomial(trace_T: List[int]) -> List[int]:
    """Coefficients of P (degree < 8) with P(4^i) = trace_T[i] over F_257 (inverse DFT, w = 4)."""
    if len(trace_T) != TRACE_LEN:
        raise ValueError(f"a trace has exactly {TRACE_LEN} values")
    inv_n = pow(TRACE_LEN, -1, FIELD_P)
    coeffs = []
    for j in range(TRACE_LEN):
        s = sum(trace_T[k] * pow(OMEGA_8, (-j * k) % TRACE_LEN, FIELD_P) for k in range(TRACE_LEN))
        coeffs.append(s * inv_n % FIELD_P)
    return coeffs


def compute_vanishing_polynomial_on_trace_domain() -> List[int]:
    """Z_H(X) = X^8 - 1, which vanishes on the 8th roots of unity H in F_257."""
    z_h = [0] * (TRACE_LEN + 1)
    z_h[0] = FIELD_P - 1
    z_h[TRACE_LEN] = 1
    return z_h


def transition_vanishing_polynomial() -> List[int]:
    """Z_T(X) = prod_{i<7} (X - 4^i) = (X^8 - 1) / (X - 4^7): vanishes on the transition points."""
    poly = [1]
    for i in range(TRANSITIONS):
        poly = poly_mul(poly, [(-DOMAIN_H[i]) % FIELD_P, 1])
    return _trim(poly)


# ------------------------------------------------------------------------------
# The toy layer and its constraint polynomials
# ------------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_input(values: Any) -> List[int]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise TypeError("the input must be a list of integers")
    if len(values) > MAX_INPUT_VALUES:
        raise ValueError(f"the input has more than {MAX_INPUT_VALUES} values")
    if not all(_is_int(v) for v in values):
        raise TypeError("input values must be integers")
    return list(values)


def _validate_trace(trace: Any) -> List[int]:
    if not isinstance(trace, (list, tuple)) or len(trace) != TRACE_LEN:
        raise ValueError(f"a trace is a list of {TRACE_LEN} field elements")
    if not all(_is_int(v) and 0 <= v < FIELD_P for v in trace):
        raise ValueError(f"trace values must be integers in 0..{FIELD_P - 1}")
    return list(trace)


def derive_layer_parameters(com_W: str) -> Tuple[int, List[int]]:
    """(a, [c_0..c_6]) from SHA-256 of the commitment string: a = h[0] mod 17 + 1, c_i = h[i+1] mod 13."""
    if not isinstance(com_W, str) or not com_W:
        raise ValueError("the weight commitment must be a non-empty string")
    h = hashlib.sha256(com_W.encode("utf-8")).digest()
    return h[0] % 17 + 1, [h[i] % 13 for i in range(1, TRACE_LEN)]


def forward_pass_with_trace(sensor_input_x: List[int], com_W: str) -> Tuple[int, List[int]]:
    """Run the toy layer on ``sensor_input_x``; returns (y, trace) with y = trace[7]."""
    x = _validate_input(sensor_input_x)
    a, offsets = derive_layer_parameters(com_W)
    trace = [sum(x) % FIELD_P]
    for c in offsets:
        trace.append((trace[-1] * a + c) % FIELD_P)
    return trace[-1], trace


def constraint_polynomials(a: int, offsets: Sequence[int], trace: Sequence[int]) -> Dict[str, List[int]]:
    """P, P(wX), B, C = P(wX) - a P - B, Z_T, and (Q, R) = divmod(C, Z_T)."""
    p_poly = interpolate_trace_polynomial(list(trace))
    b_poly = interpolate_trace_polynomial(list(offsets) + [0])
    p_shift = _scale_argument(p_poly, OMEGA_8)
    c_poly = _trim([ps - a * p - b for ps, p, b in zip(p_shift, p_poly, b_poly)])
    z_t = transition_vanishing_polynomial()
    q_poly, r_poly = poly_divmod(c_poly, z_t)
    return {"P": p_poly, "P_shift": p_shift, "B": b_poly, "C": c_poly, "Z_T": z_t, "Q": q_poly, "R": r_poly}


def _trace_commitment(com_W: str, x: Sequence[int], trace: Sequence[int]) -> str:
    payload = json.dumps(
        {"version": RECEIPT_VERSION, "com_W": com_W, "input": list(x), "trace": list(trace)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _poly_commitment(poly: Sequence[int]) -> str:
    return hashlib.sha256(json.dumps(_trim(poly), separators=(",", ":")).encode("utf-8")).hexdigest()


def fiat_shamir_challenge(seed: str) -> int:
    """Point of F_257 outside H derived from SHA-256(seed:counter) (first counter that lands outside H)."""
    counter = 0
    while True:
        digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        z = int.from_bytes(digest, "big") % FIELD_P
        if z not in DOMAIN_H:
            return z
        counter += 1


def _evaluations(polys: Dict[str, List[int]], z: int) -> Dict[str, int]:
    return {
        "eval_P_at_z": poly_eval(polys["P"], z),
        "eval_P_at_omega_z": poly_eval(polys["P"], OMEGA_8 * z % FIELD_P),
        "eval_B_at_z": poly_eval(polys["B"], z),
        "eval_Q_at_z": poly_eval(polys["Q"], z),
        "eval_ZT_at_z": poly_eval(polys["Z_T"], z),
    }


def build_trace_receipt(com_W: str, sensor_input_x: List[int], trace: List[int]) -> Dict[str, Any]:
    """Receipt for a disclosed trace (see the module docstring); no verdict is included."""
    x = _validate_input(sensor_input_x)
    t = _validate_trace(trace)
    a, offsets = derive_layer_parameters(com_W)
    polys = constraint_polynomials(a, offsets, t)
    commitment = _trace_commitment(com_W, x, t)
    z = fiat_shamir_challenge(commitment)
    receipt: Dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "proof_type": PROOF_TYPE,
        "field": f"F_{FIELD_P}",
        "com_W": com_W,
        "input": x,
        "trace": t,
        "claimed_output": t[-1],
        "commitment": commitment,
        "challenge_z": z,
        "trace_poly_degree": _degree(polys["P"]),
        "quotient_poly_degree": _degree(polys["Q"]),
        "properties": dict(RECEIPT_PROPERTIES),
    }
    receipt.update(_evaluations(polys, z))
    return receipt


# ------------------------------------------------------------------------------
# Verification
# ------------------------------------------------------------------------------

# (check name, reason code reported when it is the first failing check)
CHECK_ORDER: List[Tuple[str, str]] = [
    ("trace_well_formed", "MALFORMED_TRACE"),
    ("input_well_formed", "MALFORMED_INPUT"),
    ("weight_commitment_matches", "WEIGHT_COMMITMENT_MISMATCH"),
    ("input_matches", "INPUT_MISMATCH"),
    ("boundary_input", "BOUNDARY_CONSTRAINT_VIOLATED"),
    ("output_matches", "OUTPUT_MISMATCH"),
    ("transitions_hold", "TRANSITION_CONSTRAINT_VIOLATED"),
    ("commitment_matches", "COMMITMENT_MISMATCH"),
    ("challenge_matches", "CHALLENGE_MISMATCH"),
    ("evaluations_match", "EVALUATION_MISMATCH"),
    ("identity_at_z", "IDENTITY_FAILS_AT_Z"),
]
REASON_CODES = dict(CHECK_ORDER)


def _report(checks: Dict[str, bool], failing: List[int]) -> Dict[str, Any]:
    failed = [name for name, _ in CHECK_ORDER if not checks[name]]
    return {
        "verified": not failed,
        "checks": dict(checks),
        "failed_checks": failed,
        "reason": REASON_CODES[failed[0]] if failed else None,
        "failing_transitions": failing,
        "verifier": "check_inference_receipt: exact recomputation from the disclosed trace",
    }


def check_inference_receipt(
    receipt: Dict[str, Any],
    com_W: str,
    sensor_input_x: List[int],
    y_inference: int,
) -> Dict[str, Any]:
    """Recompute and compare every part of a receipt; ``verified`` is True only if all checks hold.

    ``com_W`` is the weight commitment the verifier trusts (ValueError if it is
    not a non-empty string); the layer parameters are derived from it, never from
    the receipt. Fields such as ``verified`` that a receipt may carry are ignored.
    """
    a, offsets = derive_layer_parameters(com_W)
    checks = {name: False for name, _ in CHECK_ORDER}
    failing: List[int] = []
    receipt = receipt if isinstance(receipt, dict) else {}
    try:
        trace = _validate_trace(receipt.get("trace"))
    except ValueError:
        return _report(checks, failing)
    checks["trace_well_formed"] = True
    try:
        x = _validate_input(sensor_input_x)
    except (TypeError, ValueError):
        return _report(checks, failing)
    checks["input_well_formed"] = True

    checks["weight_commitment_matches"] = receipt.get("com_W") == com_W
    checks["input_matches"] = receipt.get("input") == x
    checks["boundary_input"] = trace[0] == sum(x) % FIELD_P
    checks["output_matches"] = (
        _is_int(y_inference) and y_inference == trace[-1] and receipt.get("claimed_output") == y_inference
    )

    polys = constraint_polynomials(a, offsets, trace)
    failing = [i for i in range(TRANSITIONS) if poly_eval(polys["R"], DOMAIN_H[i]) != 0]
    checks["transitions_hold"] = polys["R"] == [0]

    commitment = _trace_commitment(com_W, x, trace)
    checks["commitment_matches"] = receipt.get("commitment") == commitment
    z = fiat_shamir_challenge(commitment)
    checks["challenge_matches"] = receipt.get("challenge_z") == z

    expected = _evaluations(polys, z)
    checks["evaluations_match"] = all(receipt.get(k) == v for k, v in expected.items())
    claimed = {k: receipt.get(k) for k in expected}
    if all(_is_int(v) for v in claimed.values()):
        c_at_z = (claimed["eval_P_at_omega_z"] - a * claimed["eval_P_at_z"] - claimed["eval_B_at_z"]) % FIELD_P
        checks["identity_at_z"] = c_at_z == claimed["eval_Q_at_z"] * expected["eval_ZT_at_z"] % FIELD_P
    return _report(checks, failing)


def verify_stark_quotient(
    proof_receipt: Dict[str, Any],
    com_W: str,
    sensor_input_x: List[int],
    y_inference: int,
) -> bool:
    """True iff ``check_inference_receipt`` accepts the receipt (legacy name: no STARK is involved)."""
    return check_inference_receipt(proof_receipt, com_W, sensor_input_x, y_inference)["verified"]


def generate_fri_stark_proof(P_X: List[int], Q_X: List[int], Z_H_X: List[int]) -> Dict[str, Any]:
    """Evaluation record for an identity P = Q * Z_H at one Fiat-Shamir point (legacy name).

    No FRI, low-degree test or opening proof is produced: the record holds SHA-256
    commitments to the canonical coefficient lists, a point z outside H, the three
    evaluations and whether P(z) = Q(z) Z_H(z). Checking the identity itself
    requires the polynomials (see ``check_inference_receipt``).
    """
    sha_p, sha_q = _poly_commitment(P_X), _poly_commitment(Q_X)
    z = fiat_shamir_challenge(sha_p + sha_q)
    val_p, val_q, val_zh = poly_eval(P_X, z), poly_eval(Q_X, z), poly_eval(Z_H_X, z)
    return {
        "proof_type": "POLY_EVALUATION_RECORD_F257",
        "fri_performed": False,
        "challenge_z": z,
        "eval_P_at_z": val_p,
        "eval_Q_at_z": val_q,
        "eval_ZH_at_z": val_zh,
        "identity_holds_at_z": val_p == val_q * val_zh % FIELD_P,
        "sha256_P": sha_p,
        "sha256_Q": sha_q,
        "trace_poly_degree": _degree(P_X),
        "quotient_poly_degree": _degree(Q_X),
    }


# ------------------------------------------------------------------------------
# Engines used by the API
# ------------------------------------------------------------------------------


@dataclass
class NeuralLayerTrace:
    """One execution of the toy layer: ``output_vector`` is the trace t_0..t_7 (t_7 is the output)."""

    layer_name: str
    input_vector: List[int]
    weights_fingerprint: str
    output_vector: List[int]


class VerifiableNeuralComputeEngine:
    """Prover and verifier for the toy layer, keyed by registered weight commitments.

    The verifier accepts a package only if the layer is registered, the package
    names the registered commitment, and ``check_inference_receipt`` (run with
    the registered commitment) accepts the receipt.
    """

    def __init__(
        self,
        sovereign_model_id: str = "demo_model",
        registered_commitments: Optional[Dict[str, str]] = None,
    ) -> None:
        self.sovereign_model_id = sovereign_model_id
        self._registered: Dict[str, str] = {}
        source = DEMO_WEIGHT_COMMITMENTS if registered_commitments is None else registered_commitments
        for layer_name, root in source.items():
            self.register_certified_weights(layer_name, root)

    def register_certified_weights(self, layer_name: str, merkle_root: str) -> None:
        """Register the weight commitment the verifier accepts for ``layer_name`` (legacy name)."""
        if not isinstance(merkle_root, str) or not merkle_root:
            raise ValueError("a weight commitment must be a non-empty string")
        self._registered[layer_name] = merkle_root.lower()

    def registered_commitment(self, layer_name: str) -> Optional[str]:
        return self._registered.get(layer_name)

    def generate_inference_proof(
        self,
        layer_name: str,
        input_data: List[int],
        weights_root: str,
        simulate_tampering: bool = False,
    ) -> Dict[str, Any]:
        """Run the layer with the parameters of ``weights_root`` and build a receipt.

        ``simulate_tampering`` models a dishonest prover: after the honest run,
        trace value t_3 is altered before the receipt is built. It does not set
        any verification field; the verifier has to detect the change.
        """
        t0 = time.perf_counter_ns()
        if not isinstance(weights_root, str) or not weights_root:
            raise ValueError("weights_root must be a non-empty string")
        root = weights_root.lower()
        x = _validate_input(input_data)
        _, trace = forward_pass_with_trace(x, root)
        if simulate_tampering:
            trace[3] = (trace[3] + 9999) % FIELD_P
        receipt = build_trace_receipt(root, x, trace)
        return {
            "model_id": self.sovereign_model_id,
            "layer_name": layer_name,
            "weights_root": root,
            "input_data": x,
            "claimed_output": trace[-1],
            "trace_length": len(trace),
            "proof": receipt,
            "simulation": {"tampering_simulated": bool(simulate_tampering)},
            "generation_time_ns": time.perf_counter_ns() - t0,
        }

    def verify_inference_proof(self, proof_package: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a package against the registry and by exact recomputation."""
        t0 = time.perf_counter_ns()
        package = proof_package if isinstance(proof_package, dict) else {}
        layer_name = package.get("layer_name")
        registered = self._registered.get(layer_name) if isinstance(layer_name, str) else None
        receipt = package.get("proof")
        result: Dict[str, Any] = {
            "model_id": package.get("model_id"),
            "layer_name": layer_name,
            "proof_type": PROOF_TYPE,
            "properties": dict(RECEIPT_PROPERTIES),
        }
        if registered is None or not isinstance(receipt, dict):
            reason = "LAYER_NOT_REGISTERED" if registered is None else "MISSING_RECEIPT"
            result.update(
                {
                    "verified": False,
                    "status": "REJECTED",
                    "reason": reason,
                    "failed_checks": [reason.lower()],
                    "checks": {},
                    "failing_transitions": [],
                    "verification_time_ns": time.perf_counter_ns() - t0,
                }
            )
            return result
        root = package.get("weights_root")
        weights_registered = isinstance(root, str) and root.lower() == registered
        report = check_inference_receipt(receipt, registered, package.get("input_data"), package.get("claimed_output"))
        checks = {"weights_root_registered": weights_registered}
        checks.update(report["checks"])
        failed = [name for name, ok in checks.items() if not ok]
        if not weights_registered:
            reason: Optional[str] = "WEIGHTS_ROOT_NOT_REGISTERED"
        else:
            reason = report["reason"]
        result.update(
            {
                "verified": not failed,
                "status": "VERIFIED" if not failed else "REJECTED",
                "reason": reason,
                "failed_checks": failed,
                "checks": checks,
                "failing_transitions": report["failing_transitions"],
                "verification_time_ns": time.perf_counter_ns() - t0,
            }
        )
        return result


class LineRateVerifiableNeuralCompute:
    """Prove-and-check of the toy layer for one weight commitment.

    The class name is kept for compatibility; nothing here has been measured at
    line rate. ``execute_and_prove_inference`` returns the output and a receipt;
    the receipt's ``verified`` field is the result of running
    ``check_inference_receipt`` on it in-process. An independent verifier must
    re-run that check itself and ignore the field.
    """

    def __init__(self, model_weights_commitment: str) -> None:
        if not isinstance(model_weights_commitment, str) or not model_weights_commitment:
            raise ValueError("model_weights_commitment must be a non-empty string")
        self.com_W = model_weights_commitment

    def execute_and_prove_inference(self, sensor_input_x: List[int]) -> Tuple[int, Dict[str, Any]]:
        x = _validate_input(sensor_input_x)
        y_inference, trace = forward_pass_with_trace(x, self.com_W)
        receipt = build_trace_receipt(self.com_W, x, trace)
        t0 = time.perf_counter_ns()
        report = check_inference_receipt(receipt, self.com_W, x, y_inference)
        receipt["verified"] = report["verified"]
        receipt["verification"] = {
            "checks": report["checks"],
            "failed_checks": report["failed_checks"],
            "failing_transitions": report["failing_transitions"],
            "verifier": report["verifier"],
            "verification_time_ns": time.perf_counter_ns() - t0,
        }
        return y_inference, receipt
