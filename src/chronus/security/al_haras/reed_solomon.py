"""Reed-Solomon error correction over the prime field GF(257).

This is the implemented mechanism behind AL HARAS "self-healing" of execution
traces: a trace is protected with parity symbols, and corrupted symbols are
located and corrected in place from that redundancy, without restoring a
checkpoint. The notes describe this step with Donaldson-Seiberg-Witten /
instanton vocabulary; that vocabulary is a naming metaphor, and the mechanism
is the classical code below.

Code: systematic RS(n, k) with evaluation points 1..n in GF(257). It corrects up
to t = floor((n - k) / 2) symbol errors per block. Beyond that bound, some
patterns are undetected or decode to another codeword. The ``decode_blocks``
``ok`` flag confirms codeword validity; ``heal_blocks`` also verifies the
reconstructed bytes against the expected SHA-256 digest. All arithmetic is
exact integer arithmetic modulo 257.

Two decoders implement the same code:

* ``decode_block``: Berlekamp-Welch on one block in pure Python. It is the
  reference and is kept for cross-checking.
* ``heal`` / ``heal_blocks``: a batched syndrome decoder in numpy (int64,
  exact). Syndromes ``S = R @ H`` over the parity-check matrix of the
  generalised RS code are computed for every block at once; blocks with zero
  syndromes are accepted without decoding. Damaged blocks are decoded together
  with a vectorised Berlekamp-Massey, a Chien search over the 48 evaluation
  points and Forney's formula, and every corrected word is re-checked to have
  zero syndromes. Within the bound both decoders return the same unique
  codeword (the test suite cross-checks them on random faults, including
  faults beyond the bound).
"""

import hashlib
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

