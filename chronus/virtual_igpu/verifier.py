"""Independent recompute-and-compare verification for virtual_igpu results.

The evidence chain proves *that* a workload executed and binds the result
bytes; it does not by itself prove the answer is correct.  This module is
the control-plane oracle for the workload kinds whose outputs are
deterministically recomputable **without re-invoking the executing
adapter** — a lying adapter cannot influence a recompute it never sees:

  ``sha256d_scan``    — re-scan the admitted nonce window with hashlib
  ``lucas_transform`` — exact integer L_n recurrence
  ``pisot_transform`` — nearest integer to φ**n (float64)
  ``phi_transform``   — φ**n, or per-element ``vector * φ`` (float64)
  ``cgemv``           — α·A·x + β·y in complex128 (small dims only)
  ``tensor_op``       — scale/add/matmul recompute; svd via reconstruction
  ``fold``            — decode the folded frame and compare to the payload

Kinds without an independent oracle (probe/store/retrieve/checkpoint/
unfold/custom) return ``verdict="unverifiable_kind"`` — the receipt records
that honestly instead of implying a check that never ran.

Float comparisons use a documented tight tolerance (``FLOAT_RTOL=1e-9``,
``FLOAT_ATOL=1e-12``): strict enough that a corrupted result cannot pass,
loose enough that a future physical backend with different IEEE-754
operation ordering is not falsely rejected.  Integer, digest, and shape
comparisons are exact.
"""
from __future__ import annotations

import base64
import hashlib
import math
from typing import Any, Callable, Mapping

import numpy as np

from .abi import Workload, WorkloadKind, WorkloadResult


# Verify-time bounds.  Recompute doubles the admission cost, so large
# numerical inputs are declared out of scope rather than silently trusted.
VERIFY_MAX_SCAN_NONCES = 1_000_000   # identical to the adapter's own bound
VERIFY_MAX_TENSOR_ELEMS = 4_194_304  # ~33 MiB of float64
VERIFY_MAX_CGEMV_ELEMS = 262_144     # one 512x512 complex matrix
FLOAT_RTOL = 1e-9
FLOAT_ATOL = 1e-12


class _OutOfBound(Exception):
    """Input exceeds the declared verify bound — not a correctness verdict."""


class _Unverifiable(Exception):
    """Output shape/op has no independent oracle — honestly unverifiable."""


def _float_close(a: Any, b: Any) -> bool:
    try:
        return math.isclose(float(a), float(b), rel_tol=FLOAT_RTOL, abs_tol=FLOAT_ATOL)
    except (TypeError, ValueError, OverflowError):
        return False


def _seq_close(reported: Any, expected: Any) -> bool:
    """Element-wise tolerance compare of equal-shape numeric arrays of any rank."""
    try:
        rep = np.asarray(reported, dtype=np.float64)
        exp = np.asarray(expected, dtype=np.float64)
    except (TypeError, ValueError):
        return False
    if rep.shape != exp.shape:
        return False
    diff = np.abs(rep - exp)
    bound = np.maximum(FLOAT_RTOL * np.maximum(np.abs(rep), np.abs(exp)), FLOAT_ATOL)
    return bool(np.all((rep == exp) | (diff <= bound)))


def _payload_bytes(value: Mapping[str, Any]) -> bytes:
    if "payload_b64" in value:
        return base64.b64decode(value["payload_b64"])
    if "payload_utf8" in value:
        return str(value["payload_utf8"]).encode("utf-8")
    if "payload" in value:
        p = value["payload"]
        if isinstance(p, (bytes, bytearray)):
            return bytes(p)
        return str(p).encode("utf-8")
    return b""


def _n_value(value: Mapping[str, Any]) -> int:
    n = value.get("n", value.get("index", 10))
    if type(n) is not int:
        raise ValueError("transform index must be an integer")
    return n


# --- per-kind recompute verifiers -------------------------------------------
# Each returns a list of human-readable mismatches; [] means match.


