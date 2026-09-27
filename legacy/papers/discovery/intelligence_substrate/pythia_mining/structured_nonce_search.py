"""[EXPERIMENTAL RESEARCH STRATEGY - INACTIVE IN PRODUCTION RUNTIME]
Propose mining nonces from structured Lucas attractor math — standalone research strategy.

STATUS:
  - Inactive in canonical production mining loop (which is owned strictly by
    `AgenticMiningIntegration` -> `ManifoldPoolCoordinator`).
  - Preserved for experimental property benchmarks and invariant verification.

Uses:
- LucasSearchAttractor (Pisot collapse / attractor scores)
- GroverSearch (hyba.quantum.algorithms) — substrate-agnostic
- M_32 face amplitudes from FirstPrinciplesQuantumSubstrate

SHA256d is the pool proof, not the search.
"""

from __future__ import annotations

import math
from typing import List, Sequence

from python_backend.hyba.quantum.algorithms import GroverSearch
from python_backend.mathematical_foundation.lucas_search_attractor import (
    LucasSearchAttractor,
    lucas_conditioned_nonce_score,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI = 1.0 / PHI
FACES = 32
NONCE_STRIDE = 0x100000000 // FACES


def _structured_candidates(seed: int, face_probs: Sequence[float], depth: int = 16) -> List[int]:
    attractor = LucasSearchAttractor(attractor_depth=max(depth, 16))
    lucas_nodes = [L for L in attractor.lucas_targets if L > 0]
    seen = set()
    out: List[int] = []
    ranked_faces = sorted(
        range(min(FACES, len(face_probs))), key=lambda i: face_probs[i], reverse=True
    )
    for face in ranked_faces:
        base = (seed + face * NONCE_STRIDE) & 0xFFFFFFFF
        for L in lucas_nodes:
            nonce = (base + L) & 0xFFFFFFFF
            if nonce not in seen:
                seen.add(nonce)
                out.append(nonce)
            folded = (base + int(L * PHI) + face) & 0xFFFFFFFF
            if folded not in seen:
                seen.add(folded)
                out.append(folded)
    for L in lucas_nodes:
        nonce = L & 0xFFFFFFFF
        if nonce not in seen:
            seen.add(nonce)
            out.append(nonce)
    return out


def _scores(nonces: Sequence[int]) -> List[float]:
    attractor = LucasSearchAttractor(attractor_depth=21)
    try:
        from python_backend.phi_grover_v4 import phi_resonance
    except ImportError:
        phi_resonance = None
    out = []
    for n in nonces:
        s = lucas_conditioned_nonce_score(int(n), attractor)
        if phi_resonance is not None:
            s = 0.5 * s + 0.5 * float(phi_resonance(int(n)))
        out.append(s)
    return out


def grover_order(
    nonces: Sequence[int], scores: Sequence[float], threshold: float = INV_PHI
) -> List[int]:
    """Amplitude-amplify marked (structured) indices, then return nonces in Grover-first order."""
    n = len(nonces)
    if n == 0:
        return []
    marked = [i for i, s in enumerate(scores) if s >= threshold]
    if not marked:
        marked = [max(range(n), key=lambda i: scores[i])]
    # GroverSearch's exact-rational rewrite dropped the use_golden_scaling knob;
    # its iteration count is now the standard pi/4 * sqrt(N/M), which is what
    # use_golden_scaling=True computed anyway at structure_parameter 0.
    grover = GroverSearch(N=n)
    measured = grover.search(oracle_indices=marked)
    if measured >= n or measured not in marked:
        measured = marked[measured % len(marked)]
    ordered = [int(nonces[measured])]
    for i in sorted(marked, key=lambda j: scores[j], reverse=True):
        nonce = int(nonces[i])
        if nonce not in ordered:
            ordered.append(nonce)
    return ordered


def propose_nonces(
    seed: int,
    face_probs: Sequence[float],
    limit: int = 512,
) -> List[int]:
    """Structured candidates, Grover-ordered. No GPU. No difficulty input."""
    candidates = _structured_candidates(seed, face_probs)
    scores = _scores(candidates)
    ordered = grover_order(candidates, scores)
    return ordered[: max(1, limit)]
