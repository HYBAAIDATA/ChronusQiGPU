"""Exactly certified expander graphs over finite fields (Paley graphs).

The AL HARAS notes call for a Ramanujan expander over F_257. This module builds
the Paley graph P(q) for a prime q = 1 (mod 4): vertices are the elements of
F_q and x ~ y iff x - y is a non-zero square. Everything below is verified with
integer arithmetic, no floating point:

* regularity: every vertex has degree k = (q - 1) / 2;
* strong regularity: adjacent pairs share lambda = (q - 5) / 4 neighbours and
  non-adjacent pairs share mu = (q - 1) / 4 (checked pair by pair);
* the spectrum then follows exactly: k once, and (-1 +/- sqrt(q)) / 2;
* Ramanujan bound: max non-trivial |eigenvalue| <= 2 sqrt(k - 1), decided by an
  exact integer inequality;
* random-walk mixing: the number of steps after which the total-variation
  distance to uniform is provably below a target, from a rational upper bound
  of sqrt(q);
* resilience: largest connected component after deterministic vertex removal.

Not implemented: the Lubotzky-Phillips-Sarnak Cayley graph on PSL_2(F_257) of
degree 258 named in older notes. The Paley graph is the implemented,
exactly-certified expander.
"""

import hashlib
from collections import deque
from fractions import Fraction
from functools import lru_cache
from math import isqrt
from typing import Any, Dict, List, Optional, Sequence, Set

from chronus.security.al_haras.exact import decimal_string, sqrt_decimal_string, sqrt_upper_bound

MAX_Q = 4099


class ExpanderError(ValueError):
    """Invalid expander parameters."""


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    r = isqrt(n)
    f = 3
    while f <= r:
        if n % f == 0:
            return False
        f += 2
    return True


def _check_q(q: int) -> None:
    if not is_prime(q) or q % 4 != 1 or q < 5 or q > MAX_Q:
        raise ExpanderError(f"Paley graphs need a prime q = 1 (mod 4), 5 <= q <= {MAX_Q}")


@lru_cache(maxsize=16)
def paley_neighbours(q: int) -> tuple:
    _check_q(q)
    squares = frozenset((x * x) % q for x in range(1, q))
    return tuple(frozenset((x + s) % q for s in squares) for x in range(q))


@lru_cache(maxsize=16)
def certify_paley(q: int) -> Dict[str, Any]:
    """Exact certificate of the Paley graph's structure and spectrum."""
    nbrs = paley_neighbours(q)
    k = (q - 1) // 2
    lam = (q - 5) // 4
    mu = (q - 1) // 4
    regular = all(len(n) == k for n in nbrs)
    symmetric = all(x in nbrs[y] for x in range(q) for y in nbrs[x])
    srg = True
    for x in range(q):
        nx = nbrs[x]
        for y in range(x + 1, q):
            common = len(nx & nbrs[y])
            if common != (lam if y in nx else mu):
                srg = False
                break
        if not srg:
            break
    # Exact spectrum of srg(q, k, lam, mu): k, (-1 + sqrt q)/2, (-1 - sqrt q)/2.
    # Ramanujan: (1 + sqrt q)/2 <= 2 sqrt(k - 1)  <=>  4q <= (16(k-1) - 1 - q)^2 with rhs >= 0
    rhs = 16 * (k - 1) - 1 - q
    ramanujan = rhs >= 0 and 4 * q <= rhs * rhs
    sqrt_q_up = sqrt_upper_bound(Fraction(q))
    sqrt_q_trunc = Fraction(isqrt(q * 10**16), 10**8)
    rho_up = (1 + sqrt_q_up) / (q - 1)  # max |eigenvalue| of the walk matrix A/k
    return {
        "graph": f"Paley graph P({q}) over F_{q}",
        "vertices": q,
        "degree": k,
        "regular": regular,
        "symmetric": symmetric,
        "strongly_regular": srg,
        "srg_parameters": [q, k, lam, mu],
        "connected": srg and mu > 0,
        "eigenvalues_exact": [str(k), f"(-1 + sqrt({q}))/2", f"(-1 - sqrt({q}))/2"],
        "multiplicities": [1, k, k],
        "lambda_2_decimal": decimal_string((sqrt_q_trunc - 1) / 2, 6),
        "max_nontrivial_abs_eigenvalue_decimal": decimal_string((sqrt_q_trunc + 1) / 2, 6),
        "ramanujan_bound": f"2*sqrt({k - 1})",
        "ramanujan_bound_decimal": sqrt_decimal_string(Fraction(4 * (k - 1)), 6),
        "is_ramanujan": bool(regular and symmetric and srg and ramanujan),
        "spectral_gap_exact": f"({q} - sqrt({q}))/2",
        "spectral_gap_decimal": decimal_string((q - sqrt_q_trunc) / 2, 6),
        "walk_contraction_upper_bound": rho_up,
    }