P = 257
DEFAULT_N = 48
DEFAULT_K = 32
MAX_TRACE_BYTES = 1 << 20
# Bound expanded decoder work to that of a maximum-size default trace.
_MAX_DECODE_SYMBOLS = ((MAX_TRACE_BYTES + DEFAULT_K - 1) // DEFAULT_K) * DEFAULT_N


class ReedSolomonError(ValueError):
    """Invalid parameters or envelope."""


def _inv(a: int) -> int:
    a %= P
    if a == 0:
        raise ZeroDivisionError("zero has no inverse in GF(257)")
    return pow(a, P - 2, P)


def _check_params(n: int, k: int) -> tuple[int, int]:
    if (not all(isinstance(v, (int, np.integer)) and not isinstance(v, bool) for v in (n, k))
            or not (1 <= k < n <= P - 1)):
        raise ReedSolomonError("require integer dimensions with 1 <= k < n <= 256")
    return int(n), int(k)


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
    n, k = _check_params(n, k)
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
    n, k = _check_params(n, k)
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


@lru_cache(maxsize=8)
def _tables(n: int, k: int) -> Dict[str, np.ndarray]:
    """Exact int64 tables for the batched encoder and syndrome decoder."""
    xs = list(range(1, n + 1))
    # Column multipliers of the dual (parity-check) GRS code.
    v = []
    for i, xi in enumerate(xs):
        den = 1
        for m, xm in enumerate(xs):
            if m != i:
                den = den * (xi - xm) % P
        v.append(_inv(den))
    r = n - k
    inv_table = np.zeros(P, dtype=np.int64)
    inv_table[1:] = [pow(a, P - 2, P) for a in range(1, P)]
    x_arr = np.array(xs, dtype=np.int64)
    x_inv = inv_table[x_arr]
    h = np.array([[v[i] * pow(xs[i], j, P) % P for j in range(r)] for i in range(n)], dtype=np.int64)
    # z_pows[d, i] = x_i^{-d}, d = 0..r, for evaluating polynomials at 1/x_i.
    z_pows = np.array([[pow(int(x_inv[i]), d, P) for i in range(n)] for d in range(r + 1)], dtype=np.int64)
    return {
        "weights": np.array(_parity_weights(n, k), dtype=np.int64),  # (r, k)
        "h": h,  # (n, r)
        "z_pows": z_pows,  # (r + 1, n)
        "x": x_arr,
        "v_inv": inv_table[np.array(v, dtype=np.int64)],
        "inv": inv_table,
    }


def _data_blocks(trace: bytes, k: int) -> np.ndarray:
    """``trace`` as a (blocks, k) int64 array, zero-padded in the last block."""
    blocks = (len(trace) + k - 1) // k
    buf = np.zeros(blocks * k, dtype=np.int64)
    if trace:
        buf[: len(trace)] = np.frombuffer(trace, dtype=np.uint8)
    return buf.reshape(blocks, k)


def encode_blocks(trace: bytes, n: int = DEFAULT_N, k: int = DEFAULT_K) -> np.ndarray:
    """Parity for every block of ``trace`` as a (blocks, n - k) array; same values as ``encode_block``."""
    n, k = _check_params(n, k)
    if len(trace) > MAX_TRACE_BYTES:
        raise ReedSolomonError("trace exceeds the supported size")
    data = _data_blocks(trace, k)
    if not len(data):
        return np.zeros((0, n - k), dtype=np.int64)
    return (data @ _tables(n, k)["weights"].T) % P


def _check_decode_size(blocks: int, n: int) -> None:
    if blocks * n > _MAX_DECODE_SYMBOLS:
        raise ReedSolomonError("expanded words exceed the supported decoder size")


def _repair_block_count(length: int, n: int, k: int) -> int:
    if length > MAX_TRACE_BYTES:
        raise ReedSolomonError("trace exceeds the supported size")
    blocks = (length + k - 1) // k
    _check_decode_size(blocks, n)
    return blocks


def _field_symbols(values: np.ndarray) -> np.ndarray:
    """Validate symbols without letting a cast truncate or wrap them."""
    if values.dtype.kind not in "iuf":
        raise ReedSolomonError("symbols must be integers in GF(257)")
    if values.size and (values.min() < 0 or values.max() >= P
                        or (values.dtype.kind == "f" and not (values == np.floor(values)).all())):
        raise ReedSolomonError("symbols must be integers in GF(257)")
    return values.astype(np.int64, copy=False)


def decode_blocks(words: np.ndarray, n: int, k: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Batched syndrome decoding of received words (blocks, n) with values 0..256.

    Returns ``(corrected, ok, damaged)``: corrected words, a per-block flag that
    the word is a codeword (as received or after correcting at most t symbols),
    and a per-block flag that the received word was not a codeword.
    """
    n, k = _check_params(n, k)
    words = np.asarray(words)
    if words.ndim != 2 or words.shape[1] != n:
        raise ReedSolomonError("words must have shape (blocks, n)")
    _check_decode_size(words.shape[0], n)
    words = _field_symbols(words)
    tab = _tables(n, k)
    r = n - k
    t = r // 2
    syn = (words @ tab["h"]) % P
    damaged = syn.any(axis=1)
    corrected = words.copy()
    ok = ~damaged
    idx = np.nonzero(damaged)[0]
    if not len(idx):
        return corrected, ok, damaged
    s = syn[idx]
    inv = tab["inv"]
    d_count = len(idx)
    width = r + 1
    # Vectorised Berlekamp-Massey: C is the error locator, B the previous one.
    c = np.zeros((d_count, width), dtype=np.int64)
    b = np.zeros((d_count, width), dtype=np.int64)
    c[:, 0] = 1
    b[:, 0] = 1
    length = np.zeros(d_count, dtype=np.int64)
    shift = np.ones(d_count, dtype=np.int64)
    last_d = np.ones(d_count, dtype=np.int64)
    cols = np.arange(width)
    for step in range(r):
        disc = (c[:, : step + 1] * s[:, step::-1]).sum(axis=1) % P
        nz = disc != 0
        src = cols[None, :] - shift[:, None]
        valid = src >= 0
        shifted_b = np.where(valid, np.take_along_axis(b, np.clip(src, 0, width - 1), axis=1), 0)
        coef = disc * inv[last_d] % P
        new_c = (c - coef[:, None] * shifted_b) % P
        grow = nz & (2 * length <= step)
        b = np.where(grow[:, None], c, b)
        last_d = np.where(grow, disc, last_d)
        length = np.where(grow, step + 1 - length, length)
        shift = np.where(grow, 1, shift + 1)
        c = np.where(nz[:, None], new_c, c)
    within = length <= t
    # Chien search: roots of the locator at 1/x_i mark the error positions.
    lam_at = (c @ tab["z_pows"]) % P  # (d, n)
    roots = lam_at == 0
    within &= roots.sum(axis=1) == length
    # Forney: y_i = -x_i * Omega(1/x_i) / Lambda'(1/x_i);  e_i = y_i / v_i.
    omega = np.zeros((d_count, r), dtype=np.int64)
    for j in range(r):
        omega[:, j] = (c[:, : j + 1] * s[:, j::-1]).sum(axis=1) % P
    omega_at = (omega @ tab["z_pows"][:r]) % P
    deriv = (c[:, 1:] * np.arange(1, width)[None, :]) % P  # coefficients of Lambda'
    deriv_at = (deriv @ tab["z_pows"][:r]) % P
    within &= ~(roots & (deriv_at == 0)).any(axis=1)
    y = (-tab["x"][None, :] * omega_at % P) * inv[deriv_at] % P
    err = np.where(roots, y * tab["v_inv"][None, :] % P, 0)
    fixed = (words[idx] - err) % P
    within &= ~((fixed @ tab["h"]) % P).any(axis=1)  # exactness guard: must be a codeword
    good = idx[within]
    corrected[good] = fixed[within]
    ok[good] = True
    return corrected, ok, damaged


def protect(trace: bytes, n: int = DEFAULT_N, k: int = DEFAULT_K) -> Dict[str, Any]:
    """Build a protection envelope (parity per block plus the SHA-256 of the trace)."""
    parity = encode_blocks(trace, n, k)
    return {
        "scheme": "reed-solomon-gf257-systematic",
        "n": n,
        "k": k,
        "correctable_symbols_per_block": (n - k) // 2,
        "length": len(trace),
        "blocks": len(parity),
        "parity": parity.tolist(),
        "sha256": hashlib.sha256(trace).hexdigest(),
    }


def heal_blocks(received: bytes, parity: np.ndarray, n: int, k: int, expected_sha256: str) -> Dict[str, Any]:
    """Batched repair of ``received`` from a (blocks, n - k) parity array."""
    n, k = _check_params(n, k)
    length = len(received)
    blocks = _repair_block_count(length, n, k)
    parity = np.asarray(parity)
    if parity.shape != (blocks, n - k):
        raise ReedSolomonError("parity block count does not match the envelope")
    parity = _field_symbols(parity)
    data = _data_blocks(received, k)
    words = np.concatenate([data, parity], axis=1) if blocks else np.zeros((0, n), dtype=np.int64)
    corrected, ok, damaged = decode_blocks(words, n, k)
    out_data = corrected[:, :k]
    # Padding must stay zero and data symbols must be bytes, else the block is rejected.
    pad = blocks * k - length
    bad_values = (out_data > 255).any(axis=1)
    if pad and blocks:
        bad_values[-1] |= bool(out_data[-1, k - pad:].any())
    accepted = ok & ~bad_values
    final = np.where(accepted[:, None], out_data, data)
    flat = final.reshape(-1)[:length].astype(np.uint8)
    repaired = flat.tobytes()
    changed = (final != data).reshape(-1)[:length]
    corrected_positions = np.nonzero(changed)[0].tolist()
    uncorrectable_blocks = np.nonzero(~accepted)[0].tolist()
    digest = hashlib.sha256(repaired).hexdigest()
    return {
        "repaired": repaired,
        "corrected_data_positions": corrected_positions,
        "corrected_blocks": int((accepted & damaged).sum()),
        "uncorrectable_blocks": uncorrectable_blocks,
        "sha256_after_repair": digest,
        "integrity_verified": digest == expected_sha256 and not uncorrectable_blocks,
    }


def heal(received: bytes, envelope: Dict[str, Any], received_parity: Optional[List[List[int]]] = None) -> Dict[str, Any]:
    """Detect and correct corrupted symbols in ``received`` using ``envelope``."""
    n, k = int(envelope["n"]), int(envelope["k"])
    n, k = _check_params(n, k)
    length = int(envelope["length"])
    parity = received_parity if received_parity is not None else envelope["parity"]
    if len(received) != length:
        raise ReedSolomonError("received trace length differs from the protected length")
    blocks = _repair_block_count(length, n, k)
    if len(parity) != blocks or len(parity) != int(envelope["blocks"]):
        raise ReedSolomonError("parity block count does not match the envelope")
    # Same acceptance as the reference path (``int(v) % P``); arbitrary-size
    # integers are reduced in Python before they reach int64 arrays.
    rows = []
    for row in parity:
        reduced = [int(v) % P for v in row]
        if len(reduced) != n - k:
            raise ReedSolomonError("parity block has the wrong number of symbols")
        rows.append(reduced)
    parity_arr = np.array(rows, dtype=np.int64) if rows else np.zeros((0, n - k), dtype=np.int64)
    return heal_blocks(received, parity_arr, n, k, envelope["sha256"])


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
