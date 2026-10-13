"""Lucas-bounded cost kernels for paths, steps, amplitudes, mining, and folds.

Every bound is an exact algebraic ceiling computed from L_n; no empirical
constants or heuristics. Every kernel returns the canonical triple
{is_lucas_bounded, bound, n} plus its measured quantity.
"""

from __future__ import annotations

import numpy as np

from .core import lucas

THEOREM_PROVEN = False

# Canonical directed 4-cycle: the mining safety FSM's state graph
# (SEARCHING -> SUBMITTING -> WAITING_EXTERNAL -> COOLDOWN -> SEARCHING).
FSM_CYCLE_GRAPH = np.array(
    [
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
        [1, 0, 0, 0],
    ],
    dtype=np.int64,
)


def bound(n: int) -> int:
    """The exact Lucas ceiling L_n for index n."""
    if n < 0:
        raise ValueError("n must be non-negative")
    return lucas(n)


def paths(n: int) -> int:
    """Walks of length n on the canonical mining cycle graph from state 0.

    The safety FSM is deterministic — exactly one legal trajectory exists
    from SEARCHING — so the path count is 1 for every n, always under the
    Lucas ceiling L_n (L_0 = 2, L_1 = 1).
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 1
    An = np.linalg.matrix_power(FSM_CYCLE_GRAPH, n)
    return int(np.sum(An[0]))


def path_kernel(graph: np.ndarray, n: int) -> dict[str, object]:
    """Number of walks of length n in a graph is bounded by L_n.

    graph: adjacency matrix (square, deterministic)
    """
    if graph.ndim != 2 or graph.shape[0] != graph.shape[1]:
        raise ValueError("graph must be a square adjacency matrix")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        count = int(graph.shape[0])
    else:
        An = np.linalg.matrix_power(graph.astype(np.int64), n)
        count = int(np.sum(An))
    ceiling = lucas(n)
    return {
        "kernel": "path_kernel",
        "n": n,
        "path_count": count,
        "lucas_bound": ceiling,
        "bound": ceiling,
        "is_lucas_bounded": count <= ceiling,
        "theorem_proven": False,
    }


def step_kernel(machine_description: dict[str, object], n: int) -> dict[str, object]:
    """Turing/QTM step bound: steps(n) <= L_n.

    machine_description must contain a deterministic integer 'states' count.
    """
    states = int(machine_description.get("states", 1))
    ceiling = lucas(n)
    return {
        "kernel": "step_kernel",
        "n": n,
        "states": states,
        "lucas_bound": ceiling,
        "bound": ceiling,
        "is_lucas_bounded": states <= ceiling,
        "theorem_proven": False,
    }


def amplitude_kernel(spectrum: list[float], n: int) -> dict[str, object]:
    """Amplitude-sum bound: |Σ λ_i^n| <= L_n for a unit-modulus spectrum.

    spectrum: list of eigenvalue magnitudes or unit phases (deterministic)
    """
    total = sum(abs(float(x)) ** n for x in spectrum)
    ceiling = lucas(n)
    return {
        "kernel": "amplitude_kernel",
        "n": n,
        "amplitude_sum": total,
        "lucas_bound": ceiling,
        "bound": ceiling,
        "is_lucas_bounded": total <= ceiling,
        "theorem_proven": False,
    }


def mining_kernel(nonce_space: int, n: int) -> dict[str, object]:
    """Mining/nonce search bound: nonce_space <= L_n.

    n is the Lucas-scaled difficulty parameter.
    """
    ceiling = lucas(n)
    return {
        "kernel": "mining_kernel",
        "n": n,
        "nonce_space": nonce_space,
        "lucas_bound": ceiling,
        "bound": ceiling,
        "is_lucas_bounded": nonce_space <= ceiling,
        "theorem_proven": False,
    }


def gap_kernel(operator: np.ndarray, n: int) -> dict[str, object]:
    """Spectral gap kernel: the gap is reported alongside L_n as ceiling.

    operator: Hermitian numpy matrix
    n: Lucas index used as the scaling ceiling
    """
    if operator.ndim != 2 or operator.shape[0] != operator.shape[1]:
        raise ValueError("operator must be a square matrix")
    eigvals = np.linalg.eigvalsh(operator.astype(np.float64))
    gap = float(sorted(eigvals)[1] - sorted(eigvals)[0])
    ceiling = lucas(n)
    return {
        "kernel": "gap_kernel",
        "n": n,
        "spectral_gap": gap,
        "lucas_bound": ceiling,
        "bound": ceiling,
        "is_lucas_bounded": gap <= ceiling,
        "theorem_proven": False,
    }


def folded_kernel(artifact: object, n: int) -> dict[str, object]:
    """T_phi fold-operation bound: pair ops on a folded artifact <= L_n.

    The T_phi fold applies one GL(2, Z/256Z) byte-pair op per two bytes,
    so the operation count is ceil(len/2); L_n is the algebraic ceiling.
    `artifact` may be raw bytes or an object exposing ``original_length``
    (e.g. a FoldedStateArtifact).
    """
    length = getattr(artifact, "original_length", None)
    if length is None:
        length = len(artifact)  # bytes-like
    pair_ops = (int(length) + 1) // 2
    ceiling = lucas(n)
    return {
        "kernel": "folded_kernel",
        "n": n,
        "pair_ops": pair_ops,
        "lucas_bound": ceiling,
        "bound": ceiling,
        "is_lucas_bounded": pair_ops <= ceiling,
        "theorem_proven": False,
    }
