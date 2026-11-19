"""Deliverable A: where does M15^(k) + Lucas-Pisano + exact Grover give structural advantage?

Every number here is an exact integer or ``fractions.Fraction``.  No floats, no
RNG, no mocks: targets are derived from Fibonacci/Lucas numbers or from real
block-header bytes, and every run goes through the real modules:

* ``chronus.kernels.gl2_transform``: ``hensellift_m15`` (M_k), ``FoldedRegisterN``
  (fold / Cayley-Hamilton unfold / ``collapse_generator``);
* ``chronus.geodesic.scheduler``: Lucas-Pisano geodesic order (inside the triad run);
* ``chronus.ovid.folded_custody``: real ``OvidTransformService`` + SQLite WAL
  ``DurableTheseusService`` custody, hash-chained receipts;
* ``chronus.quantum.triad_grover``: exact two-amplitude Fraction Grover.

Cost unit.  One *oracle evaluation* = one evaluation of the problem observable
F(state) (a matrix power, a trace, a polynomial, a subset sum or a SHA-256d).
A *full* query asks F(state) == target; a *graded* query asks
F(state) == target (mod 2^p).  Both cost one evaluation and share one counter.

Access models (stated so no column is compared unfairly):
  (i)   linear scan              - full boolean queries, natural order, stop at first hit
  (ii)  triad as built           - full boolean queries on every state (W), then exact Grover
  (iii) structured triad variant - graded queries drive ``collapse_generator`` bit by bit
                                   (Hensel), forks on ambiguity, then exact triad Grover on
                                   the residual 2^D_r states of each branch
  (iv)  classical structured     - (iv-a) the same graded Hensel tree with no custody/Grover;
                                   (iv-b) the best known white-box classical algorithm
  (q)   ideal Grover reference   - exact peak iteration count for (W, M); this is a
                                   *query count on a quantum machine*, not run here.

The structural property collapse needs is 2-adic continuity with shift s:
F(i) mod 2^(t+s) depends only on i mod 2^t.  ``continuity_census`` measures it
exactly from the ground-truth scan.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from chronus.geodesic.scheduler import exact_fibonacci_lucas
from chronus.kernels.gl2_transform import FoldedRegisterN, hensellift_m15
from chronus.ovid.folded_custody import FoldedWorkingHandle, OvidFoldedAdapter, attest
from chronus.quantum.triad_grover import (
    exact_grover_two_amplitude_trajectory, run_triad_exact_grover_search,
)

Mat = Tuple[Tuple[int, int], Tuple[int, int]]
Obs = Tuple[int, ...]
EVENT_HENSEL = "ATTRACTOR_HENSEL_FORK"


def F(n: int) -> int:
    return exact_fibonacci_lucas(n)[0]


def L(n: int) -> int:
    return exact_fibonacci_lucas(n)[1]


# ------------------------------------------------------------------ GL(2, Z/2^k) helpers
def mat_mul(a: Mat, b: Mat, mask: int) -> Mat:
    return (((a[0][0] * b[0][0] + a[0][1] * b[1][0]) & mask, (a[0][0] * b[0][1] + a[0][1] * b[1][1]) & mask),
            ((a[1][0] * b[0][0] + a[1][1] * b[1][0]) & mask, (a[1][0] * b[0][1] + a[1][1] * b[1][1]) & mask))


def mat_pow(m: Mat, e: int, mask: int) -> Mat:
    r: Mat = ((1, 0), (0, 1))
    while e:
        if e & 1:
            r = mat_mul(r, m, mask)
        m = mat_mul(m, m, mask)
        e >>= 1
    return r


def mat_vec(m: Mat, v: Tuple[int, int], mask: int) -> Tuple[int, int]:
    return ((m[0][0] * v[0] + m[0][1] * v[1]) & mask, (m[1][0] * v[0] + m[1][1] * v[1]) & mask)


def orbit_length_pow2(m: Mat, v: Tuple[int, int], k: int) -> Tuple[int, int]:
    """Exact orbit length of v under m in a 2-group of exponent | 2^k, by repeated
    squaring.  Returns (length, number of squarings = evaluations used)."""
    mask = (1 << k) - 1
    p, e, evals = m, 0, 0
    while True:
        evals += 1
        if mat_vec(p, v, mask) == v:
            # smallest e with m^(2^e) v = v  =>  orbit length 2^e (orbit length is a power of 2)
            return 1 << e, evals
        p = mat_mul(p, p, mask)
        e += 1
        if e > k:
            raise ArithmeticError("element order exceeds 2^k")


# ------------------------------------------------------------------ oracle with exact counters
class CountingOracle:
    def __init__(self, observable: Callable[[int], Obs], target: Obs) -> None:
        self.observable = observable
        self.target = target
        self.evaluations = 0
        self.full_queries = 0
        self.graded_queries = 0

    def obs(self, value: int) -> Obs:
        self.evaluations += 1
        return self.observable(value)

    def full(self, value: int) -> bool:
        self.full_queries += 1
        return self.obs(value) == self.target

    def graded(self, value: int, precision: int) -> bool:
        self.graded_queries += 1
        m = (1 << precision) - 1
        return all(((a ^ b) & m) == 0 for a, b in zip(self.obs(value), self.target))

    __call__ = full


# ------------------------------------------------------------------ problem definitions
@dataclass
class Problem:
    test: str
    family: str
    k: int
    N: int
    register: FoldedRegisterN          # plain (unfolded) register; state i -> value
    observable: Callable[[int], Obs]   # value -> observable tuple
    target: Obs
    obs_bits: int                      # bit width of each observable component
    shift: Optional[int]               # claimed 2-adic continuity shift (None = no structure)
    planted_index: int
    notes: Dict[str, object] = field(default_factory=dict)

    @property
    def W(self) -> int:
        return 1 << self.N

    def value(self, i: int) -> int:
        hi, lo = self.register.evaluate_index(i)
        return (hi << self.k) | lo

    def oracle(self) -> CountingOracle:
        return CountingOracle(self.observable, self.target)


def _window_register(base: int, N: int, k: int) -> FoldedRegisterN:
    return FoldedRegisterN.from_domain_offset(base & ((1 << k) - 1), num_generators=N, k=k)


def window_base(k: int) -> int:
    return L(61) & ((1 << k) - 1)


def orbit_dlog(k: int, N: int) -> Problem:
    """Test 1a - hidden shift on an M_k orbit: find x in the window with M_k^x v0 = w."""
    mask, W = (1 << k) - 1, 1 << N
    M = hensellift_m15(k)
    v0 = (F(k + 1) & mask, L(k) & mask)
    orbit, _ = orbit_length_pow2(M, v0, k)
    base = window_base(k)
    reg = _window_register(base, N, k)
    off = F(89) % W

    def observable(v: int) -> Obs:
        return mat_vec(mat_pow(M, v & mask, mask), v0, mask)

    target = observable((base + off) & mask)
    return Problem("1", "orbit_hidden_shift_dlog", k, N, reg, observable, target, k, 1, off,
                   {"v0": v0, "orbit_length": orbit, "window_base": base, "M_k": M})


def trace_fibre(k: int, N: int) -> Problem:
    """Test 1b - Cayley-Hamilton trace fibre: x with tr(M_k^x) = tau (V_x(T,-1) Lucas sequence)."""
    mask, W = (1 << k) - 1, 1 << N
    M = hensellift_m15(k)
    base = window_base(k)
    reg = _window_register(base, N, k)
    off = F(97) % W

    def observable(v: int) -> Obs:
        p = mat_pow(M, v & mask, mask)
        return ((p[0][0] + p[1][1]) & mask,)

    target = observable((base + off) & mask)
    return Problem("1", "trace_fibre", k, N, reg, observable, target, k, 1, off,
                   {"trace_M_k": (M[0][0] + M[1][1]) & mask, "window_base": base})


def order_finding(k: int, N: int) -> Problem:
    """Test 1c - order finding: exponents e in [1, W] with M_k^e u = u, u = 2^s v0 chosen
    (smallest s) so that ord(u) <= W/4; marked = multiples of ord(u)."""
    mask, W = (1 << k) - 1, 1 << N
    M = hensellift_m15(k)
    v0 = (F(k + 1) & mask, L(k) & mask)
    s = 0
    while True:
        u = ((v0[0] << s) & mask, (v0[1] << s) & mask)
        ordu, _ = orbit_length_pow2(M, u, k)
        if ordu <= W // 4:
            break
        s += 1
    reg = _window_register(1, N, k)

    def observable(v: int) -> Obs:
        return mat_vec(mat_pow(M, v & mask, mask), u, mask)

    # (M^(2^t) - I) = 0 mod 2^(t+1) and u = 0 mod 2^s  =>  continuity shift 1 + s.
    return Problem("1", "order_finding", k, N, reg, observable, u, k, 1 + s, ordu - 1,
                   {"u": u, "scale_exponent_s": s, "order": ordu, "window": "[1, W]"})


def triangular_linear(k: int, N: int) -> Problem:
    """Test 2a - sparse 2-adically triangular linear congruence over (Z/2^k)^2:
    base + sum b_j g_j = w,  g_j = 2^j (L_{3j+1}, F_{3j+1}) (both odd => unit pivots)."""
    mask, W = (1 << k) - 1, 1 << N
    gens = tuple((((L(3 * j + 1)) << j) & mask, ((F(3 * j + 1)) << j) & mask) for j in range(N))
    base = (L(k) & mask, F(k) & mask)
    reg = FoldedRegisterN(base=base, generators=gens, k=k)
    off = F(101) % W

    def observable(v: int) -> Obs:
        return (v >> k, v & mask)

    hi, lo = reg.evaluate_index(off)
    return Problem("2", "triangular_linear", k, N, reg, observable, (hi, lo), k, 0, off,
                   {"generators": "g_j = 2^j (L_{3j+1}, F_{3j+1}) mod 2^k", "base": base})


def simple_quadratic(k: int, N: int) -> Problem:
    """Test 2b - quadratic congruence with simple roots: x^2 + a x + c = T, a = L_{3k+1} odd."""
    mask, W = (1 << k) - 1, 1 << N
    a, c = L(3 * k + 1) & mask, F(k) & mask
    base = window_base(k)
    reg = _window_register(base, N, k)
    off = F(103) % W

    def observable(v: int) -> Obs:
        x = v & mask
        return ((x * x + a * x + c) & mask,)

    target = observable((base + off) & mask)
    return Problem("2", "quadratic_simple_root", k, N, reg, observable, target, k, 0, off,
                   {"a": a, "c": c, "window_base": base})


def square_root(k: int, N: int) -> Problem:
    """Test 2c - degenerate quadratic x^2 = r (mod 2^k): non-simple roots, Hensel branches."""
    mask, W = (1 << k) - 1, 1 << N
    base = window_base(k)
    reg = _window_register(base, N, k)
    off = F(107) % W

    def observable(v: int) -> Obs:
        x = v & mask
        return ((x * x) & mask,)

    target = observable((base + off) & mask)
    return Problem("2", "quadratic_square_root", k, N, reg, observable, target, k, 1, off,
                   {"window_base": base})


def generic_subset_sum(k: int, N: int) -> Problem:
    """Test 2d - dense (generic) subset-sum congruence: g_j = (L_{5j+7}, F_{5j+11}) mod 2^k,
    no 2-adic triangular structure."""
    mask, W = (1 << k) - 1, 1 << N
    gens = tuple((L(5 * j + 7) & mask, F(5 * j + 11) & mask) for j in range(N))
    base = (L(k) & mask, F(k) & mask)
    reg = FoldedRegisterN(base=base, generators=gens, k=k)
    off = F(109) % W

    def observable(v: int) -> Obs:
        return (v >> k, v & mask)

    hi, lo = reg.evaluate_index(off)
    return Problem("2", "subset_sum_generic", k, N, reg, observable, (hi, lo), k, None, off,
                   {"generators": "g_j = (L_{5j+7}, F_{5j+11}) mod 2^k", "base": base})


def sha256d_point(header: bytes, N: int) -> Problem:
    """Test 3 - flat point target hidden by SHA-256d over the nonce lane (k = 32).
    Window base and planted index come from sha256(header[:76]) only."""
    k, W = 32, 1 << N
    prefix = header[:76]
    ntime = int.from_bytes(header[68:72], "little")
    h = hashlib.sha256(prefix).digest()
    off = int.from_bytes(h[:4], "big") % W
    nbase = int.from_bytes(h[4:8], "big")
    reg = FoldedRegisterN.from_domain_offset((ntime << 32) | nbase, num_generators=N, k=32)

    def observable(v: int) -> Obs:
        d = hashlib.sha256(hashlib.sha256(prefix + (v & 0xFFFFFFFF).to_bytes(4, "little")).digest()).digest()
        return (int.from_bytes(d, "little"),)

    hi, lo = reg.evaluate_index(off)
    target = observable((hi << 32) | lo)
    return Problem("3", "sha256d_point_target", k, N, reg, observable, target, 256, None, off,
                   {"nonce_base": nbase, "ntime": ntime})


TEST1 = (orbit_dlog, trace_fibre, order_finding)
TEST2 = (triangular_linear, simple_quadratic, square_root, generic_subset_sum)


# ------------------------------------------------------------------ (i) ground truth / linear scan
@dataclass
class GroundTruth:
    observables: List[Obs]
    marked: List[int]
    first_hit_evaluations: Optional[int]
    exhaustive_evaluations: int
    ns: int


def ground_truth(p: Problem) -> GroundTruth:
    o = p.oracle()
    t0 = perf_counter_ns()
    obs = [o.obs(p.value(i)) for i in range(p.W)]
    ns = perf_counter_ns() - t0
    marked = [i for i, x in enumerate(obs) if x == p.target]
    return GroundTruth(obs, marked, marked[0] + 1 if marked else None, o.evaluations, ns)


def continuity_census(p: Problem, obs: Sequence[Obs], shift: Optional[int] = None) -> Tuple[int, int]:
    """Exact count of pairs (i, i + 2^t), t = 1..N-1, with F(i) = F(i+2^t) mod 2^min(t+s, obs_bits).
    Returns (agreeing, total).  agreeing == total  <=>  2-adically continuous with shift s."""
    s = (p.shift if p.shift is not None else 0) if shift is None else shift
    agree = total = 0
    for t in range(1, p.N):
        m = (1 << min(t + s, p.obs_bits)) - 1
        step = 1 << t
        for i in range(p.W - step):
            total += 1
            agree += all(((a ^ b) & m) == 0 for a, b in zip(obs[i], obs[i + step]))
    return agree, total


# ------------------------------------------------------------------ (q) ideal Grover reference
def ideal_grover(W: int, M: int) -> dict:
    if M == 0:
        return {"iterations": None, "probability": None}
    t, _a, _b, prob = exact_grover_two_amplitude_trajectory(W, M)[-1]
    return {"iterations": t, "probability": prob}


# ------------------------------------------------------------------ (iv-a) graded Hensel tree
def hensel_tree(p: Problem, oracle: CountingOracle, levels: int, shift: int,
                value_of: Optional[Callable[[Sequence[int]], List[int]]] = None) -> Tuple[List[int], List[int]]:
    """Bit-by-bit lift of the window index i.  Level j decides bit j with a graded query at
    precision min(j+1+shift, obs_bits) on the candidate index (higher bits 0).  Valid exactly
    when F is 2-adically continuous with that shift.  Returns (surviving prefixes, branch
    count per level)."""
    branches, widths = [0], []
    for j in range(levels):
        prec = min(j + 1 + shift, p.obs_bits)
        nxt = []
        for r in branches:
            cands = [r, r | (1 << j)]
            vals = value_of(cands) if value_of else [p.value(c) for c in cands]
            nxt.extend(c for c, v in zip(cands, vals) if oracle.graded(v, prec))
        branches = nxt
        widths.append(len(branches))
    return branches, widths


def classical_hensel(p: Problem, shift: Optional[int] = None) -> dict:
    s = p.shift if shift is None else shift
    if s is None:
        s = 0
    o = p.oracle()
    t0 = perf_counter_ns()
    leaves, widths = hensel_tree(p, o, p.N, s)
    found = [i for i in leaves if o.full(p.value(i))]
    return {"found": sorted(found), "evaluations": o.evaluations, "graded": o.graded_queries,
            "verify": o.full_queries, "max_width": max(widths) if widths else 1, "ns": perf_counter_ns() - t0,
            "shift_used": s}


# ------------------------------------------------------------------ (iv-b) best white-box classical
def classical_best(p: Problem, gt: GroundTruth) -> dict:
    """Best known classical algorithm for the family, with its own exact cost count."""
    t0 = perf_counter_ns()
    mask = (1 << p.k) - 1
    if p.family == "order_finding":
        M = hensellift_m15(p.k)
        ordu, evals = orbit_length_pow2(M, p.target, p.k)
        found = [e - 1 for e in range(ordu, p.W + 1, ordu)]      # index i <-> exponent 1 + i
        return {"method": "repeated squaring in the 2-group <M_k> (order is a power of 2)",
                "found": found, "evaluations": evals, "ns": perf_counter_ns() - t0}
    if p.family == "triangular_linear":
        o = p.oracle()
        r0 = (p.target[0] - p.register.base[0]) & mask
        bits = 0
        acc = 0
        for j, g in enumerate(p.register.generators):
            if ((r0 - acc) >> j) & 1:
                bits |= 1 << j
                acc = (acc + g[0]) & mask
        ok = o.full(p.value(bits))
        return {"method": "back-substitution (Hermite/triangular elimination mod 2^k), white-box",
                "found": [bits] if ok else [], "evaluations": o.evaluations, "ns": perf_counter_ns() - t0}
    if p.family == "quadratic_simple_root":
        # f(x) = x^2 + a x + c - T with a odd: f(x) = c - T (mod 2) for every x and f'(x) = 2x + a
        # is odd, so both residues mod 2 are simple roots and each lifts uniquely (Newton).
        a, c, T = p.notes["a"], p.notes["c"], p.target[0]
        o = p.oracle()
        base = p.notes["window_base"]
        found, steps = [], 0
        if ((c - T) & 1) == 0:
            for x in (0, 1):
                prec = 1
                while prec < p.k:
                    prec = min(2 * prec, p.k)
                    m = (1 << prec) - 1
                    fx = (x * x + a * x + c - T) & m
                    x = (x - fx * pow((2 * x + a) & m, -1, 1 << prec)) & m
                    steps += 1
                i = (x - base) & mask
                if i < p.W and o.full(p.value(i)):
                    found.append(i)
        return {"method": f"Newton-Hensel lift of both simple 2-adic roots ({steps} doubling steps), white-box",
                "found": sorted(found), "evaluations": o.evaluations, "ns": perf_counter_ns() - t0}
    if p.family == "subset_sum_generic":
        half = p.N // 2
        gens = p.register.generators
        tw = ((p.target[0] - p.register.base[0]) & mask, (p.target[1] - p.register.base[1]) & mask)
        table: Dict[Tuple[int, int], List[int]] = {}
        evals = 0
        for lo in range(1 << half):
            s0 = s1 = 0
            for j in range(half):
                if (lo >> j) & 1:
                    s0 += gens[j][0]
                    s1 += gens[j][1]
            table.setdefault((s0 & mask, s1 & mask), []).append(lo)
            evals += 1
        found = []
        for hi in range(1 << (p.N - half)):
            s0 = s1 = 0
            for j in range(p.N - half):
                if (hi >> j) & 1:
                    s0 += gens[half + j][0]
                    s1 += gens[half + j][1]
            evals += 1
            for lo in table.get(((tw[0] - s0) & mask, (tw[1] - s1) & mask), []):
                found.append(lo | (hi << half))
        return {"method": "meet-in-the-middle (Horowitz-Sahni), 2 x 2^(N/2) half-sum evaluations",
                "found": sorted(found), "evaluations": evals, "ns": perf_counter_ns() - t0}
    if p.family == "sha256d_point_target":
        return {"method": "none better known than scanning (no exploitable structure)",
                "found": gt.marked[:1], "evaluations": gt.first_hit_evaluations, "ns": 0}
    # orbit dlog / trace fibre / square root: the 2-adic bit lift *is* the best known
    # classical method (Pohlig-Hellman in a 2-group / Hensel lifting of roots).
    r = classical_hensel(p)
    method = {"orbit_hidden_shift_dlog": "Pohlig-Hellman / 2-adic bit lift in the 2-group <M_k>",
              "trace_fibre": "2-adic bit lift of V_x(T,-1) = tr(M_k^x)",
              "quadratic_square_root": "2-adic square-root lift (Hensel, branching)"}[p.family]
    return {"method": method, "found": r["found"], "evaluations": r["evaluations"], "ns": r["ns"]}


# ------------------------------------------------------------------ (ii) triad as built
def triad_as_built(p: Problem, adapter: OvidFoldedAdapter, artifact_id: str) -> dict:
    o = p.oracle()
    t0 = perf_counter_ns()
    h = adapter.stage_domain(artifact_id, p.register)
    r = run_triad_exact_grover_search(adapter=adapter, handle=h, oracle_predicate=o)
    ns = perf_counter_ns() - t0
    return {"found": r.found, "winner_index": r.winner_index, "marked_count": r.marked_count,
            "iterations": r.iterations, "probability": r.total_marked_probability,
            "evaluations": o.evaluations, "receipt": r.receipts[0], "handle_version": r.handle_version,
            "ns": ns}


# ------------------------------------------------------------------ (iii) structured triad variant
def _relabel(h: FoldedWorkingHandle, artifact_id: str) -> FoldedWorkingHandle:
    return FoldedWorkingHandle(artifact_id, h.version, h.register, h.wire_frame, h.sha256_digest, h.shard_ref)


def triad_structured(p: Problem, adapter: OvidFoldedAdapter, artifact_id: str, residual_dim: int = 4,
                     shift: Optional[int] = None) -> dict:
    """Hensel-collapse the low N - D_r generators through the real OVID/THESEUS adapter
    (graded queries on OVID-materialised states, one ``commit_collapse_step`` per decided
    bit, fork into child artifacts when both lifts survive), then run the exact triad
    Grover on each branch's residual 2^D_r states."""
    s = p.shift if shift is None else shift
    if s is None:
        s = 0
    D = min(residual_dim, p.N - 1)
    levels = p.N - D
    o = p.oracle()
    t0 = perf_counter_ns()
    branches: List[Tuple[int, FoldedWorkingHandle]] = [(0, adapter.stage_domain(artifact_id, p.register))]
    widths, forks, collapses = [], 0, 0
    for j in range(levels):
        prec = min(j + 1 + s, p.obs_bits)
        nxt: List[Tuple[int, FoldedWorkingHandle]] = []
        for r, h in branches:
            cands = [r, r | (1 << j)]
            vals = adapter.materialise_indices(h, cands)
            alive = [b for b, v in zip((0, 1), vals) if o.graded(v, prec)]
            for b in alive:
                hh = h if len(alive) == 1 else _relabel(h, f"{h.artifact_id}.{b}")
                nxt.append((r | (b << j), adapter.commit_collapse_step(hh, j, b)))
                collapses += 1
            if len(alive) == 2:
                forks += 1
                adapter.theseus.append_audit_receipt(EVENT_HENSEL, attest({
                    "event": EVENT_HENSEL, "artifact_id": h.artifact_id, "generator": j,
                    "precision_bits": prec, "frame_sha256": h.sha256_digest}))
        branches = nxt
        widths.append(len(branches))
    graded_evals = o.evaluations
    found, receipts, grover = [], [], []
    for r, h in branches:
        g = run_triad_exact_grover_search(adapter=adapter, handle=h, oracle_predicate=o)
        receipts.append(g.receipts[0])
        grover.append({"marked": g.marked_count, "iterations": g.iterations,
                       "probability": g.total_marked_probability})
        if g.found:
            found.append(g.winner_index)
    ns = perf_counter_ns() - t0
    return {"found": sorted(found), "evaluations": o.evaluations, "graded_evaluations": graded_evals,
            "residual_evaluations": o.evaluations - graded_evals, "residual_dim": D, "levels": levels,
            "branches": len(branches), "max_width": max(widths) if widths else 1, "forks": forks,
            "collapses": collapses, "grover": grover, "receipts": receipts, "ns": ns, "shift_used": s}


# ------------------------------------------------------------------ ensembles for the no-structure controls
def hensel_residual_counts(p: Problem, residual_dim: int = 4, shift: int = 0) -> dict:
    """Same decision logic as ``triad_structured`` (graded lift of the low N - D_r bits, then
    every residual state per branch with full queries) without custody, for ensembles."""
    D = min(residual_dim, p.N - 1)
    o = p.oracle()
    leaves, widths = hensel_tree(p, o, p.N - D, shift)
    found = []
    for r in leaves:
        for t in range(1 << D):
            i = r | (t << (p.N - D))
            if o.full(p.value(i)):
                found.append(i)
    return {"found": found, "evaluations": o.evaluations, "branches": len(leaves),
            "hit": p.planted_index in found}


def with_planted_index(p: Problem, index: int) -> Problem:
    """Same instance, target re-planted at ``index`` (target = F(value(index)))."""
    hi, lo = p.register.evaluate_index(index)
    t = p.observable((hi << p.k) | lo)
    return Problem(p.test, p.family, p.k, p.N, p.register, p.observable, t, p.obs_bits, p.shift, index, p.notes)