def mixing_steps(q: int, epsilon: Fraction = Fraction(1, 2**32)) -> int:
    """Smallest t with (sqrt(n)/2) * rho^t <= epsilon, using an upper bound of rho."""
    cert = certify_paley(q)
    rho = cert["walk_contraction_upper_bound"]
    n = Fraction(q)
    t = 0
    bound_sq = n / 4
    rho_sq = rho * rho
    target = Fraction(epsilon) * Fraction(epsilon)
    while bound_sq > target:
        bound_sq *= rho_sq
        t += 1
        if t > 10_000:
            raise ExpanderError("mixing bound did not converge")
    return t


def _largest_component(alive: Set[int], nbrs: Sequence[frozenset]) -> int:
    seen: Set[int] = set()
    best = 0
    for start in alive:
        if start in seen:
            continue
        size = 0
        queue = deque([start])
        seen.add(start)
        while queue:
            u = queue.popleft()
            size += 1
            for v in nbrs[u]:
                if v in alive and v not in seen:
                    seen.add(v)
                    queue.append(v)
        best = max(best, size)
    return best


def removal_resilience(q: int, fraction: Fraction, seed: bytes = b"al-haras", strategy: str = "hashed") -> Dict[str, Any]:
    """Remove ``fraction`` of the vertices and measure the largest surviving component.

    ``hashed`` removes vertices in SHA-256(seed || vertex) order (a deterministic,
    reproducible spread); ``ball`` removes a contiguous breadth-first region around
    vertex 0, modelling a localised outage.
    """
    fraction = Fraction(fraction)
    if not 0 <= fraction < 1:
        raise ExpanderError("removal fraction must be in [0, 1)")
    nbrs = paley_neighbours(q)
    remove_count = (fraction * q).numerator // (fraction * q).denominator
    if strategy == "hashed":
        order = sorted(range(q), key=lambda v: hashlib.sha256(seed + v.to_bytes(4, "big")).digest())
    elif strategy == "ball":
        order, seen, queue = [], {0}, deque([0])
        while queue:
            u = queue.popleft()
            order.append(u)
            for v in sorted(nbrs[u]):
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
    else:
        raise ExpanderError("strategy must be 'hashed' or 'ball'")
    removed = set(order[:remove_count])
    alive = set(range(q)) - removed
    largest = _largest_component(alive, nbrs) if alive else 0
    surviving = Fraction(largest, len(alive)) if alive else Fraction(0)
    return {
        "strategy": strategy,
        "vertices": q,
        "removed": len(removed),
        "remaining": len(alive),
        "largest_component": largest,
        "remaining_connected": largest == len(alive),
        "largest_component_share_of_remaining": decimal_string(surviving, 6),
    }


def neighbours_list(q: int) -> List[List[int]]:
    return [sorted(n) for n in paley_neighbours(q)]


def shortest_path(q: int, source: int, target: int, blocked: Optional[Set[int]] = None) -> Optional[List[int]]:
    """Breadth-first shortest path avoiding ``blocked`` vertices (None if cut off)."""
    nbrs = paley_neighbours(q)
    blocked = blocked or set()
    if source in blocked or target in blocked:
        return None
    prev = {source: None}
    queue = deque([source])
    while queue:
        u = queue.popleft()
        if u == target:
            path = [u]
            while prev[path[-1]] is not None:
                path.append(prev[path[-1]])
            return path[::-1]
        for v in sorted(nbrs[u]):
            if v not in prev and v not in blocked:
                prev[v] = u
                queue.append(v)
    return None
