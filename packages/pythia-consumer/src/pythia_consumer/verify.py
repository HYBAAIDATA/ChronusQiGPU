"""Structural + canonical verification of PYTHIA substrate receipts.

Contract v2 (hardened):

REQUIRED fields — a "pass" verdict is impossible without all of them
present, correctly typed, and in range:
  token_hex          str  "ZECK-" + 16 hex chars (canonical form: uppercase)
  non_adjacent_mask  int  0..2047 (11-bit decoupling mask)
  canonical_int      int  0..2^64-1
  coordinate_masks   list[int] of exactly 11 entries, each a producible
                      Zeckendorf mask: bits only in [2,24], non-adjacent
  context_id         str  (empty string permitted)

CANONICAL BINDING — independently re-derives the 64-bit accumulator from
coordinate_masks + context_id using the documented φ¹⁵/ZECK algorithm
(see PROVENANCE.md): acc = fold of (mask_i ^ PRIME_BUCKETS[max_k_i]),
then a context-mix step, then token == f"ZECK-{acc:016X}". Passing proves
the receipt is internally consistent under the published algorithm. It
does NOT authenticate the producer — anyone can compute the same fold.

OPTIONAL fields checked when present: "token" alias consistency,
cassini_ledger rows, lucas_ladder entries, zeckendorf_indices/value.
Unknown fields are ignored (forward compatibility).

PROVENANCE AUTHENTICATION: unsupported. The iGPU sign_certificate/
verify_signature scheme is symmetric-HMAC with a caller-supplied secret
and no key provisioning — it cannot distinguish producer from key-holder
inside a distributed consumer binary. Establishing provenance requires
an asymmetric signature or a documented key-distribution trust model.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

__all__ = [
    "fibonacci", "lucas", "cassini_holds", "zeckendorf",
    "zeckendorf_legal", "canonical_accumulator", "verify_receipt",
]

_TOKEN_RE = re.compile(r"^ZECK-[0-9a-fA-F]{16}$")
_MASK64 = 0xFFFFFFFFFFFFFFFF
_PRIME_BUCKETS = (
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41,
    43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
)
_DIMS = 11


def fibonacci(n: int) -> int:
    """Exact F_n via fast doubling (F_0=0, F_1=1)."""
    if n < 0:
        raise ValueError("fibonacci index must be non-negative")

    def pair(k: int) -> tuple[int, int]:
        if k == 0:
            return 0, 1
        a, b = pair(k >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        return (d, c + d) if k & 1 else (c, d)

    return pair(n)[0]


def lucas(n: int) -> int:
    """Exact L_n via fast doubling (L_0=2, L_1=1)."""
    if n < 0:
        raise ValueError("lucas index must be non-negative")
    if n == 0:
        return 2
    return fibonacci(n - 1) + fibonacci(n + 1)


def cassini_holds(n: int) -> bool:
    """L_n² - 5·F_n² == 4·(-1)^n."""
    if n < 0:
        raise ValueError("cassini index must be non-negative")
    return lucas(n) ** 2 - 5 * fibonacci(n) ** 2 == 4 * ((-1) ** n)


def zeckendorf(n: int) -> List[int]:
    """Greedy non-consecutive Fibonacci indices (k >= 2) summing to n."""
    if n <= 0:
        raise ValueError("zeckendorf requires a positive integer")
    indices, i = [], 2
    while fibonacci(i + 1) <= n:
        i += 1
    while n:
        while fibonacci(i) > n:
            i -= 1
        indices.append(i)
        n -= fibonacci(i)
        i -= 1
    return indices


def zeckendorf_legal(indices: List[int]) -> bool:
    """Non-adjacency: no two consecutive indices may both appear."""
    s = sorted(indices)
    return len(set(indices)) == len(indices) and all(
        s[k + 1] - s[k] >= 2 for k in range(len(s) - 1)
    )


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _check(name: str, ok: bool, detail: str = "") -> Dict[str, Any]:
    return {"check": name, "result": "pass" if ok else "fail",
            "passed": bool(ok), "detail": detail}


def _skipped(name: str, detail: str) -> Dict[str, Any]:
    return {"check": name, "result": "skipped", "passed": False, "detail": detail}


def _mask_max_k(mask: int) -> int:
    """Highest set bit of a Zeckendorf coordinate mask (0 for empty masks)."""
    return mask.bit_length() - 1 if mask else 0


def _mask_producible(mask: int) -> bool:
    """A producible mask uses Fibonacci-index bits in [2,24] and is non-adjacent."""
    return (mask >> 25) == 0 and (mask & 0b11) == 0 and (mask & (mask << 1)) == 0


def canonical_accumulator(coordinate_masks: List[int], context_id: str) -> int:
    """Independent re-derivation of the certificate's canonical 64-bit value.

    Mirrors the documented producer fold: per coordinate, xor the Zeckendorf
    mask with PRIME_BUCKETS[max_k] where max_k is the mask's highest set bit;
    then mix SHA256(context_id)[:8] when a context is present.
    """
    acc = 0
    for m in coordinate_masks:
        mk = _mask_max_k(m)
        if mk >= len(_PRIME_BUCKETS):
            raise ValueError(f"coordinate mask {m} exceeds the 25 prime buckets")
        acc = ((acc * 31) + (m ^ _PRIME_BUCKETS[mk])) & _MASK64
    if context_id:
        ctx = int.from_bytes(hashlib.sha256(context_id.encode("utf-8")).digest()[:8], "big")
        acc = ((acc * 31) + ctx) & _MASK64
    return acc


_REQUIRED_INT_BOUNDS = {
    "non_adjacent_mask": (0, 0x7FF),
    "canonical_int": (0, _MASK64),
}


def verify_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a receipt against contract v2. Returns a structured verdict.

    verdict "pass" requires every required field present/valid AND every
    executed contract check passed. Checks carry result
    pass|fail|skipped — a skipped check never counts as evidence.
    """
    checks: List[Dict[str, Any]] = []
    verdict = {"schema": "pythia.consumer.verdict/2", "checks": checks}
    if not isinstance(receipt, dict):
        checks.append(_check("receipt_shape", False, "receipt must be a JSON object"))
        return _finish(verdict)

    token = receipt.get("token_hex")
    mask = receipt.get("non_adjacent_mask")
    canonical = receipt.get("canonical_int")
    coord_masks = receipt.get("coordinate_masks")
    context_id = receipt.get("context_id")

    # --- required fields ---------------------------------------------------
    req_ok = True

    ok = isinstance(token, str)
    checks.append(_check("required:token_hex", ok, "string required"))
    req_ok &= ok

    for field, (lo, hi) in _REQUIRED_INT_BOUNDS.items():
        v = receipt.get(field)
        ok = _is_int(v) and lo <= v <= hi
        checks.append(_check(f"required:{field}", ok, f"int in [{lo},{hi}] required"))
        req_ok &= ok

    ok = isinstance(coord_masks, list) and len(coord_masks) == _DIMS \
        and all(_is_int(m) for m in coord_masks)
    checks.append(_check("required:coordinate_masks", ok,
                         f"list of exactly {_DIMS} ints required"))
    req_ok &= ok

    ok = isinstance(context_id, str)
    checks.append(_check("required:context_id", ok, "string required"))
    req_ok &= ok

    # --- contract checks (skipped, not passed, when prerequisites fail) ------
    if req_ok:
        checks.append(_check("token_format", bool(_TOKEN_RE.match(token)),
                             "expected 'ZECK-' + 16 hex chars"))
        checks.append(_check("non_adjacent_mask", (mask & (mask << 1)) == 0,
                             "mask & (mask << 1) == 0 required"))
        checks.append(_check(
            "coordinate_masks_producible",
            all(_mask_producible(m) for m in coord_masks),
            "bits restricted to [2,24], non-adjacent, per coordinate"))
        checks.append(_check(
            "token_canonical_binding",
            token == f"ZECK-{canonical:016X}",
            "token must equal canonical_int as ZECK-%016X"))
        try:
            derived = canonical_accumulator(coord_masks, context_id)
            checks.append(_check(
                "canonical_derivation", derived == canonical,
                "coordinate_masks + context_id fold must equal canonical_int"))
        except ValueError as exc:
            checks.append(_check("canonical_derivation", False, str(exc)))
    else:
        for name in ("token_format", "non_adjacent_mask", "coordinate_masks_producible",
                     "token_canonical_binding", "canonical_derivation"):
            checks.append(_skipped(name, "required-field prerequisite failed"))

    # --- optional fields ---------------------------------------------------
    alias = receipt.get("token")
    if req_ok and alias is not None:
        checks.append(_check("token_alias_consistent", alias == token,
                             "'token' must equal 'token_hex' when both present"))

    indices, value = receipt.get("zeckendorf_indices"), receipt.get("zeckendorf_value")
    if indices is not None:
        legal = isinstance(indices, list) and all(_is_int(i) and i >= 2 for i in indices) \
            and zeckendorf_legal(indices)
        checks.append(_check("zeckendorf_indices", legal, "non-adjacent Fibonacci indices required"))
        if legal and value is not None:
            checks.append(_check("zeckendorf_value", sum(fibonacci(i) for i in indices) == value,
                                 "indices must sum to the declared value"))
    elif value is not None:
        if _is_int(value) and value > 0:
            checks.append(_check("zeckendorf_value", True,
                                 f"decomposition {zeckendorf(value)} recomputed"))
        else:
            checks.append(_check("zeckendorf_value", False, "positive integer required"))

    for idx, row in enumerate(receipt.get("cassini_ledger") or []):
        try:
            i, fp, fi, fn, parity = row
            ok = (fibonacci(i - 1) == fp and fibonacci(i) == fi and fibonacci(i + 1) == fn
                  and parity == (-1) ** i and fp * fn - fi * fi == parity)
            detail = ""
        except Exception as exc:
            ok, detail = False, f"malformed row: {exc}"
        checks.append(_check(f"cassini_ledger[{idx}]",
                             ok, detail or "F_{i-1}·F_{i+1} − F_i² == (-1)^i"))

    ladder = receipt.get("lucas_ladder")
    if ladder is not None:
        for k, v in (ladder.items() if isinstance(ladder, dict) else []):
            try:
                checks.append(_check(f"lucas_ladder[{k}]", lucas(int(k)) == int(v), ""))
            except Exception as exc:
                checks.append(_check(f"lucas_ladder[{k}]", False, str(exc)))

    return _finish(verdict)


def _finish(verdict: Dict[str, Any]) -> Dict[str, Any]:
    checks = verdict["checks"]
    passed_all = bool(checks) and all(c["result"] == "pass" for c in checks)
    binding = any(c["check"] == "canonical_derivation" and c["result"] == "pass"
                  for c in checks)
    verdict.update({
        "verdict": "pass" if passed_all else "fail",
        "levels": {
            "structural": passed_all,
            "canonical_binding": bool(binding and passed_all),
            "provenance_authentication": "unsupported",
        },
        "verification_level": "canonical_binding" if binding and passed_all else "structural",
        "custody_proof": False,
    })
    return verdict
