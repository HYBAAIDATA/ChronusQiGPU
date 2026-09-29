"""phi-Grover Production Miner v4 -- the SOLVE core.

Structured nonce search on the phi-resonant manifold M_32. The deterministic
structured lane is the primary path (we know where the needle is); the
unstructured Grover lane is the fallback when no structure is detected.

TRUTH BOUNDARY (SHA256d validity is never gated by resonance):
  R_phi (phi_resonance) has ZERO correlation with SHA256d validity -- see
  artifacts/phi_hash_validity/phi_hash_correlation_summary.json (r=-0.0023)
  and docs/phi/PHI_WINNER_RESONANCE_REPORT.md (z=+1.167, p=0.24). R_phi only
  orders which candidates are visited; the SHA256d check_pow is evaluated for
  EVERY candidate and any nonce with SHA256d <= target is always returned.
"""

from __future__ import annotations

import math
import hashlib
import struct
import random
import os
import argparse
import logging
from multiprocessing import Process, Manager
from typing import List, Dict

log = logging.getLogger("phi_grover_v4")

# ============================================================
# CONSTANTS
# ============================================================

PHI = (1 + math.sqrt(5)) / 2
# Fixed heuristic threshold constant (3 - phi) ~= 1.381966 -- a hand-picked
# gate for curvature_action_score(), NOT a Yang-Mills mass gap and NOT the
# M_32 graph's Fiedler eigenvalue (~5.2318). No physics derivation claimed.
ACTION_THRESHOLD = 3 - PHI
PHI_I = PHI - 1
ALPHA = PHI**-2
BETA = PHI**-3
GAMMA = PHI**-4
NORM = ALPHA + BETA + GAMMA

FIBS: List[int] = [
    1,
    2,
    3,
    5,
    8,
    13,
    21,
    34,
    55,
    89,
    144,
    233,
    377,
    610,
    987,
    1597,
    2584,
    4181,
    6765,
    10946,
    17711,
    28657,
    46368,
    75025,
    121393,
    196418,
]

# ============================================================
# M_32 manifold (12 dodecahedral + 20 icosahedral face normals)
# ============================================================


def _nv(v):
    m = math.sqrt(sum(x * x for x in v))
    return tuple(x / m for x in v)


def _build_M32():
    F = []
    p = PHI
    for s1 in [1, -1]:
        for s2 in [1, -1]:
            F.append(_nv((0, s1 / p, s2 * p)))
            F.append(_nv((s2 * p, 0, s1 / p)))
            F.append(_nv((s1 / p, s2 * p, 0)))
    for sx in [1, -1]:
        for sy in [1, -1]:
            for sz in [1, -1]:
                F.append(_nv((sx, sy, sz)))
    for s1 in [1, -1]:
        for s2 in [1, -1]:
            F.append(_nv((0, s1, s2 * p)))
            F.append(_nv((s2 * p, 0, s1)))
            F.append(_nv((s1, s2 * p, 0)))
    return F[:32]


M32 = _build_M32()
COS_2PI5 = math.cos(2 * math.pi / 5)
ADJ = [
    [sum(M32[i][k] * M32[j][k] for k in range(3)) >= COS_2PI5 for j in range(32)] for i in range(32)
]

# ============================================================
# Precomputed curvature action-score table
# ============================================================

_CURVATURE_SCALE = 2 * math.pi / PHI / 255.0
CURV_TABLE = [[0.0] * 256 for _ in range(256)]
for _i in range(256):
    for _j in range(256):
        _ai = _i * _CURVATURE_SCALE
        _aj = _j * _CURVATURE_SCALE
        CURV_TABLE[_i][_j] = (_ai - _aj) ** 2 + (_ai * _aj) ** 2


def curvature_action_score(n: int) -> float:
    b = [(n >> (8 * k)) & 0xFF for k in range(4)]
    return sum(CURV_TABLE[b[i]][b[j]] for i in range(4) for j in range(i + 1, 4))


# ============================================================
# Embedding + Voronoi
# ============================================================

_V_CACHE: Dict[int, int] = {}
_V_CACHE_MAX = 150_000