def _verify_sha256d_scan(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    if "header80_hex" in value:
        header80 = bytes.fromhex(str(value["header80_hex"]))
        if len(header80) != 80:
            return ["header80_hex did not encode 80 bytes"]
        prefix = header80[:76]
        start = int(value.get("start_nonce", int.from_bytes(header80[76:80], "little")))
        count = int(value.get("count", 1))
    else:
        if "prefix_b64" in value:
            prefix = base64.b64decode(value["prefix_b64"])
        elif "prefix_hex" in value:
            prefix = bytes.fromhex(str(value["prefix_hex"]))
        else:
            prefix = _payload_bytes(value)
        start = int(value.get("start_nonce", 0))
        count = int(value.get("count", 1))
    if len(prefix) != 76:
        return [f"input prefix is {len(prefix)} bytes; scan contract is 76"]
    explicit = value.get("nonces")
    if explicit is not None:
        # Exact ordered batch authorised by the caller: probe in submitted order.
        if (
            not isinstance(explicit, (list, tuple))
            or not explicit
            or any(isinstance(n, bool) or not isinstance(n, int) for n in explicit)
            or any(not 0 <= n <= 0xFFFFFFFF for n in explicit)
        ):
            return ["nonces must be a non-empty list of uint32 integers"]
        count = len(explicit)
        nonce_seq: Any = list(explicit)
    else:
        nonce_seq = None
    if count <= 0 or count > VERIFY_MAX_SCAN_NONCES:
        raise _OutOfBound(f"count={count} outside verify bound 1..{VERIFY_MAX_SCAN_NONCES}")
    target = value.get("target", value.get("target_hex"))
    if target is None:
        return ["no target/target_hex in workload input"]
    target_int = int(target, 16) if isinstance(target, str) else int(target)

    expected_hits: list[dict[str, Any]] = []
    checked = 0
    for i in range(count):
        nonce = nonce_seq[i] if nonce_seq is not None else start + i
        d2 = hashlib.sha256(
            hashlib.sha256(prefix + nonce.to_bytes(4, "little")).digest()
        ).digest()
        digest_int = int.from_bytes(d2[::-1], "big")
        checked += 1
        if digest_int <= target_int:
            expected_hits.append(
                {"nonce": nonce, "hash_hex": d2.hex(), "digest_int": digest_int}
            )
            break

    problems: list[str] = []
    reported_hits = list(out.get("hits") or [])
    if len(reported_hits) != len(expected_hits):
        problems.append(
            f"hits count {len(reported_hits)} != recomputed {len(expected_hits)}"
        )
    else:
        for rep, exp in zip(reported_hits, expected_hits):
            if int(rep.get("nonce", -1)) != exp["nonce"]:
                problems.append(f"hit nonce {rep.get('nonce')} != {exp['nonce']}")
            if str(rep.get("hash_hex", "")).lower() != exp["hash_hex"]:
                problems.append("hit hash_hex mismatch")
            if int(rep.get("digest_int", -1)) != exp["digest_int"]:
                problems.append("hit digest_int mismatch")
    if int(out.get("checked", -1)) != checked:
        problems.append(f"checked {out.get('checked')} != recomputed {checked}")
    if int(out.get("start_nonce", start)) != start:
        problems.append("start_nonce mismatch")
    return problems


def _verify_lucas(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    n = _n_value(value)
    if n < 0 or n > 10_000:
        raise _OutOfBound(f"n={n} outside declared domain 0..10000")
    if n == 0:
        expected = 2
    elif n == 1:
        expected = 1
    else:
        a, b = 2, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        expected = b
    problems: list[str] = []
    if type(out.get("lucas")) is not int or out["lucas"] != expected:
        problems.append(f"lucas({n}) reported {out.get('lucas')} != {expected}")
    if type(out.get("n")) is not int or out["n"] != n:
        problems.append("reported n mismatch")
    return problems


def _lucas(n: int) -> int:
    """Exact integer L_n — the reference recurrence, duplicated on purpose:
    an independent oracle must not call adapter internals."""
    if n == 0:
        return 2
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


#: float64 ceiling for φ^n — beyond n=1474 the scalar transform is out of
#: the declared numeric domain (phi_pow is then None on the wire, never inf).
PHI_FLOAT64_MAX_N = 1474


def _verify_pisot(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    n = _n_value(value)
    if n < 0 or n > 10_000:
        raise _OutOfBound(f"n={n} outside declared domain 0..10000")
    # Exact contract: round(φ^n) == L_n for n >= 2 (Pisot property);
    # n in {0, 1} are literal-rounding boundary cases.
    expected = 1 if n == 0 else 2 if n == 1 else _lucas(n)
    problems: list[str] = []
    if type(out.get("pisot_nearest")) is not int or out["pisot_nearest"] != expected:
        problems.append(
            f"pisot_nearest reported {out.get('pisot_nearest')} != {expected}"
        )
    reported_pow = out.get("phi_pow")
    if n <= PHI_FLOAT64_MAX_N:
        if not _float_close(reported_pow, ((1.0 + 5.0**0.5) / 2.0) ** n):
            problems.append("phi_pow mismatch")
    elif reported_pow is not None:
        problems.append("phi_pow must be absent beyond the float64 bound")
    return problems


def _verify_phi(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    phi = (1.0 + 5.0**0.5) / 2.0
    if "vector" in value:
        vec = np.asarray(value["vector"], dtype=np.float64)
        expected = (vec * phi).tolist()
        if not _seq_close(out.get("vector"), expected):
            return ["vector*phi mismatch"]
        return []
    n = _n_value(value)
    if n < 0 or n > 10_000:
        raise _OutOfBound(f"n={n} outside declared domain 0..10000")
    if n > PHI_FLOAT64_MAX_N:
        # Scalar φ^n is undeclared past the float64 ceiling; an "ok" result
        # here is out of contract, not merely unverifiable.
        return [f"phi_transform scalar reported ok outside float64 domain: n={n}"]
    if not _float_close(out.get("phi_pow"), phi**n):
        return ["phi_pow mismatch"]
    if type(out.get("n")) is not int or out["n"] != n:
        return ["reported n mismatch"]
    return []


def _verify_cgemv(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    a = np.asarray(value.get("a"), dtype=np.complex128)
    x = np.asarray(value.get("x"), dtype=np.complex128)
    if a.size > VERIFY_MAX_CGEMV_ELEMS:
        raise _OutOfBound(
            f"cgemv matrix {a.size} elems exceeds verify bound {VERIFY_MAX_CGEMV_ELEMS}"
        )
    alpha = complex(value.get("alpha", 1.0))
    beta = complex(value.get("beta", 0.0))
    y = np.asarray(
        value.get("y", np.zeros(a.shape[0], dtype=np.complex128)),
        dtype=np.complex128,
    )
    expected = alpha * (a @ x) + beta * y
    problems: list[str] = []
    if list(out.get("shape") or []) != list(expected.shape):
        problems.append(f"shape {out.get('shape')} != {list(expected.shape)}")
    reported = out.get("data") or []
    flat = [
        complex(float(pair[0]), float(pair[1])) for pair in reported
    ] if reported else []
    if len(flat) != expected.size:
        problems.append(f"data length {len(flat)} != {expected.size}")
    else:
        for i, (rep, exp) in enumerate(zip(flat, expected.tolist())):
            if not (
                _float_close(rep.real, exp.real) and _float_close(rep.imag, exp.imag)
            ):
                problems.append(f"cgemv[{i}] reported {rep} != {exp}")
                break
    return problems


#: tensor_op names the canonical ``tensor`` layer can independently re-derive.
_TENSOR_LAYER_OPS = {
    "scale": "scale",
    "mul_scalar": "scale",
    "add": "add",
    "elementwise_add": "add",
    "matmul": "matmul",
}


def _tensor_layer_operands(
    canonical: str, a: np.ndarray, value: Mapping[str, Any]
) -> list[np.ndarray] | None:
    """Operands in the ``tensor`` layer's convention, or None when it cannot express the op."""
    if canonical == "scale":
        scalar = float(value.get("scalar", value.get("alpha", 1.0)))
        return [a, np.asarray([scalar], dtype=np.float64)]
    if canonical == "add":
        b = np.asarray(value.get("b", 0.0), dtype=np.float64)
        if np.broadcast_shapes(a.shape, b.shape) != a.shape:
            return None
        return [a, np.broadcast_to(b, a.shape).copy()]
    return [a, np.asarray(value.get("b"), dtype=np.float64)]


def _verify_via_tensor_layer(
    op: str, a: np.ndarray, value: Mapping[str, Any], out: Mapping[str, Any]
) -> list[str] | None:
    """Single source of tensor verification: ``tensor.verification`` (folded-resident recompute).

    Returns the problem list, or None when the tensor layer could not run its re-check
    (the caller then falls back to the local NumPy recompute rather than skip verification).
    """
    canonical = _TENSOR_LAYER_OPS.get(op)
    if canonical is None:
        return None
    operands = _tensor_layer_operands(canonical, a, value)
    if operands is None:
        return None
    try:
        from tensor.verification import VERDICT_FAIL, VERDICT_PASS, verify_backend_output

        actual = np.asarray(out.get("data"), dtype=np.float64)
        verdict = verify_backend_output(canonical, operands, actual)
    except ValueError:
        return [f"{op} output is not a rectangular numeric array"]
    except Exception:  # tensor layer unavailable: caller falls back to the local recompute
        return None
    if verdict.verdict == VERDICT_PASS:
        return []
    if verdict.verdict == VERDICT_FAIL:
        return [f"{op} output mismatch ({verdict.method}): {verdict.detail}"]
    return None


def _verify_tensor_op(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    op = str(value.get("op", "scale"))
    a = np.asarray(value.get("a", value.get("x", [])), dtype=np.float64)
    if a.size > VERIFY_MAX_TENSOR_ELEMS:
        raise _OutOfBound(
            f"tensor_op input {a.size} elems exceeds verify bound "
            f"{VERIFY_MAX_TENSOR_ELEMS}"
        )
    delegated = _verify_via_tensor_layer(op, a, value, out)
    if delegated is not None:
        return delegated
    problems: list[str] = []
    if op in {"scale", "mul_scalar"}:
        scalar = float(value.get("scalar", value.get("alpha", 1.0)))
        expected = a * scalar
        if not _seq_close(out.get("data"), expected):
            problems.append("scale output mismatch")
    elif op in {"add", "elementwise_add"}:
        b = np.asarray(value.get("b", 0.0), dtype=np.float64)
        expected = a + b
        if not _seq_close(out.get("data"), expected):
            problems.append("add output mismatch")
    elif op == "matmul":
        b = np.asarray(value.get("b"), dtype=np.float64)
        expected = a @ b
        if not _seq_close(out.get("data"), expected):
            problems.append("matmul output mismatch")
    elif op == "svd":
        # Backend-independent check: verify the *reconstruction property*
        # u @ diag(s) @ vh ≈ a rather than bit-exact LAPACK factor equality.
        try:
            u = np.asarray(out.get("u"), dtype=np.float64)
            s = np.asarray(out.get("s"), dtype=np.float64)
            vh = np.asarray(out.get("vh"), dtype=np.float64)
            recon = (u * s) @ vh
            if recon.shape != a.shape or not np.allclose(
                recon, a, rtol=1e-6, atol=1e-9
            ):
                problems.append("svd reconstruction u·diag(s)·vh != a")
        except Exception as exc:  # malformed factor lists
            problems.append(f"svd output unverifiable: {exc}")
        return problems
    else:
        raise _Unverifiable(f"no independent oracle for tensor op {op!r}")
    if list(out.get("shape") or []) != list(expected.shape):
        problems.append(f"shape {out.get('shape')} != {list(expected.shape)}")
    return problems


def _verify_fold(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    payload = _payload_bytes(value)
    problems: list[str] = []
    try:
        ser = base64.b64decode(str(out["folded_b64"]))
    except Exception:
        return ["folded_b64 is not valid base64"]
    engine = str(out.get("engine", ""))
    decoded: bytes | None = None
    if ser.startswith(b'{"format":"aethel.zeckendorf.v1"'):
        import json as _json

        try:
            from aethel.encoding import ZeckendorfVector, unfold as aethel_unfold

            meta = _json.loads(ser.decode("utf-8"))
            blocks = tuple((int(a), int(b)) for a, b in meta["blocks"])
            z = ZeckendorfVector(blocks=blocks, total_bytes=int(meta["total_bytes"]))
            decoded = bytes(aethel_unfold(z))
        except Exception as exc:
            problems.append(f"aethel frame failed independent decode: {exc}")
    elif engine in {"length_prefix_identity", ""}:
        # length_prefix_identity frame: 4-byte LE length + payload
        if len(ser) >= 4:
            n = int.from_bytes(ser[:4], "little")
            decoded = ser[4 : 4 + n] if 4 + n <= len(ser) else ser[4:]
        else:
            decoded = ser
    else:
        raise _Unverifiable(
            f"fold engine {engine!r} has no independent decoder"
        )
    if decoded is not None and decoded != payload:
        problems.append(
            f"folded frame decodes to {len(decoded)}B != original {len(payload)}B"
        )
    if int(out.get("logical_bytes", -1)) != len(payload):
        problems.append("logical_bytes mismatch")
    if int(out.get("folded_bytes", -1)) != len(ser):
        problems.append("folded_bytes mismatch")
    return problems


def _verify_grid_geometry(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    from .geometric import verify_grid

    return verify_grid(value, out)


def _verify_modular_geometry(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    from .geometric import verify_modular

    return verify_modular(value, out)


def _verify_exact_graph(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    from .exact_graph import verify_exact_graph

    return verify_exact_graph(value, out)


def _verify_quantum_program(value: Mapping[str, Any], out: Mapping[str, Any]) -> list[str]:
    from .exact_quantum import verify_quantum_program

    return verify_quantum_program(value, out)


_VERIFIERS: dict[WorkloadKind, tuple[str, Callable[[Mapping[str, Any], Mapping[str, Any]], list[str]]]] = {
    WorkloadKind.GRID_GEOMETRY: ("coordinate_oracle:d4_components", _verify_grid_geometry),
    WorkloadKind.MODULAR_GEOMETRY: ("identity_oracle:psl2z", _verify_modular_geometry),
    WorkloadKind.EXACT_GRAPH: ("replay:kellogg:exact_graph", _verify_exact_graph),
    WorkloadKind.QUANTUM_PROGRAM: ("replay:turing:exact_certificate", _verify_quantum_program),
    WorkloadKind.SHA256D_SCAN: ("recompute:sha256d_scan:hashlib", _verify_sha256d_scan),
    WorkloadKind.LUCAS_TRANSFORM: ("recompute:lucas_transform:exact_recurrence", _verify_lucas),
    WorkloadKind.PISOT_TRANSFORM: ("recompute:pisot_transform:exact_integer_with_float64_diagnostic", _verify_pisot),
    WorkloadKind.PHI_TRANSFORM: ("recompute:phi_transform:float64", _verify_phi),
    WorkloadKind.CGEMV: ("recompute:cgemv:complex128", _verify_cgemv),
    WorkloadKind.TENSOR_OP: ("recompute:tensor_op:float64", _verify_tensor_op),
    WorkloadKind.FOLD: ("recompute:fold:inverse_decode", _verify_fold),
}


def verify_workload_result(
    workload: Workload, result: WorkloadResult
) -> dict[str, Any]:
    """Independently recompute ``result`` for verifiable workload kinds.

    Never mutates inputs and never consults the executing adapter.  The
    returned dict is receipt-safe and always carries:

      * ``recomputed`` — did an independent recompute actually run
      * ``verifier``   — oracle identity (``none`` when not applicable)
      * ``verdict``    — ``match`` | ``mismatch`` | ``unverifiable_kind``
                         | ``out_of_verify_bound`` | ``skipped_not_ok``
      * ``detail``     — mismatch/bound description when not ``match``
      * ``tolerance``  — recorded when any float comparison ran
    """
    try:
        kind = workload.kind if isinstance(workload.kind, WorkloadKind) else WorkloadKind(str(workload.kind))
    except ValueError:
        return {
            "recomputed": False,
            "verifier": "none",
            "verdict": "unverifiable_kind",
            "detail": f"unknown workload kind {workload.kind!r}",
        }
    entry = _VERIFIERS.get(kind)
    if entry is None:
        return {
            "recomputed": False,
            "verifier": "none",
            "verdict": "unverifiable_kind",
            "detail": f"no independent oracle for kind={kind.value}",
        }
    if result.status != "ok":
        return {
            "recomputed": False,
            "verifier": entry[0],
            "verdict": "skipped_not_ok",
            "detail": f"result status {result.status!r}",
        }
    name, fn = entry
    report: dict[str, Any] = {"recomputed": True, "verifier": name}
    if kind in {
        WorkloadKind.PHI_TRANSFORM,
        WorkloadKind.PISOT_TRANSFORM,
        WorkloadKind.CGEMV,
        WorkloadKind.TENSOR_OP,
    }:
        report["tolerance"] = {"rtol": FLOAT_RTOL, "atol": FLOAT_ATOL}
    try:
        problems = fn(workload.input or {}, result.output or {})
    except _OutOfBound as exc:
        return {
            "recomputed": False,
            "verifier": name,
            "verdict": "out_of_verify_bound",
            "detail": str(exc),
        }
    except _Unverifiable as exc:
        return {
            "recomputed": False,
            "verifier": name,
            "verdict": "unverifiable_kind",
            "detail": str(exc),
        }
    except Exception as exc:  # malformed output or verifier fault: not a match
        return {
            "recomputed": True,
            "verifier": name,
            "verdict": "mismatch",
            "detail": f"verifier could not recompute/compare: {exc}",
        }
    if problems:
        report["verdict"] = "mismatch"
        report["detail"] = "; ".join(problems[:8])
    else:
        report["verdict"] = "match"
    return report


__all__ = [
    "VERIFY_MAX_SCAN_NONCES",
    "VERIFY_MAX_TENSOR_ELEMS",
    "VERIFY_MAX_CGEMV_ELEMS",
    "FLOAT_RTOL",
    "FLOAT_ATOL",
    "verify_workload_result",
]
