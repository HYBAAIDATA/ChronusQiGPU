"""
TURING CORE & PYTHIA MINING ENGINE (Zero External Dependencies)
==============================================================
Internal Substrate Mining Engine (PYTHIA) and TURING Quantum Core.
Used strictly for internal bootstrapping, self-verification, and substrate validation.
Decoupled from commercial enterprise APIs and AL HARAS security layer.
"""

import hashlib
import math
import struct
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

# =====================================================================
# 1. EXACT PHI-ALGEBRAIC & SYMPLECTIC CORE
# =====================================================================

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
PSI: float = (1.0 - math.sqrt(5.0)) / 2.0
INV_PHI: float = 1.0 / PHI
SQRT5: float = math.sqrt(5.0)


def fibonacci(n: int) -> int:
    """Fast doubling exact arbitrary-precision Fibonacci sequence."""
    if n < 0:
        return ((-1) ** ((-n) + 1)) * fibonacci(-n)
    if n == 0:
        return 0
    if n in (1, 2):
        return 1

    def _fib(k: int) -> Tuple[int, int]:
        if k == 0:
            return (0, 1)
        a, b = _fib(k >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        if k & 1:
            return (d, c + d)
        return (c, d)

    return _fib(n)[0]


def lucas(n: int) -> int:
    """Exact Lucas sequence: L_n = F_{n-1} + F_{n+1}."""
    if n < 0:
        return ((-1) ** (-n)) * lucas(-n)
    if n == 0:
        return 2
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n + 1)


def binet_fibonacci(n: int) -> float:
    """Analytical closed form: (Phi^n - Psi^n) / sqrt(5)."""
    return (math.pow(PHI, n) - math.pow(PSI, n)) / SQRT5


def binet_lucas(n: int) -> float:
    """Analytical closed form: Phi^n + Psi^n."""
    return math.pow(PHI, n) + math.pow(PSI, n)


def cassini_check(n: int) -> bool:
    """Cassini identity witness: F_{n+1}*F_{n-1} - F_n^2 == (-1)^n."""
    return (fibonacci(n + 1) * fibonacci(n - 1) - (fibonacci(n) ** 2)) == ((-1) ** n)


def doubling_check(n: int) -> bool:
    """Doubling identity witness: L_n * F_n == F_{2n}."""
    return lucas(n) * fibonacci(n) == fibonacci(2 * n)