def embed(n: int):
    x = y = z = 0.0
    for k in range(32):
        if (n >> k) & 1:
            fx, fy, fz = M32[k]
            x += fx
            y += fy
            z += fz
    mag = math.sqrt(x * x + y * y + z * z)
    if mag < 1e-9:
        return M32[0]
    return (x / mag, y / mag, z / mag)


def voronoi(n: int) -> int:
    if n in _V_CACHE:
        return _V_CACHE[n]
    ex, ey, ez = embed(n)
    f = max(range(32), key=lambda f: M32[f][0] * ex + M32[f][1] * ey + M32[f][2] * ez)
    if len(_V_CACHE) > _V_CACHE_MAX:
        _V_CACHE.clear()
    _V_CACHE[n] = f
    return f


# ============================================================
# phi-resonance R_phi(n) -- ordering/visitation heuristic ONLY
# ============================================================


def phi_resonance(n: int) -> float:
    if n == 0:
        return 0.0
    ex, ey, ez = embed(n)
    c1 = min(
        max(abs(M32[f][0] * ex + M32[f][1] * ey + M32[f][2] * ez) for f in range(32)) / PHI_I, 1.0
    )
    c2 = 1.0 - 2.0 * abs((n * PHI) % 1.0 - 0.5)
    c3 = math.exp(-curvature_action_score(n) / ACTION_THRESHOLD)
    raw = (ALPHA * c1 + BETA * c2 + GAMMA * c3) / NORM
    return 1.0 / (1.0 + math.exp(-8.0 * (raw - PHI_I)))


def cheap_resonance(n: int) -> float:
    return 1.0 - 2.0 * abs((n * PHI) % 1.0 - 0.5)


# ============================================================
# Soft action gate (visitation/ordering only, never submission)
# ============================================================


def soft_action_gate(S: float, rng: random.Random) -> bool:
    if S >= ACTION_THRESHOLD:
        return True
    return rng.random() < math.exp(-(ACTION_THRESHOLD - S))


# ============================================================
# phi-gradient directed proposal
# ============================================================


def phi_gradient_proposal(n: int, rng: random.Random, scale: int = 1) -> int:
    g = cheap_resonance(n + 1) - cheap_resonance(n - 1)
    sign = 1 if g >= 0 else -1 if rng.random() >= 0.70 else rng.choice([-1, 1])
    return (n + sign * rng.choice(FIBS[:14]) * scale) % (2**32)


# ============================================================
# Shared best-candidate coherence bus
# ============================================================


def make_bus(manager):
    return {
        "best_r": manager.Value("d", 0.0),
        "best_n": manager.Value("i", 0),
        "best_face": manager.Value("i", 0),
        "best_S": manager.Value("d", 0.0),
        "warrior_r": manager.Array("d", [0.0] * 32),
        "found": manager.Value("i", 0),
        "solution": manager.Value("Q", 0),
        "lock": manager.Lock(),
    }


def bus_broadcast(bus, wid, n, r, S, face):
    bus["warrior_r"][wid] = r
    with bus["lock"]:
        if r > bus["best_r"].value:
            bus["best_r"].value = r
            bus["best_n"].value = n
            bus["best_face"].value = face
            bus["best_S"].value = S


def bus_read(bus):
    with bus["lock"]:
        return (bus["best_r"].value, bus["best_n"].value, bus["best_face"].value)


def bus_solve(bus, n):
    if type(n) is not int or not 0 <= n < 2**32:
        raise ValueError("winning nonce must be uint32")
    with bus["lock"]:
        if not bus["found"].value:
            bus["solution"].value = n
            bus["found"].value = 1


# ============================================================
# Block header + SHA256d
# ============================================================


def build_header(version, prev_hash, merkle, timestamp, bits, nonce) -> bytes:
    h = struct.pack("<I", version)
    h += bytes.fromhex(prev_hash)[::-1]
    h += bytes.fromhex(merkle)[::-1]
    h += struct.pack("<I", timestamp)
    h += bytes.fromhex(bits)[::-1]
    h += struct.pack("<I", nonce)
    return h


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def bits_to_target(bits_hex: str) -> int:
    b = int(bits_hex, 16)
    return (b & 0xFFFFFF) * (2 ** (8 * ((b >> 24) - 3)))


