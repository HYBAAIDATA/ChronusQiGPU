"""Structural verification of PYTHIA substrate receipts.

Self-contained exact-integer math: Fibonacci/Lucas fast doubling, the
Cassini identity, Zeckendorf decomposition, and the non-adjacency mask
legality used by ``ZeckendorfCertificate`` (``ZECK-`` tokens).

This is a *structural* verifier: it proves a receipt's internal invariants.
It does not prove custody, provenance, or that the receipt was produced by
a specific node — those require the custody chain in hyba_db/THESEUS.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

__all__ = [
    "fibonacci", "lucas", "cassini_holds", "zeckendorf",
    "zeckendorf_legal", "verify_receipt",
]

_TOKEN_RE = re.compile(r"^ZECK-[0-9a-fA-F]{16}$")


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


def _check(name: str, ok: bool, detail: str = "") -> Dict[str, Any]:
    return {"check": name, "passed": bool(ok), "detail": detail}


def verify_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a receipt's internal invariants. Returns a structured verdict.

    Recognised fields (all optional; absent fields are reported, not failed):
      token_hex            — "ZECK-" + 16 hex chars
      non_adjacent_mask    — int; must satisfy mask & (mask << 1) == 0
      zeckendorf_value     — int; receipt may pair it with zeckendorf_indices
      zeckendorf_indices   — list[int]; must be legal and sum to the value
      cassini_ledger       — rows [i, F_{i-1}, F_i, F_{i+1}, parity]
      lucas_ladder         — mapping {index: L_index}
    """
    if not isinstance(receipt, dict):
        return {"schema": "pythia.consumer.verdict/1", "verdict": "fail",
                "checks": [_check("receipt_shape", False, "receipt must be a JSON object")]}
    checks: List[Dict[str, Any]] = []

    token = receipt.get("token_hex") or receipt.get("token")
    if token is not None:
        checks.append(_check("token_format", isinstance(token, str) and bool(_TOKEN_RE.match(token)),
                             "expected 'ZECK-' + 16 hex chars"))

    mask = receipt.get("non_adjacent_mask")
    if mask is not None:
        ok = isinstance(mask, int) and mask >= 0 and (mask & (mask << 1)) == 0
        checks.append(_check("non_adjacent_mask", ok, "mask & (mask << 1) == 0 required"))

    indices, value = receipt.get("zeckendorf_indices"), receipt.get("zeckendorf_value")
    if indices is not None:
        legal = isinstance(indices, list) and all(isinstance(i, int) and i >= 2 for i in indices) \
            and zeckendorf_legal(indices)
        checks.append(_check("zeckendorf_indices", legal, "non-adjacent Fibonacci indices required"))
        if legal and value is not None:
            checks.append(_check("zeckendorf_value", sum(fibonacci(i) for i in indices) == value,
                                 "indices must sum to the declared value"))
    elif value is not None:
        if isinstance(value, int) and value > 0:
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

    run = [c for c in checks if not c["passed"]]
    verdict = "pass" if checks and not run else ("incomplete" if not run else "fail")
    return {
        "schema": "pythia.consumer.verdict/1",
        "verdict": verdict,
        "verification_level": "structural",
        "custody_proof": False,
        "checks": checks,
    }
