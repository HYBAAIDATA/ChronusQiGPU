"""Reed-Solomon error correction over the prime field GF(257).

This is the implemented mechanism behind AL HARAS "self-healing" of execution
traces: a trace is protected with parity symbols, and corrupted symbols are
located and corrected in place from that redundancy, without restoring a
checkpoint. The notes describe this step with Donaldson-Seiberg-Witten /
instanton vocabulary; that vocabulary is a naming metaphor, and the mechanism
is the classical code below.

Code: systematic RS(n, k) with evaluation points 1..n in GF(257). It corrects up
to t = floor((n - k) / 2) symbol errors per block (Berlekamp-Welch decoding)
and detects heavier corruption as uncorrectable. All arithmetic is exact
integer arithmetic modulo 257.
"""

import hashlib
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

P = 257
DEFAULT_N = 48
DEFAULT_K = 32
MAX_TRACE_BYTES = 1 << 20


class ReedSolomonError(ValueError):
    """Invalid parameters or envelope."""


def _inv(a: int) -> int:
    a %= P
    if a == 0:
        raise ZeroDivisionError("zero has no inverse in GF(257)")
    return pow(a, P - 2, P)


def _check_params(n: int, k: int) -> None:
    if not (1 <= k < n <= P - 1):
        raise ReedSolomonError("require 1 <= k < n <= 256")


@lru_cache(maxsize=32)
def _parity_weights(n: int, k: int) -> Tuple[Tuple[int, ...], ...]:
    """W[j][i] = L_i(x_{k+j}) for Lagrange basis on points 1..k."""
    xs = list(range(1, k + 1))
    weights = []
    for j in range(n - k):
        x = k + 1 + j
        row = []
        for i, xi in enumerate(xs):
            num, den = 1, 1
            for m, xm in enumerate(xs):
                if m != i:
                    num = num * (x - xm) % P
                    den = den * (xi - xm) % P
            row.append(num * _inv(den) % P)
        weights.append(tuple(row))
    return tuple(weights)


def encode_block(data: Sequence[int], n: int, k: int) -> List[int]:
    """Parity symbols for one block of ``k`` data symbols (values 0..256)."""
    _check_params(n, k)
    if len(data) != k:
        raise ReedSolomonError("block must contain exactly k symbols")
    return [sum(w * d for w, d in zip(row, data)) % P for row in _parity_weights(n, k)]


def _poly_eval(coeffs: Sequence[int], x: int) -> int:
    acc = 0
    for c in reversed(coeffs):
        acc = (acc * x + c) % P
    return acc


def _poly_divmod(num: List[int], den: List[int]) -> Tuple[List[int], List[int]]:
    num = list(num)
    while den and den[-1] == 0:
        den.pop()
    if not den:
        raise ZeroDivisionError("polynomial division by zero")
    inv_lead = _inv(den[-1])
    quot = [0] * max(0, len(num) - len(den) + 1)
    for i in range(len(num) - len(den), -1, -1):
        coef = num[i + len(den) - 1] * inv_lead % P
        quot[i] = coef
        if coef:
            for j, d in enumerate(den):
                num[i + j] = (num[i + j] - coef * d) % P
    rem = num[: len(den) - 1]
    return quot, rem


def _solve_mod_p(rows: List[List[int]], rhs: List[int], ncols: int) -> Optional[List[int]]:
    aug = [list(r) + [b] for r, b in zip(rows, rhs)]
    pivots = []
    r = 0
    for c in range(ncols):
        pivot = next((i for i in range(r, len(aug)) if aug[i][c] % P), None)
        if pivot is None:
            continue
        aug[r], aug[pivot] = aug[pivot], aug[r]
        inv = _inv(aug[r][c])
        aug[r] = [x * inv % P for x in aug[r]]
        for i in range(len(aug)):
            if i != r and aug[i][c] % P:
                f = aug[i][c]
                aug[i] = [(x - f * y) % P for x, y in zip(aug[i], aug[r])]
        pivots.append(c)
        r += 1
    if any(aug[i][ncols] % P for i in range(r, len(aug))):
        return None
    x = [0] * ncols
    for i, pc in enumerate(pivots):
        x[pc] = aug[i][ncols]
    return x


