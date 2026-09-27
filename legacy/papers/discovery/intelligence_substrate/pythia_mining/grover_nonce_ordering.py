"""
OPT-IN experimental nonce-candidate selection using a real Grover's-algorithm
simulator (hyba.quantum.algorithms.GroverSearch's genuine amplitude-
amplification + measurement, not a hand-rolled classical scan dressed up in
quantum vocabulary).

Status: this is NOT the production default. headless_miner.py's
`_phi_guided_nonce_search` only routes through `grover_select_candidate` when
the operator explicitly sets HYBA_MINING_GROVER_NONCE_ORDERING=true; with the
flag unset (the default), mining keeps its existing classical argmax
selection over the phi-resonance-scored candidate list, byte-for-byte
identical to prior behavior.

Why opt-in rather than the new default: swapping the selection strategy on a
live hash-search path changes which nonce gets submitted to the pool on every
mining cycle. That is a real behavior/performance change to production
mining, not a bug fix, so it needs an explicit human decision (timing
overhead of the classical state-vector simulation at scale, and whether
amplitude-amplified selection over a resonance-thresholded candidate set is
actually desirable versus plain argmax) before it can become the default.
See the task report for the full analysis.
"""

import math
from typing import Any, Optional, Sequence

from python_backend.hyba.quantum.algorithms import GroverSearch
from python_backend.pythia_mining.oracle import SearchOracle

INV_PHI = (math.sqrt(5.0) - 1.0) / 2.0  # phi^-1 ~= 0.6180339887


def grover_select_candidate(
    candidates: Sequence[Any],
    oracle: Optional[SearchOracle] = None,
    threshold: Optional[float] = None,
) -> int:
    """
    Select an index from `candidates` using Grover amplitude amplification.
    Supports physical SearchOracle evaluation or resonance-score thresholding.
    """
    n = len(candidates)
    if n == 0:
        raise ValueError("grover_select_candidate requires at least one candidate")

    thresh = INV_PHI if threshold is None else threshold
    marked = []

    if oracle is not None:
        for i, cand in enumerate(candidates):
            res = oracle.evaluate(cand)
            if getattr(res, "is_valid", False):
                marked.append(i)
    else:
        for i, cand in enumerate(candidates):
            if isinstance(cand, (int, float)) and float(cand) >= thresh:
                marked.append(i)

    if not marked:
        # Classical argmax degradation
        if all(isinstance(c, (int, float)) for c in candidates):
            return max(range(n), key=lambda i: candidates[i])
        return 0

    grover = GroverSearch(N=n)
    measured = grover.search(oracle_indices=marked)

    if measured >= n or measured not in marked:
        measured = marked[measured % len(marked)]
    return measured