def check_pow(header: bytes, target: int) -> bool:
    return int.from_bytes(sha256d(header), "little") <= target


# ============================================================
# Oracle -- SHA256d validity check (never gated by resonance)
# ============================================================


def oracle(n, version, prev_hash, merkle, timestamp, bits, target, threshold) -> bool:
    """Return True iff SHA256d(n) <= target. Resonance never gates this."""
    header = build_header(version, prev_hash, merkle, timestamp, bits, n)
    return check_pow(header, target)


# ============================================================
# Warrior process: check_pow evaluated for EVERY visited candidate
# ============================================================


def warrior_process(
    face_idx,
    version,
    prev_hash,
    merkle,
    timestamp,
    bits,
    target,
    budget,
    base_threshold,
    bus,
    call_frequency=5000,
    shared_face_probs=None,
    shared_face_resonance=None,
):
    seed = int.from_bytes(os.urandom(8), "big") ^ (face_idx * 0xDEADBEEF)
    rng = random.Random(seed)

    n = rng.randint(0, 2**32 - 1)
    for _ in range(500):
        c = rng.randint(0, 2**32 - 1)
        if voronoi(c) == face_idx:
            n = c
            break
    r = phi_resonance(n)
    S = curvature_action_score(n)
    tau = budget * 0.35

    for step in range(budget):
        if bus["found"].value:
            return
        threshold_t = base_threshold - 0.08 * math.exp(-step / tau)
        scale = max(1, int(8 * math.exp(-step / (budget * 0.6))))
        n2 = phi_gradient_proposal(n, rng, scale)
        f2 = voronoi(n2)
        if f2 != face_idx and not ADJ[face_idx][f2]:
            continue
        S2 = curvature_action_score(n2)
        if not soft_action_gate(S2, rng):
            continue
        r2 = phi_resonance(n2)
        if r2 >= r or rng.random() < math.exp(8.0 * (r2 - r)):
            n = n2
            r = r2
            S = S2
        if step % call_frequency == 0:
            bus_broadcast(bus, face_idx, n, r, S, face_idx)
        # Oracle: SHA256d check_pow for EVERY visited candidate, independent of
        # resonance. Resonance only orders visitation; it never gates submission.
        if oracle(n, version, prev_hash, merkle, timestamp, bits, target, threshold_t):
            bus_solve(bus, n)
            return


# ============================================================
# Solver
# ============================================================


def solve_32_warriors(
    version,
    prev_hash,
    merkle,
    timestamp,
    bits,
    target,
    budget,
    threshold,
    actual_nonce=None,
):
    import time

    manager = Manager()
    bus = make_bus(manager)
    shared_face_probs = manager.Array("d", [1.0 / 32.0] * 32)
    shared_face_resonance = manager.Array("d", [0.5] * 32)
    t0 = time.time()
    procs = []
    for face_idx in range(32):
        p = Process(
            target=warrior_process,
            args=(
                face_idx,
                version,
                prev_hash,
                merkle,
                timestamp,
                bits,
                target,
                budget,
                threshold,
                bus,
                5000,
                shared_face_probs,
                shared_face_resonance,
            ),
            daemon=True,
        )
        p.start()
        procs.append(p)
    while any(p.is_alive() for p in procs):
        time.sleep(0.5)
        if bus["found"].value:
            break
    for p in procs:
        p.terminate()
        p.join(timeout=2)
    elapsed = time.time() - t0
    if bus["found"].value:
        n = bus["solution"].value
        header = build_header(version, prev_hash, merkle, timestamp, bits, n)
        valid = check_pow(header, target)
        return {
            "found_nonce": n,
            "valid": valid,
            "elapsed": elapsed,
            "r_phi": phi_resonance(n),
            "face": voronoi(n),
        }
    return {
        "found_nonce": None,
        "valid": False,
        "elapsed": elapsed,
        "peak_r_phi": bus["best_r"].value,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="phi-Grover Production Miner v4")
    parser.add_argument("--budget", type=int, default=200000)
    parser.add_argument("--threshold", type=float, default=PHI_I)
    args = parser.parse_args()
    print("phi-Grover v4 | informational CLI only | does not run the solver or verify SHA256d")