def decode_block(codeword: Sequence[int], n: int, k: int) -> Dict[str, Any]:
    """Berlekamp-Welch decoding of one received block (data + parity)."""
    _check_params(n, k)
    if len(codeword) != n:
        raise ReedSolomonError("codeword must contain n symbols")
    received = [int(v) % P for v in codeword]
    data, parity = received[:k], received[k:]
    if encode_block(data, n, k) == parity:
        return {"status": "clean", "data": data, "error_positions": []}
    t = (n - k) // 2
    xs = list(range(1, n + 1))
    # unknowns: q_0..q_{k+t-1}, e_0..e_{t-1};  Q(x_i) - r_i E'(x_i) = r_i x_i^t
    ncols = (k + t) + t
    rows, rhs = [], []
    for x, r in zip(xs, received):
        powers = [pow(x, j, P) for j in range(k + t)]
        rows.append(powers + [(-r * powers[j]) % P for j in range(t)])
        rhs.append(r * pow(x, t, P) % P)
    sol = _solve_mod_p(rows, rhs, ncols)
    if sol is None:
        return {"status": "uncorrectable", "data": data, "error_positions": []}
    q_poly = sol[: k + t]
    e_poly = sol[k + t:] + [1]
    msg, rem = _poly_divmod(q_poly, e_poly)
    if any(rem):
        return {"status": "uncorrectable", "data": data, "error_positions": []}
    msg = (msg + [0] * k)[:k]
    corrected = [_poly_eval(msg, x) for x in xs]
    errors = [i for i in range(n) if corrected[i] != received[i]]
    if len(errors) > t:
        return {"status": "uncorrectable", "data": data, "error_positions": []}
    return {"status": "corrected", "data": corrected[:k], "error_positions": errors}


def protect(trace: bytes, n: int = DEFAULT_N, k: int = DEFAULT_K) -> Dict[str, Any]:
    """Build a protection envelope (parity per block plus the SHA-256 of the trace)."""
    _check_params(n, k)
    if len(trace) > MAX_TRACE_BYTES:
        raise ReedSolomonError("trace exceeds the supported size")
    parity: List[List[int]] = []
    for start in range(0, len(trace), k):
        block = list(trace[start:start + k])
        block += [0] * (k - len(block))
        parity.append(encode_block(block, n, k))
    return {
        "scheme": "reed-solomon-gf257-systematic",
        "n": n,
        "k": k,
        "correctable_symbols_per_block": (n - k) // 2,
        "length": len(trace),
        "blocks": len(parity),
        "parity": parity,
        "sha256": hashlib.sha256(trace).hexdigest(),
    }


def heal(received: bytes, envelope: Dict[str, Any], received_parity: Optional[List[List[int]]] = None) -> Dict[str, Any]:
    """Detect and correct corrupted symbols in ``received`` using ``envelope``."""
    n, k = int(envelope["n"]), int(envelope["k"])
    _check_params(n, k)
    length = int(envelope["length"])
    parity = received_parity if received_parity is not None else envelope["parity"]
    if len(received) != length:
        raise ReedSolomonError("received trace length differs from the protected length")
    if len(parity) != int(envelope["blocks"]):
        raise ReedSolomonError("parity block count does not match the envelope")
    out = bytearray()
    corrected_positions: List[int] = []
    corrected_blocks = 0
    uncorrectable_blocks: List[int] = []
    for b, start in enumerate(range(0, length, k)):
        chunk = list(received[start:start + k])
        pad = k - len(chunk)
        word = chunk + [0] * pad + [int(v) for v in parity[b]]
        res = decode_block(word, n, k)
        if res["status"] == "uncorrectable":
            uncorrectable_blocks.append(b)
            out.extend(bytes(chunk))
            continue
        data = res["data"]
        if any(v > 255 for v in data[: k - pad]) or any(data[k - pad:]):
            uncorrectable_blocks.append(b)
            out.extend(bytes(chunk))
            continue
        if res["status"] == "corrected":
            corrected_blocks += 1
            corrected_positions.extend(start + i for i in res["error_positions"] if i < k - pad)
        out.extend(bytes(data[: k - pad]))
    repaired = bytes(out)
    digest = hashlib.sha256(repaired).hexdigest()
    return {
        "repaired": repaired,
        "corrected_data_positions": corrected_positions,
        "corrected_blocks": corrected_blocks,
        "uncorrectable_blocks": uncorrectable_blocks,
        "sha256_after_repair": digest,
        "integrity_verified": digest == envelope["sha256"] and not uncorrectable_blocks,
    }


def deterministic_fault_positions(trace: bytes, count: int) -> List[int]:
    """Distinct byte positions derived from SHA-256(trace) for fault-injection drills."""
    if not trace or count <= 0:
        return []
    positions: List[int] = []
    counter = 0
    while len(positions) < min(count, len(trace)):
        h = hashlib.sha256(trace + counter.to_bytes(4, "big")).digest()
        pos = int.from_bytes(h[:4], "big") % len(trace)
        if pos not in positions:
            positions.append(pos)
        counter += 1
    return positions


def inject_faults(trace: bytes, positions: Sequence[int]) -> bytes:
    """Flip bits at the given positions (each byte changes; value XOR 0x5A)."""
    corrupted = bytearray(trace)
    for pos in positions:
        if not 0 <= pos < len(corrupted):
            raise ReedSolomonError("fault position outside the trace")
        corrupted[pos] ^= 0x5A
    return bytes(corrupted)
