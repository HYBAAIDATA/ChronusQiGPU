# pythagoras/asi/manifold_bridge.py — NEW

"""Shared adapter between the 11D Poincaré-Golden substrate and the ASI schools.

The substrate ``Intelligence/poincare_golden_11d.py`` endows R^11 with the
golden-weighted Poincaré metric

    ds^2 = 4 * sum_i phi^{-(i+1)} dx_i^2 / (1 - ||x||_phi^2)^2

on the open ball B_phi^11 = {x : ||x||_phi^2 < 1}, where
||x||_phi^2 = sum_i phi^{-(i+1)} x_i^2.

Exact isometry used everywhere below: the diagonal rescaling

    y_i = phi^{-(i+1)/2} * x_i   (i.e. y = S x, S = diag(sqrt(PHI_POWERS)))

maps B_phi^11 onto the *standard* Poincaré ball B^11 and conjugates the
golden metric into ds^2 = 4|dy|^2 / (1-|y|^2)^2 (curvature -1). The
substrate's ``poincare_golden_distance`` is exactly the standard Poincaré
distance in y-coordinates, so all geodesic operations below (Möbius
addition, exponential map, Riemannian gradient) are the genuine
curvature -1 operators transported through this isometry — not
approximations.

This module is the only new shared dependency for the S-2 / S-3 / S-11
elevations. Nothing here mutates the substrate; every function is a
pure lift/project adapter.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np

try:
    from toe.poincare_golden_11d import (
        PHI_POWERS,
        PoincareFoldedArray,
        compute_poincare_norm_sq,
        fold_poincare_11d_vector,
        unfold_poincare_11d_vector,
    )
except ImportError:  # direct execution / embedded interpreter
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    from toe.poincare_golden_11d import (
        PHI_POWERS,
        PoincareFoldedArray,
        compute_poincare_norm_sq,
        fold_poincare_11d_vector,
        unfold_poincare_11d_vector,
    )


MANIFOLD_DIM = 11
GOLDEN_SCALE = np.sqrt(PHI_POWERS)  # S_ii = phi^{-(i+1)/2}
_LN2 = math.log(2.0)


# ---------------------------------------------------------------------------
# Coordinate transport: ambient R^11 <-> golden ball <-> standard ball
# ---------------------------------------------------------------------------


def as_ball_vector(state: np.ndarray) -> np.ndarray:
    """Coerce ``state`` to an 11-D point inside the golden ball B_phi^11.

    Contract:
      - PoincareFoldedArray (already folded) -> returned with its exact
        preimage payload intact (roundtrip < 1e-14 preserved).
      - length-11 array with ||x||_phi^2 < 1   -> treated as a ball point;
        its closed-form preimage is attached so the lift/project
        roundtrip stays at machine epsilon.
      - length-11 array with ||x||_phi^2 >= 1 -> treated as an ambient
        vector and folded through the exact Klein contraction.
      - anything else -> ValueError.
    """
    arr = np.asarray(state, dtype=np.float64)
    if arr.ndim != 1 or arr.size != MANIFOLD_DIM:
        raise ValueError(
            f"manifold state must be a length-{MANIFOLD_DIM} vector, got shape {arr.shape}"
        )
    if isinstance(state, PoincareFoldedArray):
        return state
    if compute_poincare_norm_sq(arr) < 1.0:
        ball = arr.view(PoincareFoldedArray)
        n = compute_poincare_norm_sq(arr)
        ball._poincare_preimage = arr / math.sqrt(max(1e-15, 1.0 - n))
        return ball
    folded, _ = fold_poincare_11d_vector(arr)
    return folded


def standardize(x_golden: np.ndarray) -> np.ndarray:
    """Isometry B_phi^11 -> B^11:  y = S x.  |y|^2 == ||x||_phi^2 exactly."""
    return GOLDEN_SCALE * np.asarray(x_golden, dtype=np.float64).reshape(MANIFOLD_DIM)


def goldenize(y_standard: np.ndarray) -> np.ndarray:
    """Inverse isometry B^11 -> B_phi^11:  x = S^{-1} y."""
    return np.asarray(y_standard, dtype=np.float64).reshape(MANIFOLD_DIM) / GOLDEN_SCALE


def unstandardize(y_standard: np.ndarray) -> np.ndarray:
    """Alias of :func:`goldenize` (interface-map name).

    Inverse isometry B^11 -> B_phi^11:  x = S^{-1} y, exact.
    """
    return goldenize(y_standard)


def unfold_ball_vector(x_golden: np.ndarray) -> np.ndarray:
    """Ambient preimage u = x / sqrt(1 - ||x||_phi^2) (exact diffeomorphism)."""
    return unfold_poincare_11d_vector(as_ball_vector(x_golden))


def fold_ambient_vector(u: np.ndarray) -> np.ndarray:
    """Ambient R^11 -> B_phi^11 via the substrate's exact Klein contraction.

    Returns the PoincareFoldedArray (preimage payload preserved), so the
    unfold project/lift roundtrip remains bit-exact.
    """
    folded, _ = fold_poincare_11d_vector(np.asarray(u, dtype=np.float64))
    return folded


def lift_state(u: np.ndarray) -> np.ndarray:
    """Alias of :func:`fold_ambient_vector` (interface-map name).

    Ambient R^11 -> B_phi^11 via the substrate's exact Klein contraction.
    Returns the PoincareFoldedArray (preimage payload preserved), so the
    lift/project roundtrip remains bit-exact (< 1e-14).
    """
    return fold_ambient_vector(u)


def project_state(x_golden: np.ndarray) -> np.ndarray:
    """Alias of :func:`unfold_ball_vector` (interface-map name).

    Ball B_phi^11 -> ambient preimage u = x / sqrt(1 - ||x||_phi^2),
    the exact Klein diffeomorphism inverse.
    """
    return unfold_ball_vector(x_golden)


def unfold_jacobian(x_golden: np.ndarray) -> np.ndarray:
    """Jacobian J = d(u)/d(x) of the unfolding u = x / sqrt(1 - ||x||_phi^2).

    With s = (1 - n)^{-1/2}, n = ||x||_phi^2, w_i = phi^{-(i+1)}:
        J_ij = s * delta_ij + s^3 * w_j * x_i * x_j
    A diagonal matrix plus a rank-1 update — exact, O(11^2).
    """
    x = np.asarray(x_golden, dtype=np.float64).reshape(MANIFOLD_DIM)
    n = compute_poincare_norm_sq(x)
    s = 1.0 / math.sqrt(max(1e-15, 1.0 - min(n, 1.0 - 1e-15)))
    return s * np.eye(MANIFOLD_DIM) + (s**3) * np.outer(x, PHI_POWERS * x)


# ---------------------------------------------------------------------------
# Genuine Poincaré geodesic operators (curvature -1, standard ball coords)
# ---------------------------------------------------------------------------


def mobius_add(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Möbius addition on the standard Poincaré ball (curvature -1)."""
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    uv = float(np.dot(u, v))
    uu = float(np.dot(u, u))
    vv = float(np.dot(v, v))
    num = (1.0 + 2.0 * uv + vv) * u + (1.0 - uu) * v
    den = 1.0 + 2.0 * uv + uu * vv
    return num / den