def q_matrix_power(n: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Symplectic Fibonacci Q-matrix power M^n."""
    return ((fibonacci(n + 1), fibonacci(n)), (fibonacci(n), fibonacci(n - 1)))


def golden_matrix_trace(n: int) -> int:
    """Tr(M^n) = L_n."""
    return lucas(n)


def golden_matrix_det(n: int) -> int:
    """det(M^n) = (-1)^n."""
    return (-1) ** n


def zeckendorf_encode(n: int) -> List[int]:
    """Decomposes n into unique non-consecutive Fibonacci indices."""
    if n <= 0:
        return []
    fibs = [fibonacci(2), fibonacci(3)]
    k = 3
    while fibs[-1] <= n:
        k += 1
        fibs.append(fibonacci(k))
    indices = []
    rem = n
    for idx in range(len(fibs) - 1, -1, -1):
        if fibs[idx] <= rem:
            indices.append(idx + 2)
            rem -= fibs[idx]
            if rem == 0:
                break
    return indices


def zeckendorf_decode(indices: List[int]) -> int:
    """Reconstructs integer from Zeckendorf index sequence."""
    return sum(fibonacci(idx) for idx in indices)


# =====================================================================
# 1.5 EXTENDED ALGEBRAIC FAMILY — THE FULL PISOT SPECTRUM
# =====================================================================
# One operator algebra, five generators. Every family member is the
# dominant root of a monic characteristic polynomial with all Galois
# conjugates strictly inside the unit disk, so each carries the same
# invariant bundle the golden family does: exact integer coordinate and
# trace limbs, a unimodular companion matrix (|det| = 1 — the generalised
# Cassini volume invariant), a Binet-type closed form, and exponential
# drift collapse |mu|^n -> 0.
#
#   family      char poly          coordinate limb   trace limb    |mu|max
#   golden      x^2 - x - 1        Fibonacci         Lucas          0.618
#   silver      x^2 - 2x - 1       Pell              Pell-Lucas     0.414
#   plastic     x^3 - x - 1        Padovan           Perrin         0.868
#   supergolden x^3 - x^2 - 1      Narayana          trace limb     0.826
#   tribonacci  x^3 - x^2 - x - 1  Tribonacci        trace limb     0.737

FAMILY_COEFFS: Dict[str, Tuple[int, ...]] = {
    "golden": (1, -1, -1),
    "silver": (1, -2, -1),
    "plastic": (1, 0, -1, -1),
    "supergolden": (1, -1, 0, -1),
    "tribonacci": (1, -1, -1, -1),
}

FAMILY_ROOT_NAMES: Dict[str, str] = {
    "golden": "phi",
    "silver": "delta_S",
    "plastic": "rho",
    "supergolden": "psi_s",
    "tribonacci": "tau",
}


def _polyval_dec(coeffs: List[int], x: Decimal) -> Decimal:
    """Horner evaluation of an integer polynomial at a Decimal point."""
    acc = Decimal(0)
    for c in coeffs:
        acc = acc * x + Decimal(c)
    return acc


_FAMILY_ROOT_CACHE: Dict[Tuple[str, int], Decimal] = {}


def family_root(name: str, precision: int = 50) -> Decimal:
    """Dominant Pisot root of the family's characteristic polynomial.

    Decimal Newton iteration on the exact integer polynomial — converges
    to the unique real root > 1 for every family in the spectrum.
    """
    coeffs = list(FAMILY_COEFFS[name])
    key = (name, precision)
    if key in _FAMILY_ROOT_CACHE:
        return _FAMILY_ROOT_CACHE[key]
    getcontext().prec = max(getcontext().prec, precision + 8)
    deg = len(coeffs) - 1
    dcoeffs = [c * (deg - i) for i, c in enumerate(coeffs[:-1])]
    x = Decimal(3) / 2
    tol = Decimal(10) ** (-(precision - 5))
    for _ in range(4 * precision):
        f = _polyval_dec(coeffs, x)
        fp = _polyval_dec(dcoeffs, x)
        if fp == 0:
            break
        step = f / fp
        x -= step
        if abs(step) < tol:
            break
    _FAMILY_ROOT_CACHE[key] = +x
    return _FAMILY_ROOT_CACHE[key]


def family_pisot_modulus(name: str, precision: int = 50) -> Decimal:
    """Largest conjugate modulus |mu|max, exactly: (|a0| / alpha)^(1/(d-1)).

    Every family polynomial has one real root alpha > 1; the remaining
    d-1 roots are a single real conjugate (d = 2) or a complex conjugate
    pair (d = 3). The product of all roots is (-1)^d * a0 with a0 = -1,
    so the conjugate modulus is alpha^{-1} (quadratics) or alpha^{-1/2}
    (cubics) — exact Decimal arithmetic, no eigensolver.
    """
    coeffs = FAMILY_COEFFS[name]
    d = len(coeffs) - 1
    getcontext().prec = max(getcontext().prec, precision)
    alpha = family_root(name, precision)
    ratio = Decimal(abs(coeffs[-1])) / alpha
    return ratio if d == 2 else ratio.sqrt()


def family_companion(name: str) -> List[List[int]]:
    """Integer companion matrix: superdiagonal ones, last row the
    recurrence coefficients. det(M) = (-1)^d * a0, unimodular here."""
    coeffs = FAMILY_COEFFS[name]
    d = len(coeffs) - 1
    M = [[0] * d for _ in range(d)]
    for i in range(d - 1):
        M[i][i + 1] = 1
    for j in range(d):
        M[d - 1][j] = -coeffs[d - j]
    return M


def _imat_mul(A: List[List[int]], B: List[List[int]]) -> List[List[int]]:
    n = len(A)
    return [[sum(A[i][k] * B[k][j] for k in range(n)) for j in range(n)] for i in range(n)]


def family_matrix_power(name: str, n: int) -> List[List[int]]:
    """Exact integer M^n via binary exponentiation."""
    M = family_companion(name)
    d = len(M)
    R = [[int(i == j) for j in range(d)] for i in range(d)]
    e = n
    while e:
        if e & 1:
            R = _imat_mul(R, M)
        M = _imat_mul(M, M)
        e >>= 1
    return R


def family_trace(name: str, n: int) -> int:
    """tr(M^n) — the integer-snap trace identity for any family."""
    M_n = family_matrix_power(name, n)
    return sum(M_n[i][i] for i in range(len(M_n)))


def _imat_det(M: List[List[int]]) -> int:
    if len(M) == 1:
        return M[0][0]
    if len(M) == 2:
        return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    return sum(
        ((-1) ** j) * M[0][j] * _imat_det([row[:j] + row[j + 1 :] for row in M[1:]])
        for j in range(len(M))
    )


def family_det(name: str, n: int) -> int:
    """det(M^n) — the generalised Cassini witness (always ±1 here)."""
    return _imat_det(family_matrix_power(name, n))


def _linear_recurrence(coeffs_tail: Tuple[int, ...], init: Tuple[int, ...], n: int) -> int:
    """Exact integer linear recurrence: a_k = sum_j coeffs_tail[j-1] * a_{k-j}."""
    if n < 0:
        return 0
    terms = list(init)
    d = len(coeffs_tail)
    while len(terms) <= n:
        terms.append(sum(coeffs_tail[j - 1] * terms[-j] for j in range(1, d + 1)))
    return terms[n]


def pell(n: int) -> int:
    """Pell numbers — silver-family coordinate limb: 0,1,2,5,12,29,..."""
    return _linear_recurrence((2, 1), (0, 1), n)


def pell_lucas(n: int) -> int:
    """Pell-Lucas numbers — silver-family trace limb: 2,2,6,14,34,82,..."""
    return _linear_recurrence((2, 1), (2, 2), n)


def padovan(n: int) -> int:
    """Padovan sequence — plastic-family coordinate limb: 1,1,1,2,2,3,4,5,7,9,12,..."""
    return _linear_recurrence((0, 1, 1), (1, 1, 1), n)


def perrin(n: int) -> int:
    """Perrin sequence — plastic-family trace limb: 3,0,2,3,2,5,5,7,10,12,17,..."""
    return _linear_recurrence((0, 1, 1), (3, 0, 2), n)


def narayana(n: int) -> int:
    """Narayana sequence — supergolden coordinate limb: 1,1,1,2,3,4,6,9,13,19,..."""
    return _linear_recurrence((1, 0, 1), (1, 1, 1), n)


def tribonacci(n: int) -> int:
    """Tribonacci sequence: 0,0,1,1,2,4,7,13,24,44,..."""
    return _linear_recurrence((1, 1, 1), (0, 0, 1), n)


def _supergolden_trace(n: int) -> int:
    """Supergolden trace limb tr(M^n): 3,1,1,4,5,6,10,..."""
    return _linear_recurrence((1, 0, 1), (3, 1, 1), n)


def _tribonacci_trace(n: int) -> int:
    """Tribonacci trace limb tr(M^n): 3,1,3,7,11,21,39,..."""
    return _linear_recurrence((1, 1, 1), (3, 1, 3), n)


FAMILY_COORDINATE_LIMBS: Dict[str, Any] = {
    "golden": fibonacci,
    "silver": pell,
    "plastic": padovan,
    "supergolden": narayana,
    "tribonacci": tribonacci,
}

FAMILY_TRACE_LIMBS: Dict[str, Any] = {
    "golden": lucas,
    "silver": pell_lucas,
    "plastic": perrin,
    "supergolden": _supergolden_trace,
    "tribonacci": _tribonacci_trace,
}


def detect_family_signature(series: Any) -> Dict[str, Any]:
    """Detect which recurrence structure a series obeys — exact Decimal
    arithmetic, same canonical implementation toe.engine delegates to.

    Fits the four lag templates (lag-12 golden, lag-23 plastic, lag-13
    supergolden, lag-123 tribonacci) against the data and returns the
    best-matching family with a confidence margin. Unstructured data
    reports 'unstructured'.
    """
    flat: List[Decimal] = []
    if hasattr(series, "ravel"):
        series = series.ravel().tolist()
    for x in series:
        try:
            fx = float(x)
            if fx == fx and abs(fx) != float("inf"):
                flat.append(Decimal(str(fx)))
        except (TypeError, ValueError):
            continue
    if len(flat) < 6:
        return {"family": "unstructured", "confidence": Decimal(0), "residuals": {}}
    mean = sum(flat) / len(flat)
    var = sum((x - mean) ** 2 for x in flat) / len(flat)
    if var == 0:
        return {"family": "unstructured", "confidence": Decimal(0), "residuals": {}}
    scale = var.sqrt()
    templates = {
        "golden": lambda x: [x[i + 2] - x[i + 1] - x[i] for i in range(len(x) - 2)],
        "plastic": lambda x: [x[i + 3] - x[i + 1] - x[i] for i in range(len(x) - 3)],
        "supergolden": lambda x: [x[i + 3] - x[i + 2] - x[i] for i in range(len(x) - 3)],
        "tribonacci": lambda x: [x[i + 3] - x[i + 2] - x[i + 1] - x[i] for i in range(len(x) - 3)],
    }
    residuals = {}
    for name, resid in templates.items():
        r = resid(flat)
        residuals[name] = (
            (sum(v * v for v in r) / len(r)).sqrt() / scale if r else Decimal("Infinity")
        )
    ranked = sorted(residuals.items(), key=lambda kv: kv[1])
    best, best_r = ranked[0]
    margin = ranked[1][1] - best_r if len(ranked) > 1 else Decimal(0)

    def _clip(v: Decimal) -> Decimal:
        return max(Decimal(0), min(Decimal(1), v))

    confidence = _clip(Decimal(1) - best_r) * _clip(margin * 4)
    family = best if (best_r < Decimal("0.5") and confidence > Decimal("0.05")) else "unstructured"
    return {
        "family": family,
        "confidence": confidence,
        "residuals": residuals,
        "runner_up": ranked[1][0] if len(ranked) > 1 else None,
    }


# Family limbs used to diversify the nonce probe order across lag
# structures — one per family so no single recurrence's arithmetic
# progressions dominate the front of the scan.
FAMILY_NONCE_LIMBS: Tuple[Any, ...] = (lucas, pell_lucas, padovan, narayana, tribonacci)


# ---------------------------------------------------------------------
# T_phi — the Cassini-protected fold over Z/256Z
# ---------------------------------------------------------------------
# M15 is a byte-pair bijection in GL(2, Z/256Z): det(M15) = -1 mod 256
# (the Cassini invariant), so M15_INV is an exact integer inverse and the
# fold is *bit-exact* — no floats, no tolerance, no information loss.
# The fold is a working representation, not a codec: queries are compiled
# against folded bytes via q^T x = (M^-T q)^T y (mod 256) and never
# materialise the raw buffer.

M15: Tuple[Tuple[int, int], Tuple[int, int]] = ((219, 98), (98, 121))
M15_INV: Tuple[Tuple[int, int], Tuple[int, int]] = ((135, 98), (98, 37))
FOLD_MODULUS: int = 256


def t_phi_fold(raw: bytes) -> bytes:
    """Fold raw bytes through the Cassini-protected T_phi bijection.

    Byte pairs are multiplied by M15 mod 256 — exact, invertible,
    same-length (a trailing odd byte pads with zero on the fold axis).
    """
    out = bytearray(len(raw) + (len(raw) & 1))
    n_pairs = len(raw) // 2
    for i in range(n_pairs):
        x, y = raw[2 * i], raw[2 * i + 1]
        out[2 * i] = (M15[0][0] * x + M15[0][1] * y) % FOLD_MODULUS
        out[2 * i + 1] = (M15[1][0] * x + M15[1][1] * y) % FOLD_MODULUS
    if len(raw) & 1:
        x = raw[-1]
        out[-2] = (M15[0][0] * x) % FOLD_MODULUS
        out[-1] = (M15[1][0] * x) % FOLD_MODULUS
    return bytes(out)


def t_phi_unfold(folded: bytes, original_len: int) -> bytes:
    """Exact inverse of t_phi_fold over Z/256Z."""
    out = bytearray()
    for i in range(0, len(folded) - 1, 2):
        u, v = folded[i], folded[i + 1]
        out.append((M15_INV[0][0] * u + M15_INV[0][1] * v) % FOLD_MODULUS)
        if len(out) < original_len:
            out.append((M15_INV[1][0] * u + M15_INV[1][1] * v) % FOLD_MODULUS)
    return bytes(out[:original_len])


def iter_original_u8(folded: bytes, original_len: int):
    """Stream the original bytes out of folded state — inverse fused into
    the read, no raw buffer materialised."""
    emitted = 0
    for i in range(0, len(folded) - 1, 2):
        u, v = folded[i], folded[i + 1]
        if emitted < original_len:
            yield (M15_INV[0][0] * u + M15_INV[0][1] * v) % FOLD_MODULUS
            emitted += 1
        if emitted < original_len:
            yield (M15_INV[1][0] * u + M15_INV[1][1] * v) % FOLD_MODULUS
            emitted += 1


def folded_modular_dot(folded: bytes, original_len: int, weights: List[int]) -> int:
    """q^T x (mod 256) computed directly on folded bytes as (M^-T q)^T y —
    the query is compiled into the fold; the data never leaves it."""
    total = 0
    for pair, i in enumerate(range(0, len(folded) - 1, 2)):
        q0 = int(weights[2 * pair]) if 2 * pair < original_len else 0
        q1 = int(weights[2 * pair + 1]) if 2 * pair + 1 < original_len else 0
        qu = (M15_INV[0][0] * q0 + M15_INV[1][0] * q1) % FOLD_MODULUS
        qv = (M15_INV[0][1] * q0 + M15_INV[1][1] * q1) % FOLD_MODULUS
        total = (total + qu * folded[i] + qv * folded[i + 1]) % FOLD_MODULUS
    return total


def extended_nonce_schedule(nonce_window: int, seed: int = 0, cap: int = 1000) -> Tuple[int, ...]:
    """Multi-family nonce probe order for the PYTHIA scan.

    Zeckendorf leading offsets (seed-dependent, same as the plain
    fallback), then a round-robin of the five family limbs modulo the
    window. The accept/reject rule is untouched — this only reorders
    which nonces get probed first.
    """
    window = max(int(nonce_window), 1)
    limit = min(window, max(int(cap), 1))
    seen: set = set()
    schedule: List[int] = []
    for z in zeckendorf_encode(max(int(seed), 1)):
        off = (z * 13) % window
        if off not in seen:
            schedule.append(off)
            seen.add(off)
    k = 1
    li = 0
    guard = 0
    while len(schedule) < limit and guard < window * 16:
        off = FAMILY_NONCE_LIMBS[li % len(FAMILY_NONCE_LIMBS)](k) % window
        if off not in seen:
            schedule.append(off)
            seen.add(off)
        li += 1
        if li % len(FAMILY_NONCE_LIMBS) == 0:
            k += 1
        guard += 1
    return tuple(schedule)


# =====================================================================
# 2. 32-NODE DODECAHEDRON-ICOSAHEDRON DUAL OVERLAY & HILBERT FOLDING
# =====================================================================


def _normalize_vec(v: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return v
    return [x / norm for x in v]


def generate_icosahedron_vertices() -> List[List[float]]:
    """Generates the 12 normalized vertices of a regular icosahedron."""
    vertices = []
    for s1 in [-1.0, 1.0]:
        for s2 in [-1.0, 1.0]:
            vertices.append(_normalize_vec([0.0, s1 * 1.0, s2 * PHI]))
            vertices.append(_normalize_vec([s1 * 1.0, s2 * PHI, 0.0]))
            vertices.append(_normalize_vec([s1 * PHI, 0.0, s2 * 1.0]))
    return vertices


def generate_dodecahedron_vertices() -> List[List[float]]:
    """The 20 normalized vertices of the icosahedron's dual dodecahedron.

    They are the face centres of ``generate_icosahedron_vertices()``: the cube
    corners (+-1, +-1, +-1) and the cyclic family (0, +-phi, +-1/phi). The
    mirror family (0, +-1/phi, +-phi) is a regular dodecahedron too, but not
    this icosahedron's dual.
    """
    vertices = []
    for s1 in [-1.0, 1.0]:
        for s2 in [-1.0, 1.0]:
            for s3 in [-1.0, 1.0]:
                vertices.append(_normalize_vec([s1, s2, s3]))
    for s1 in [-1.0, 1.0]:
        for s2 in [-1.0, 1.0]:
            vertices.append(_normalize_vec([0.0, s1 * PHI, s2 * INV_PHI]))
            vertices.append(_normalize_vec([s1 * PHI, s2 * INV_PHI, 0.0]))
            vertices.append(_normalize_vec([s1 * INV_PHI, 0.0, s2 * PHI]))
    return vertices


def generate_dual_overlay_frame() -> List[List[float]]:
    """Generates the unified 32-node compound frame on S^2."""
    return generate_icosahedron_vertices() + generate_dodecahedron_vertices()


class HilbertOverlayProjector:
    """Projects quantum states onto the 32-node dual frame to evaluate concentration."""

    def __init__(self):
        self.frame = generate_dual_overlay_frame()

    def project_state(self, state_3d: List[float]) -> List[float]:
        norm = math.sqrt(sum(x * x for x in state_3d)) + 1e-12
        norm_state = [x / norm for x in state_3d]
        overlaps = [sum(f[i] * norm_state[i] for i in range(3)) for f in self.frame]
        probs = [ov * ov for ov in overlaps]
        total_p = sum(probs)
        return [p / total_p for p in probs]

    def calculate_n_eff(self, state_3d: List[float]) -> float:
        """Computes effective subspace dimension: N_eff = 1 / sum(p_i^2)."""
        probs = self.project_state(state_3d)
        sum_p2 = sum(p * p for p in probs)
        return float(1.0 / sum_p2)


# =====================================================================
# 3. INTERNAL PYTHIA MINING ENGINE WITH MIDSTATE CHUNKING
# =====================================================================

MAX_TARGET: int = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


def nbits_to_target(nbits: int) -> int:
    """Converts compact 32-bit nBits format to 256-bit target integer."""
    exponent = nbits >> 24
    mantissa = nbits & 0x007FFFFF
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def target_to_difficulty(target: int) -> float:
    """Calculates pool difficulty relative to Genesis difficulty 1."""
    if target <= 0:
        return 0.0
    return float(MAX_TARGET) / float(target)


def hash_meets_target(digest: bytes, target: int) -> bool:
    """The single canonical consensus check.

    The sha256d digest is interpreted as a little-endian 256-bit integer
    and must be <= the target. This is the ONLY accept rule — every
    search path in the repo must route through it so byte order can never
    diverge between modules.
    """
    return int.from_bytes(digest, "little") <= target


class PythiaMiningEngine:
    """
    PYTHIA Substrate Mining Engine.
    High-throughput double-SHA256 engine with 64-byte Chunk-1 midstate partitioning.
    Internal bootstrapping engine.
    """

    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()

    @classmethod
    def compute_merkle_root(cls, coinbase_hash: bytes, merkle_branches: List[bytes]) -> bytes:
        curr = coinbase_hash
        for branch in merkle_branches:
            curr = cls.double_sha256(curr + branch)
        return curr

    @classmethod
    def partition_header_for_midstate(
        cls,
        version: int,
        prev_hash_le: bytes,
        merkle_root_le: bytes,
        ntime: int,
        nbits: int,
    ) -> Tuple[bytes, bytes]:
        """Partitions 76 fixed bytes into 64-byte Chunk 1 and 12-byte Chunk 2 prefix."""
        header_76 = (
            struct.pack("<I", version)
            + prev_hash_le
            + merkle_root_le
            + struct.pack("<II", ntime, nbits)
        )
        return header_76[:64], header_76[64:76]

    def scan_range(
        self,
        chunk1: bytes,
        chunk2_prefix: bytes,
        target: int,
        nonce_start: int = 0,
        nonce_count: int = 10_000,
    ) -> Optional[Tuple[int, bytes]]:
        """Evaluates nonces against target threshold using little-endian consensus order."""
        for nonce in range(nonce_start, nonce_start + nonce_count):
            header = chunk1 + chunk2_prefix + struct.pack("<I", nonce)
            h = self.double_sha256(header)
            if hash_meets_target(h, target):
                return nonce, h
        return None


# Alias for backward compatibility
MiningEngine = PythiaMiningEngine


# =====================================================================
# 4. EMBEDDED INVARIANT VERIFICATION HARNESS
# =====================================================================


def run_self_verification() -> bool:
    # 1. Algebraic Recurrences & Identities
    for n in range(1, 35):
        assert cassini_check(n), f"Cassini invariant failed at n={n}"
        assert doubling_check(n), f"Doubling identity failed at n={n}"
        assert abs(binet_fibonacci(n) - fibonacci(n)) < 1e-4, f"Binet Fibonacci failed at n={n}"
        assert abs(binet_lucas(n) - lucas(n)) < 1e-4, f"Binet Lucas failed at n={n}"

    # 2. Symplectic Matrix Group
    for n in range(1, 20):
        assert golden_matrix_trace(n) == lucas(n), f"Matrix trace failed at n={n}"
        assert golden_matrix_det(n) == ((-1) ** n), f"Matrix determinant failed at n={n}"

    # 3. Zeckendorf Base Decomposition
    for v in range(1, 100):
        indices = zeckendorf_encode(v)
        sorted_idx = sorted(indices)
        for i in range(len(sorted_idx) - 1):
            assert (
                sorted_idx[i + 1] > sorted_idx[i] + 1
            ), f"Consecutive indices in Zeckendorf for {v}"
        assert zeckendorf_decode(indices) == v, f"Decode mismatch for {v}"

    # 3.5 Extended algebraic family — the full Pisot spectrum
    for fam in FAMILY_COEFFS:
        r = family_root(fam)
        assert r > 1, f"{fam} root not > 1"
        assert abs(_polyval_dec(list(FAMILY_COEFFS[fam]), r)) < Decimal(
            "1e-38"
        ), f"{fam} root residual too large"
        assert family_pisot_modulus(fam) < 1, f"{fam} conjugate modulus not < 1"
        for n in range(1, 12):
            assert family_trace(fam, n) == FAMILY_TRACE_LIMBS[fam](
                n
            ), f"{fam} trace identity failed at n={n}"
        assert abs(family_det(fam, 8)) == 1, f"{fam} det(M^8) not unimodular"
    assert pell(8) == 408 and pell_lucas(5) == 82, "Silver limbs off"
    assert padovan(9) == 9 and perrin(9) == 12, "Plastic limbs off"
    assert narayana(9) == 19 and tribonacci(9) == 44, "Cubic limbs off"
    sched = extended_nonce_schedule(10_000, seed=42)
    assert 0 < len(sched) <= 1000, "Extended nonce schedule malformed"
    assert len(set(sched)) == len(sched), "Extended nonce schedule has duplicates"

    # 3b. T_phi fold: Cassini-protected bijection, bit-exact, fold-space dot.
    assert (M15[0][0] * M15_INV[0][0] + M15[0][1] * M15_INV[1][0]) % 256 == 1
    assert (M15[1][0] * M15_INV[0][1] + M15[1][1] * M15_INV[1][1]) % 256 == 1
    assert (M15[0][0] * M15_INV[0][1] + M15[0][1] * M15_INV[1][1]) % 256 == 0
    for x in range(256):  # every byte value, both odd and even lengths
        for y in (0, 255, x):
            assert t_phi_unfold(t_phi_fold(bytes([x, y])), 2) == bytes([x, y])
        assert t_phi_unfold(t_phi_fold(bytes([x])), 1) == bytes([x])
    sample = bytes(range(256)) * 3
    assert t_phi_unfold(t_phi_fold(sample), len(sample)) == sample
    w = [7] * len(sample)
    assert folded_modular_dot(t_phi_fold(sample), len(sample), w) == (
        sum(7 * b for b in sample) % 256
    ), "folded modular dot diverges from raw"

    # 4. Dodecahedron-Icosahedron Compound Overlay
    frame = generate_dual_overlay_frame()
    assert len(frame) == 32, "Dual overlay must have exactly 32 nodes"
    for node in frame:
        norm = math.sqrt(sum(x * x for x in node))
        assert abs(norm - 1.0) < 1e-9, f"Node not unit norm: {norm}"
    proj = HilbertOverlayProjector()
    sample_state = [0.577, 0.577, 0.577]
    n_eff = proj.calculate_n_eff(sample_state)
    assert 1.0 <= n_eff <= 32.0, f"N_eff bounds violation: {n_eff} not in [1.0, 32.0]"

    # 5. Mining Target & Midstate Invariants
    assert nbits_to_target(0x1D00FFFF) == MAX_TARGET, "Genesis target conversion mismatch"
    assert target_to_difficulty(MAX_TARGET) == 1.0, "Difficulty 1.0 baseline mismatch"
    engine = PythiaMiningEngine()
    c1, c2 = engine.partition_header_for_midstate(1, b"\x00" * 32, b"\x00" * 32, 1000, 0x1D00FFFF)
    assert len(c1) == 64 and len(c2) == 12, "Midstate header partition size mismatch"

    easy_target = int.from_bytes(b"\xff" * 32, "big")
    synthetic_result = engine.scan_range(c1, c2, easy_target, 0, 100)
    assert synthetic_result is not None, "Nonce scanner failed on maximum target test"
    return True


if __name__ == "__main__":
    run_self_verification()
    print("[PASS] TURING & PYTHIA internal core self-verification: 100% PASS.")


# Deterministic complete nonce-window schedule — package-internal module
# (consolidated from chronus/mla1517_platform/python/turing_core.py).
# Re-exported here so the historical ``core`` namespace keeps resolving; the
# package __init__ imports them from .schedule directly.
from .schedule import (  # noqa: E402,F401
    TuringScheduleError,
    complete_nonce_schedule,
    iter_nonce_schedule,
    validate_schedule,
)
