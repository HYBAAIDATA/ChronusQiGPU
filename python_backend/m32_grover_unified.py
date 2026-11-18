"""M_32 lanes + deterministic Zeckendorf/Pisano/Lucas domain order + exact Grover.

One module that wires together existing repository components:

* M_32 manifold and Voronoi lanes (12 dodecahedral + 20 icosahedral directions):
  ``python_backend/phi_grover_v4.py``.
* Domain order from Zeckendorf decomposition, the Pisano period of Fibonacci
  mod 32 (period 48), and Lucas numbers, seeded only from header[:76]
  (the winning nonce is not an input to the order).
* Exact two-amplitude folded Grover iterate (partial-phase form, Pisot-damped
  phases): ``turing_universal_quantum_computer/grover_exact_scale.py``
  (``FoldedGrover``, ``optimal_iterations``).
* Bit-sliced SHA-256d domain oracle (midstate + cached chunk-2 rounds 0-2,
  128-lane bit planes, adaptive H2 early abort, hashlib confirm):
  ``python_backend/bit_sliced_domain_oracle.py``.

Pipeline for one header and a nonce window of size W:

1. Each nonce in the window is assigned to one of the 32 M_32 lanes by
   ``phi_grover_v4.voronoi``.
2. Lanes are processed in the deterministic Zeckendorf/Pisano/Lucas order
   derived from header[:76].  Same header => same order.  No RNG.
3. Inside a lane the bit-sliced oracle produces an exact integer phase_mask
   (one SHA-256d evaluation of every lane candidate, counted in lane-rounds/64).
   Grover amplitude amplification then runs on the lane with the exact folded
   iterate (or the dense statevector when ``engine="statevector"``), for the
   iteration count that maximises the exact success probability under the
   chosen Pisot phase damping.  The collapse threshold phi^-1 gates
   measurement; because marked basis states share one amplitude, the measured
   nonce is chosen deterministically among the marked set (header-derived
   Zeckendorf/Lucas index).  The measured nonce is verified with one fresh
   SHA-256d call.

Every compression is counted as lanes x rounds/64, never one per bit-sliced
pass.  The oracle itself is classical SHA-256d evaluation: a real Grover
oracle has to mark the same set.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import struct
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence

import numpy as np

from python_backend import phi_grover_v4 as pg
from python_backend.bit_sliced_domain_oracle import (
    BitSlicedDomainOracle,
    derive_early_abort_constraints,
    sha256d,
    target_from_bits,
)
from quantum_compute_substrate.quantum_2026.classics.grover import apply_diffusion, apply_oracle

try:
    from turing_universal_quantum_computer.grover_exact_scale import FoldedGrover, optimal_iterations
except ImportError:  # pragma: no cover - repo-root import path
    from turing_universal_quantum_computer.turing_universal_quantum_computer.grover_exact_scale import (  # type: ignore
        FoldedGrover,
        optimal_iterations,
    )

from lucas.core import lucas as lucas_exact

PHI = pg.PHI
COLLAPSE_THRESHOLD = pg.PHI_I  # phi^-1
PSI_ABS = abs((1.0 - math.sqrt(5.0)) / 2.0)
N_LANES = len(pg.M32)
PISANO_32 = 48  # π(32) = 48


def _pisano_fib_mod32() -> tuple:
    """F_n mod 32 for one Pisano period, F_0=0, F_1=1."""
    seq = []
    a, b = 0, 1
    for _ in range(PISANO_32):
        seq.append(a & 31)
        a, b = b, a + b
    return tuple(seq)


PISANO_FIB_MOD32 = _pisano_fib_mod32()


def zeckendorf_indices(n: int) -> List[int]:
    """Greedy Zeckendorf indices k>=2 with n = sum F_k, no two consecutive."""
    if n <= 0:
        return []
    # F2=1, F3=2, F4=3, ...
    fib = [1, 2]
    idx = [2, 3]
    while fib[-1] < n:
        fib.append(fib[-1] + fib[-2])
        idx.append(idx[-1] + 1)
    out: List[int] = []
    rest = n
    for k, f in zip(reversed(idx), reversed(fib)):
        if f <= rest:
            out.append(k)
            rest -= f
    if rest != 0:
        raise RuntimeError(f"Zeckendorf failed for {n}: remainder {rest}")
    return out


def header_seed_integer(header80: bytes) -> int:
    """Integer seed from header bytes excluding the nonce field (bytes 76:80)."""
    if len(header80) < 76:
        raise ValueError("header must have at least 76 bytes")
    return int.from_bytes(bytes(header80[:76]), "little")


def domain_order(header80: bytes, occupied: Sequence[int]) -> List[int]:
    """Deterministic permutation of occupied M_32 lanes from header[:76].

    Start index in the Pisano cycle is the sum of L_k + k over the
    Zeckendorf indices of the header integer, reduced mod 48.  Unique
    F_n mod 32 residues are emitted in that cyclic order; any lane that
    never appears in the period is appended in Lucas-residue order.
    """
    occ = [f for f in occupied if 0 <= f < N_LANES]
    if not occ:
        return []
    zidx = zeckendorf_indices(header_seed_integer(header80))
    start = 0
    if zidx:
        for k in zidx:
            start = (start + (lucas_exact(k) % PISANO_32) + (k % PISANO_32)) % PISANO_32
    else:
        start = lucas_exact(0) % PISANO_32  # L_0 = 2
    order: List[int] = []
    seen = set()
    for i in range(PISANO_32):
        face = PISANO_FIB_MOD32[(start + i) % PISANO_32]
        if face not in seen:
            seen.add(face)
            order.append(face)
    missing = [f for f in range(N_LANES) if f not in seen]
    missing.sort(key=lambda f: (lucas_exact(f) % N_LANES, f))
    order.extend(missing)
    occ_set = set(occ)
    return [f for f in order if f in occ_set]


def deterministic_window_offset(header80: bytes, window: int) -> int:
    """Offset in [0, window) from Zeckendorf/Lucas of header[:76]."""
    if window <= 0:
        return 0
    zidx = zeckendorf_indices(header_seed_integer(header80))
    acc = lucas_exact(2) if not zidx else 0
    for k in zidx:
        acc += lucas_exact(k)
    return acc % window


def window_base_including_winner(nonce: int, window: int, header80: bytes) -> int:
    off = deterministic_window_offset(header80, window)
    nonce &= 0xFFFFFFFF
    if nonce >= off:
        return nonce - off
    return 0


def window_base_excluding_winner(nonce: int, window: int) -> int:
    """Place the window at nonce+W (wrapping in the 32-bit nonce space)."""
    nonce &= 0xFFFFFFFF
    base = (nonce + window) & 0xFFFFFFFF
    # If the unwrapped window [base, base+window) contains nonce, shift again.
    def contains(b: int) -> bool:
        end = b + window
        if end <= 1 << 32:
            return b <= nonce < end
        # wrapped window: [b, 2^32) U [0, end-2^32)
        return nonce >= b or nonce < (end - (1 << 32))
    if contains(base):
        base = (base + window) & 0xFFFFFFFF
    return base


# ---------------------------------------------------------------------------
# Grover engines
# ---------------------------------------------------------------------------


def pisot_damp(pisot_n: Optional[int]) -> float:
    return 1.0 if pisot_n is None else 1.0 - PSI_ABS ** int(pisot_n)


def peak_iterations(N: int, M: int, damp: float = 1.0) -> int:
    """Iteration count maximising the exact success probability for these phases."""
    if M <= 0 or M >= N:
        return 0
    if damp == 1.0:
        return optimal_iterations(N, M)
    st = FoldedGrover.uniform(N, M)
    best_k, best_p = 0, M / N
    for k in range(1, 2 * optimal_iterations(N, M) + 3):
        st.step(math.pi * damp, math.pi * damp)
        if st.marked_probability > best_p + 1e-15:
            best_k, best_p = k, st.marked_probability
    return best_k


def statevector_grover(N: int, marked: Sequence[int], k: int, damp: float = 1.0) -> np.ndarray:
    """Dense statevector Grover. damp == 1 uses the repo's apply_oracle/apply_diffusion;
    damp < 1 applies the same partial-phase operators as FoldedGrover.step."""
    psi = np.full(N, 1.0 / math.sqrt(N), dtype=complex)
    m = np.asarray(list(marked), dtype=int)
    for _ in range(k):
        if damp == 1.0:
            psi = apply_diffusion(apply_oracle(psi, m))
        else:
            ph = cmath.exp(1j * math.pi * damp)
            psi[m] *= ph
            psi = psi + (ph - 1.0) * psi.mean()
    return psi


def choose_marked_index(header80: bytes, marked: Sequence[int]) -> int:
    """Deterministic selection among equal-amplitude marked basis states."""
    if len(marked) == 1:
        return int(marked[0])
    off = deterministic_window_offset(header80, len(marked))
    return int(marked[off])


@dataclass
class LaneRun:
    lane: int
    candidates: int
    marked: int
    iterations: int
    repetitions: int
    p_marked: float
    measured_nonce: Optional[int]
    verified: bool
    phase_mask: int = 0


def grover_lane(lane: int, cands: List[int], oracle: BitSlicedDomainOracle,
                header80: bytes, damp: float = 1.0, engine: str = "fold") -> LaneRun:
    """Build the lane's phase oracle (bit-sliced SHA-256d -> exact mask), run
    exact amplitude amplification, measure when P >= phi^-1, verify."""
    phase_mask = oracle.phase_mask(cands)
    marked = [i for i in range(len(cands)) if (phase_mask >> i) & 1]
    N, M = len(cands), len(marked)
    if M == 0 or N == 0:
        return LaneRun(lane, N, 0, 0, 0, 0.0, None, False, phase_mask)
    if M == N:
        k, p = 0, 1.0
    else:
        k = peak_iterations(N, M, damp)
        if engine == "statevector":
            psi = statevector_grover(N, marked, k, damp)
            p = float(np.sum(np.abs(psi[marked]) ** 2))
        else:
            st = FoldedGrover.uniform(N, M)
            for _ in range(k):
                st.step(math.pi * damp, math.pi * damp)
            p = st.marked_probability
    if p < COLLAPSE_THRESHOLD and M < N:
        # Small lanes with M/N >= 1/4 (e.g. N=2, M=1) cannot cross phi^-1 with pi phases
        # (P stays 0.5).  Use the same exactly-unitary partial-phase iterate
        # (FoldedGrover.step) with a matched phase: best of k in 1..3 over a 0.25-degree grid.
        best = (p, k)
        for kk in (1, 2, 3):
            for g in range(1, 721):
                ph = math.pi * g / 720.0
                st = FoldedGrover.uniform(N, M)
                for _ in range(kk):
                    st.step(ph, ph)
                if st.marked_probability > best[0] + 1e-12:
                    best = (st.marked_probability, kk)
        p, k = best[0], best[1]
    if p < COLLAPSE_THRESHOLD:  # collapse gate: amplification did not cross phi^-1
        return LaneRun(lane, N, M, k, 0, p, None, False, phase_mask)
    idx = choose_marked_index(header80, marked)
    nonce = cands[idx]
    # Fresh SHA-256d verification (3 compressions), counted on the oracle telemetry.
    digest = sha256d(oracle.prefix + struct.pack("<I", nonce & 0xFFFFFFFF))
    oracle.telemetry.hashlib_confirms += 1
    ok = int.from_bytes(digest, "little") <= oracle.target
    if ok:
        oracle.telemetry.hashlib_hits += 1
    return LaneRun(lane, N, M, k, 1 if ok else 0, p, nonce if ok else None, ok, phase_mask)


# ---------------------------------------------------------------------------
# Unified search
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    found_nonce: Optional[int]
    found_by: str
    window_base: int
    window: int
    lanes_processed: int
    lane_order: List[int]
    grover_iterations_total: int
    measurements: int
    sha256d_calls: int
    distinct_nonces_hashed: int
    lane_rounds: int
    lane_compressions: float
    bitsliced_lane_compressions: float
    hashlib_confirms: int
    linear_scan_compressions: float
    lane_runs: List[dict] = field(default_factory=list)


def assign_lanes(base: int, window: int) -> Dict[int, List[int]]:
    lanes: Dict[int, List[int]] = {f: [] for f in range(N_LANES)}
    for n in range(base, base + window):
        lanes[pg.voronoi(n & 0xFFFFFFFF)].append(n & 0xFFFFFFFF)
    for f in lanes:  # R_phi orders visitation inside a lane (ordering only)
        lanes[f].sort(key=pg.phi_resonance, reverse=True)
    return lanes


def unified_search(header80: bytes, target: int, base: int, window: int, *,
                   pisot_n: Optional[int] = None, engine: str = "fold",
                   warrior_steps: int = 0, seed: int = 0) -> SearchResult:
    """Search ``[base, base+window)``.  ``warrior_steps`` and ``seed`` are
    accepted for call-site compatibility and ignored: the scheduler is
    deterministic and uses no RNG.
    """
    del warrior_steps, seed
    oracle = BitSlicedDomainOracle(header80, target)
    lanes = assign_lanes(base, window)
    occupied = [f for f in range(N_LANES) if lanes[f]]
    order = domain_order(header80, occupied)
    damp = pisot_damp(pisot_n)
    runs, iters, meas = [], 0, 0
    for i, face in enumerate(order, 1):
        lr = grover_lane(face, lanes[face], oracle, header80, damp, engine)
        runs.append(asdict(lr)); iters += lr.iterations * max(1, lr.repetitions); meas += lr.repetitions
        if lr.verified:
            tel = oracle.telemetry
            return SearchResult(
                lr.measured_nonce, "grover_lane", base, window, i, order, iters, meas,
                tel.hashlib_confirms, tel.lanes, tel.lane_rounds, tel.lane_compressions,
                tel.bitsliced_lane_compressions, tel.hashlib_confirms,
                0.0, runs,
            )
    tel = oracle.telemetry
    return SearchResult(
        None, "none", base, window, len(order), order, iters, meas,
        tel.hashlib_confirms, tel.lanes, tel.lane_rounds, tel.lane_compressions,
        tel.bitsliced_lane_compressions, tel.hashlib_confirms,
        0.0, runs,
    )



# ---------------------------------------------------------------------------
# CLI: run on verified mainnet headers (offline, no pool access)
# ---------------------------------------------------------------------------



def fair_linear_cost(header80: bytes, target: int, base: int, window: int, *,
                     stop_at_first_hit: bool = True):
    """(lane_compressions, nonces_evaluated, hit_nonce) for a scalar scan with the
    same midstate, cached rounds 0-2 and adaptive H2 early abort as the oracle."""
    prefix = bytes(header80[:76])
    _h7, h6 = derive_early_abort_constraints(target)
    rounds = 0
    evaluated = 0
    hit = None
    for i in range(window):
        n = (base + i) & 0xFFFFFFFF
        evaluated += 1
        rounds += 61 + 61
        digest = sha256d(prefix + struct.pack("<I", n))
        word7 = int.from_bytes(digest[28:32], "big")
        z7 = _h7
        survive7 = True
        if z7 >= 8:
            mod_bits = 8 * (z7 // 8)
            # digest bytes 28..31 big-endian = word 7; low bits must be zero
            survive7 = (word7 & ((1 << mod_bits) - 1)) == 0 if mod_bits < 32 else word7 == 0
        elif z7 > 0:
            rounds += 3
            lo = 8 - z7
            survive7 = ((word7 >> lo) & ((1 << (8 - lo)) - 1)) == 0
        if survive7 and h6 > 0 and z7 >= 8:
            rounds += 1
        if int.from_bytes(digest, "little") <= target:
            rounds += 3 * 64  # confirm
            hit = n
            if stop_at_first_hit:
                break
    return rounds / 64.0, evaluated, hit


def run_headers(path: str, window_bits: int, limit: Optional[int], pisot_n: Optional[int],
                engine: str, include_winner: bool = True,
                seed: int = 0, warrior_steps: int = 0) -> dict:
    del seed, warrior_steps
    rows = json.load(open(path))
    if limit:
        rows = rows[:limit]
    W = 1 << window_bits
    out = []
    t0 = time.perf_counter()
    for r in rows:
        hdr = bytes.fromhex(r["header_hex"])
        T = target_from_bits(int(r["bits"]))
        nonce = struct.unpack("<I", hdr[76:80])[0]
        if include_winner:
            base = window_base_including_winner(nonce, W, hdr)
        else:
            base = window_base_excluding_winner(nonce, W)
        res = unified_search(hdr, T, base, W, pisot_n=pisot_n, engine=engine)
        # Fair linear baseline on the same window, same midstate / cached rounds /
        # H2 early abort: per evaluated nonce 61 H1 + 61 H2 rounds (+1 H2 round
        # when a word-6 check applies and the lane survives word 7), plus a full
        # SHA-256d (3 compressions) for the hit it confirms.  The first-hit
        # position is located with hashlib.
        lin_comp, lin_eval, lin_hit = fair_linear_cost(hdr, T, base, W, stop_at_first_hit=include_winner)
        res.linear_scan_compressions = lin_comp
        out.append(dict(
            height=r["height"], true_nonce=nonce,
            winner_in_window=base <= nonce < base + W or (
                (base + W) > (1 << 32) and (nonce >= base or nonce < ((base + W) & 0xFFFFFFFF))
            ),
            found_nonce=res.found_nonce, correct=res.found_nonce == nonce,
            found_by=res.found_by, lanes_processed=res.lanes_processed,
            grover_iterations=res.grover_iterations_total,
            measurements=res.measurements,
            sha256d_calls=res.sha256d_calls,
            distinct_hashed=res.distinct_nonces_hashed,
            lane_rounds=res.lane_rounds,
            lane_compressions=res.lane_compressions,
            bitsliced_lane_compressions=res.bitsliced_lane_compressions,
            hashlib_confirms=res.hashlib_confirms,
            linear_scan_compressions=lin_comp,
            linear_scan_sha256d=lin_eval if not include_winner or lin_hit is None else lin_eval,
            lane_order=res.lane_order,
        ))
    found = [o for o in out if o["found_nonce"] is not None]
    n = len(out)
    correct = sum(1 for o in out if o["correct"])
    summary = dict(
        headers=n, window=W, sqrtW=math.sqrt(W), engine=engine, pisot_n=pisot_n,
        include_winner=include_winner,
        found=len(found), correct=correct,
        mean_lane_compressions=sum(o["lane_compressions"] for o in out) / n,
        mean_bitsliced_lane_compressions=sum(o["bitsliced_lane_compressions"] for o in out) / n,
        mean_linear_scan_compressions=sum(o["linear_scan_compressions"] for o in out) / n,
        mean_lanes_processed=sum(o["lanes_processed"] for o in out) / n,
        mean_distinct_hashed=sum(o["distinct_hashed"] for o in out) / n,
        seconds=round(time.perf_counter() - t0, 1),
    )
    if found:
        summary["mean_lane_compressions_per_winner_found"] = sum(o["lane_compressions"] for o in found) / len(found)
        summary["mean_linear_compressions_per_winner_found"] = sum(o["linear_scan_compressions"] for o in found) / len(found)
    # Round savings vs the fair linear baseline (same midstate / early abort).
    # Do not claim sub-linear: this can be larger or smaller than linear.
    lin = summary["mean_linear_scan_compressions"]
    ours = summary["mean_lane_compressions"]
    summary["mean_compression_delta_vs_linear"] = ours - lin
    summary["mean_round_savings_vs_linear"] = (lin - ours) * 64.0
    return dict(summary=summary, rows=out)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="M_32 lanes + Zeckendorf/Pisano/Lucas order + exact Grover (offline)"
    )
    ap.add_argument("--headers", required=True, help="JSON list with header_hex, bits, height")
    ap.add_argument("--window-bits", type=int, default=12)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0, help="ignored; retained for CLI compatibility")
    ap.add_argument("--warrior-steps", type=int, default=0, help="ignored; scheduler is not MCMC")
    ap.add_argument("--pisot-n", type=int, default=None, help="damp phases by 1-|psi|^n (default: canonical pi)")
    ap.add_argument("--engine", choices=("fold", "statevector"), default="fold")
    ap.add_argument("--no-winner", action="store_true", help="place the window at nonce+W, excluding the true nonce")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res = run_headers(a.headers, a.window_bits, a.limit, a.pisot_n, a.engine,
                      include_winner=not a.no_winner)
    print(json.dumps(res["summary"], indent=1))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