def exp_map(y: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Riemannian exponential map exp_y(v) on the standard Poincaré ball.

    exp_y(v) = y ⊕ ( tanh(lambda_y |v| / 2) * v / |v| ),
    lambda_y = 2 / (1 - |y|^2).  Exact geodesic flow, curvature -1.
    """
    y = np.asarray(y, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    v_norm = float(np.linalg.norm(v))
    if v_norm < 1e-15:
        return y.copy()
    lam = 2.0 / max(1e-15, 1.0 - float(np.dot(y, y)))
    return mobius_add(y, math.tanh(lam * v_norm / 2.0) * v / v_norm)


def log_map(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Riemannian logarithm log_y(z): tangent at y reaching z along a geodesic."""
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    diff = mobius_add(-y, z)
    d = float(np.linalg.norm(diff))
    if d < 1e-15:
        return np.zeros_like(y)
    lam = 2.0 / max(1e-15, 1.0 - float(np.dot(y, y)))
    return (2.0 / lam) * math.atanh(min(d, 1.0 - 1e-15)) * diff / d


def riemannian_gradient(euclidean_grad: np.ndarray, y_standard: np.ndarray) -> np.ndarray:
    """Convert a Euclidean gradient to the Riemannian gradient on B^11.

    For the conformal metric g = lambda^2 g_E, grad_R F = lambda^{-2} grad_E F,
    lambda_y = 2 / (1 - |y|^2).  Exact — no discretisation.
    """
    y = np.asarray(y_standard, dtype=np.float64)
    lam = 2.0 / max(1e-15, 1.0 - float(np.dot(y, y)))
    return np.asarray(euclidean_grad, dtype=np.float64) / (lam * lam)


def geodesic_descent_step(
    x_golden: np.ndarray,
    grad_x: np.ndarray,
    step_size: float,
) -> np.ndarray:
    """One Riemannian gradient step on the golden ball.

    grad_x is the Euclidean gradient of F in golden coordinates. The step is
        x' = S^{-1} exp_{Sx}( -step * grad_R F )
    where grad_R F = ((1-|y|^2)/2)^2 * S^{-1} grad_x  (chain rule y = S x
    composed with the conformal-factor gradient).  The exponential map keeps
    the iterate strictly inside the ball by construction.
    """
    y = standardize(x_golden)
    grad_y = np.asarray(grad_x, dtype=np.float64).reshape(MANIFOLD_DIM) / GOLDEN_SCALE
    g_r = riemannian_gradient(grad_y, y)
    return goldenize(exp_map(y, -step_size * g_r))


def geodesic_towards(
    x_golden: np.ndarray, target_golden: np.ndarray, gamma: float = 1.0
) -> np.ndarray:
    """Move ``gamma`` of the way from x to target along their geodesic.

    x' = exp_x(gamma * log_x(target)) in standard-ball coordinates — the
    exact curvature -1 geodesic interpolation (gamma=1 lands on target).
    """
    y = standardize(as_ball_vector(x_golden))
    y_t = standardize(as_ball_vector(target_golden))
    return goldenize(exp_map(y, gamma * log_map(y, y_t)))


def geodesic_descent(
    x0_golden: np.ndarray,
    objective_fn: Callable[[np.ndarray], float],
    grad_fn: Callable[[np.ndarray], np.ndarray],
    step_size: float = 0.5,
    tol: float = 1e-10,
    max_steps: int = 512,
) -> Tuple[np.ndarray, Dict[str, object]]:
    """Riemannian gradient descent on B_phi^11 with Armijo backtracking.

    Each iterate is produced by :func:`geodesic_descent_step`; if a step would
    increase the objective the step size is halved (standard monotone line
    search), so the free-energy history is non-increasing by construction.

    Returns (x*, info) with info keys: free_energy_history, converged,
    steps, final_free_energy, riemannian_grad_norm.
    """
    x = as_ball_vector(x0_golden)
    f = float(objective_fn(x))
    history = [f]
    step = float(step_size)
    converged = False
    last_rg_norm = float("inf")
    for _ in range(int(max_steps)):
        grad = np.asarray(grad_fn(x), dtype=np.float64).reshape(MANIFOLD_DIM)
        y = standardize(x)
        last_rg_norm = float(np.linalg.norm(riemannian_gradient(grad / GOLDEN_SCALE, y)))
        if last_rg_norm < tol:
            converged = True
            break
        x_next = geodesic_descent_step(x, grad, step)
        f_next = float(objective_fn(x_next))
        while f_next > f and step > 1e-12:
            step *= 0.5
            x_next = geodesic_descent_step(x, grad, step)
            f_next = float(objective_fn(x_next))
        if f_next > f:
            break  # cannot descend further along this geodesic direction
        if abs(f - f_next) < tol * (1.0 + abs(f)):
            converged = True
            x, f = x_next, f_next
            history.append(f)
            break
        x, f = x_next, f_next
        history.append(f)
        step = min(step * 1.5, 4.0)  # grow step after a successful descent
    return x, {
        "free_energy_history": history,
        "converged": converged,
        "steps": len(history) - 1,
        "final_free_energy": f,
        "riemannian_grad_norm": last_rg_norm,
    }


# ---------------------------------------------------------------------------
# State -> structure projections (shared by S-2, S-3, S-11)
# ---------------------------------------------------------------------------


def state_to_covariance(state: np.ndarray, regularization: float = 1e-9) -> np.ndarray:
    """Golden-geometry-aware covariance of a manifold state.

    Two input modes:
      - length-11 state: instantaneous second-moment Sigma = y y^T + eps I
        in standardised (isometric) coordinates — a genuine PSD matrix whose
        off-diagonals are the coordinate couplings induced by the state.
      - (T x 11) sample matrix: empirical covariance of the standardised
        rows + eps I.
    """
    arr = np.asarray(state, dtype=np.float64)
    if arr.ndim == 2 and arr.shape[1] == MANIFOLD_DIM:
        y = arr * GOLDEN_SCALE
        y = y - y.mean(axis=0, keepdims=True)
        cov = (y.T @ y) / max(arr.shape[0] - 1, 1)
        return cov + regularization * np.eye(MANIFOLD_DIM)
    y = standardize(as_ball_vector(arr))
    return np.outer(y, y) + regularization * np.eye(MANIFOLD_DIM)


def state_to_graph(state: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
    """Project a manifold state to a DAG adjacency matrix A in {0,1}^{11x11}.

    Nodes are the 11 golden dimensions. The coordinate coupling |Sigma_ij|
    (from :func:`state_to_covariance`) defines edge strength; an edge i -> j
    is kept when |Sigma_ij| exceeds the threshold (default: the median
    off-diagonal coupling). Edges are oriented low-index -> high-index,
    matching the golden hierarchy in which dim 0 carries weight phi^{-1},
    the dominant scale. Index orientation makes the result acyclic by
    construction — a genuine DAG derived from the state.
    """
    cov = state_to_covariance(state)
    coupling = np.abs(cov)
    off = [coupling[i, j] for i in range(MANIFOLD_DIM) for j in range(i + 1, MANIFOLD_DIM)]
    tau = float(np.median(off)) if threshold is None else float(threshold)
    adj = np.zeros((MANIFOLD_DIM, MANIFOLD_DIM), dtype=np.float64)
    for i in range(MANIFOLD_DIM):
        for j in range(i + 1, MANIFOLD_DIM):
            if coupling[i, j] > tau:
                adj[i, j] = coupling[i, j]
    return adj


def adjacency_to_digraph(adjacency: np.ndarray):
    """Optional convenience: adjacency matrix -> networkx.DiGraph.

    networkx is optional (the ``graph`` extra); this is a thin view.
    """
    import networkx as nx

    adj = np.asarray(adjacency, dtype=np.float64)
    graph = nx.DiGraph()
    graph.add_nodes_from(range(adj.shape[0]))
    for i, j in zip(*np.nonzero(adj)):
        graph.add_edge(int(i), int(j), weight=float(adj[i, j]))
    return graph


def golden_smoothing_kernel() -> np.ndarray:
    """Row-stochastic golden-weighted tridiagonal averaging kernel K.

    K u computes a weighted moving average over the dimension lattice with
    weights phi^{-(i+1)} — a diffusion / coarse-graining operator, one
    exact step per hierarchy level.  S-11 uses K as the layer-wise
    generative map g(u_{l+1}) = K u_{l+1} on ambient coordinates.
    """
    w = PHI_POWERS
    k = np.zeros((MANIFOLD_DIM, MANIFOLD_DIM), dtype=np.float64)
    for i in range(MANIFOLD_DIM):
        idxs = [j for j in (i - 1, i, i + 1) if 0 <= j < MANIFOLD_DIM]
        total = sum(float(w[j]) for j in idxs)
        for j in idxs:
            k[i, j] = float(w[j]) / total
    return k


def state_to_prior_layers(state: np.ndarray, depth: int) -> List[np.ndarray]:
    """Hierarchical coarse-graining of a manifold state.

    Layer 0 is the ball point itself (sensory level). Each deeper layer is
    the golden-weighted diffusion of the previous layer's ambient
    coordinates, refolded into the ball — so every layer is itself a valid
    B_phi^11 state and deeper layers are progressively smoother priors.
    """
    if depth < 1:
        return []
    x = as_ball_vector(state)
    layers = [x]
    k = golden_smoothing_kernel()
    u = unfold_ball_vector(x)
    for _ in range(depth - 1):
        u = k @ u
        layers.append(fold_ambient_vector(u))
    return layers


def scalar_projection(tensor: np.ndarray) -> float:
    """Canonical dual-mode scalar projection used by every elevated school.

    - length-11 vector -> ||x||_phi^2 (folded first if outside the ball),
      a deterministic scalar in [0, 1) for ball states.
    - matrix           -> squared Frobenius norm.
    - other arrays     -> sum of squares of the flattened array.
    """
    arr = np.asarray(tensor, dtype=np.float64)
    if arr.ndim == 1 and arr.size == MANIFOLD_DIM:
        return compute_poincare_norm_sq(as_ball_vector(arr))
    return float(np.sum(arr**2))


# ---------------------------------------------------------------------------
# DAG utilities for the S-2 elevation
# ---------------------------------------------------------------------------


def topological_sort(adjacency: np.ndarray) -> List[int]:
    """Kahn's algorithm over an adjacency matrix A[i, j] == edge i -> j.

    Raises ValueError if the graph contains a cycle.
    """
    adj = np.asarray(adjacency)
    n = adj.shape[0]
    in_degree = np.count_nonzero(adj != 0, axis=0).astype(int)
    queue = [i for i in range(n) if in_degree[i] == 0]
    order: List[int] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for j in np.nonzero(adj[node] != 0)[0]:
            in_degree[j] -= 1
            if in_degree[j] == 0:
                queue.append(int(j))
    if len(order) != n:
        raise ValueError("adjacency matrix contains a cycle — not a DAG")
    return order


def sever_incoming_edges(adjacency: np.ndarray, nodes: Sequence[int]) -> np.ndarray:
    """Pearl graph surgery on the adjacency matrix.

    do(X_i) removes every edge INTO X_i:  A'[:, i] = 0.
    This is the explicit edge-severing operator — the intervened variable
    is decoupled from its parents while outgoing causal influence survives.
    """
    severed = np.array(adjacency, dtype=np.float64, copy=True)
    for node in nodes:
        severed[:, int(node)] = 0.0
    return severed


# ---------------------------------------------------------------------------
# Information measures for the S-3 elevation
# ---------------------------------------------------------------------------


def iter_bipartitions(n: int) -> Iterator[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    """Enumerate all non-trivial bipartitions of {0..n-1} exactly once.

    Element 0 is fixed in side A so each unordered partition {A, B} is
    yielded a single time: 2^{n-1} - 1 partitions. The only excluded mask
    is all-ones (B empty, trivial partition).
    """
    for mask in range(0, 2 ** (n - 1) - 1):
        a = [0] + [i + 1 for i in range(n - 1) if mask & (1 << i)]
        b = [i for i in range(1, n) if not (mask & (1 << (i - 1)))]
        yield tuple(a), tuple(b)


def gaussian_mutual_information(
    cov: np.ndarray, part_a: Sequence[int], part_b: Sequence[int]
) -> float:
    """I(A;B) = 1/2 ln( det Sigma_AA * det Sigma_BB / det Sigma ).

    This is exactly the KL divergence D(N(0, Sigma) || N(0, Sigma_AA (+) Sigma_BB))
    between the joint Gaussian and the product of its marginals — the
    classical integrated-information measure of Barrett & Seth (2011).
    Natural log (nats).  Zero iff the blocks are uncorrelated.
    """
    cov = np.asarray(cov, dtype=np.float64)
    sa = cov[np.ix_(part_a, part_a)]
    sb = cov[np.ix_(part_b, part_b)]
    sign_a, la = np.linalg.slogdet(sa)
    sign_b, lb = np.linalg.slogdet(sb)
    sign_t, lt = np.linalg.slogdet(cov)
    if min(sign_a, sign_b, sign_t) <= 0:
        return 0.0
    return max(0.0, 0.5 * (la + lb - lt))


def density_matrix_from_state(state: np.ndarray) -> np.ndarray:
    """Pure-state density matrix rho = |psi><psi| over C^11.

    The amplitude vector is the standardised ball state normalised to unit
    l2 norm. A zero state maps to the maximally mixed state I/11 — the
    unique trace-1 positive operator invariant under U(11).
    """
    y = standardize(as_ball_vector(state))
    norm = float(np.linalg.norm(y))
    if norm < 1e-15:
        return np.eye(MANIFOLD_DIM, dtype=np.complex128) / MANIFOLD_DIM
    psi = (y / norm).astype(np.complex128)
    return np.outer(psi, np.conj(psi))


def von_neumann_entropy(rho: np.ndarray) -> float:
    """S(rho) = -Tr(rho ln rho) in nats, computed from the spectrum."""
    vals = np.linalg.eigvalsh(np.asarray(rho, dtype=np.complex128))
    vals = vals[vals > 1e-15]
    return float(-np.sum(vals * np.log(vals)))


def quantum_relative_entropy(rho: np.ndarray, sigma: np.ndarray) -> float:
    """D(rho || sigma) = Tr(rho ln rho - rho ln sigma) in nats.

    Computed exactly in the eigenbases of both operators:
        D = sum_i l_i ln l_i - sum_{i,j} |<i|j'>|^2 l_i ln m_j
    with l_i, |i> the eigenpairs of rho and m_j, |j'> those of sigma.
    """
    rho = np.asarray(rho, dtype=np.complex128)
    sigma = np.asarray(sigma, dtype=np.complex128)
    l_rho, v_rho = np.linalg.eigh(rho)
    l_sig, v_sig = np.linalg.eigh(sigma)
    l_rho = np.clip(l_rho.real, 0.0, None)
    l_sig = np.clip(l_sig.real, 0.0, None)
    overlap = np.abs(v_rho.conj().T @ v_sig) ** 2
    d = 0.0
    for i, li in enumerate(l_rho):
        if li <= 1e-15:
            continue
        d += li * math.log(li)
        for j, mj in enumerate(l_sig):
            if mj <= 1e-15:
                if overlap[i, j] > 1e-12:
                    return float("inf")  # support of rho outside support of sigma
                continue
            d -= li * overlap[i, j] * math.log(mj)
    return float(d)


def partial_trace(rho: np.ndarray, site_dims: Sequence[int], keep: Sequence[int]) -> np.ndarray:
    """Partial trace of a multipartite density matrix.

    ``rho`` acts on the tensor product of sites with dimensions
    ``site_dims``; ``keep`` lists the site indices retained. Traced-out
    sites are contracted via np.trace over their (bra, ket) axis pairs.
    """
    rho = np.asarray(rho, dtype=np.complex128)
    site_dims = [int(d) for d in site_dims]
    n = len(site_dims)
    assert int(np.prod(site_dims)) == rho.shape[0] == rho.shape[1]
    keep = sorted(int(k) for k in keep)
    tensor = rho.reshape(site_dims + site_dims)
    # Trace out non-kept sites, highest axis first so indices stay valid.
    for site in sorted((s for s in range(n) if s not in keep), reverse=True):
        tensor = np.trace(tensor, axis1=site, axis2=site + tensor.ndim // 2)
    kept_dims = [site_dims[k] for k in keep]
    dim = int(np.prod(kept_dims)) if kept_dims else 1
    return tensor.reshape(dim, dim)


def mutual_information_density(
    rho: np.ndarray, site_dims: Sequence[int], part_a: Sequence[int]
) -> float:
    """I(A;B) = S(rho_A) + S(rho_B) - S(rho) for a site bipartition.

    Equals the quantum relative entropy D(rho || rho_A (x) rho_B) exactly.
    """
    site_dims = list(site_dims)
    part_a = sorted(part_a)
    part_b = [i for i in range(len(site_dims)) if i not in part_a]
    rho_a = partial_trace(rho, site_dims, part_a)
    rho_b = partial_trace(rho, site_dims, part_b)
    mi = von_neumann_entropy(rho_a) + von_neumann_entropy(rho_b) - von_neumann_entropy(rho)
    return max(0.0, mi)


def minimum_information_partition(
    cov_or_rho: np.ndarray,
    site_dims: Optional[Sequence[int]] = None,
) -> Dict[str, object]:
    """Bipartite Minimum Information Partition.

    Two genuine measures, chosen by the input kind:
      - ``site_dims`` given: quantum relative entropy route.
        Phi = min_{A,B} D(rho || rho_A (x) rho_B)
              = min_{A,B} S(rho_A) + S(rho_B) - S(rho).
      - ``site_dims`` None:  Gaussian route over coordinate bipartitions,
        Phi = min_{A,B} I_Gauss(A;B) on the covariance matrix.

    Returns {"phi", "partition", "method"}.
    """
    mat = np.asarray(cov_or_rho)
    best_phi = float("inf")
    best_partition: Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]] = None
    if site_dims is not None:
        n = len(site_dims)
        for a, b in iter_bipartitions(n):
            mi = mutual_information_density(mat, site_dims, a)
            if mi < best_phi:
                best_phi = mi
                best_partition = (a, b)
        method = "quantum_relative_entropy"
    else:
        n = mat.shape[0]
        for a, b in iter_bipartitions(n):
            mi = gaussian_mutual_information(mat, a, b)
            if mi < best_phi:
                best_phi = mi
                best_partition = (a, b)
        method = "gaussian_relative_entropy"
    return {"phi": float(best_phi), "partition": best_partition, "method": method}


# ---------------------------------------------------------------------------
# Dual-mode result base class
# ---------------------------------------------------------------------------


@dataclass
class ManifoldResult:
    """Base for dual-mode returns: a manifold payload + scalar projection."""

    state: np.ndarray

    def to_scalar(self) -> float:
        return scalar_projection(self.state)
