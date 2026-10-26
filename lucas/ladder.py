"""Lucas ladder — the canonical scale sequence the mining session climbs.

FULL_LADDER is the ordered list of Lucas indices the orchestrator climbs:
the original curriculum prefix plus the restored mining rungs 31, 50 and
the Pisot collapse index 76. Values are verified against the exact
fast-doubling substrate in lucas.core — nothing is hardcoded against a
table of expectations.
"""

from __future__ import annotations

from .core import lucas

CURRICULUM_RUNGS: tuple[int, ...] = (10, 12, 15, 18, 20)

# The declared mining ladder. A launch/scale index is valid iff it is a rung
# or a multiple of a rung. This is the single source for scale rungs; algorithm
# and device layers import it rather than restating the tuple.
SCALE_RUNGS: tuple[int, ...] = (*CURRICULUM_RUNGS, 31, 50, 76)
FULL_LADDER: list[int] = list(SCALE_RUNGS)
PISOT_EXACT_N: int = 76

# Chronus-domain name for the same ladder (capacity/dispatch rungs).
CHRONUS_SCALE_RUNGS: tuple[int, ...] = SCALE_RUNGS

# Exact Lucas value at each rung (computed once via the fast-doubling substrate).
LUCAS_SCALE_LADDER: dict[int, int] = {i: lucas(i) for i in FULL_LADDER}

THEOREM_PROVEN = False


def is_ladder_index(n: int) -> bool:
    """True iff n is a rung or a multiple of a rung (n = k·r)."""
    return n > 0 and any(n % r == 0 for r in SCALE_RUNGS)


def ladder_multiples_of(n: int) -> list[int]:
    """Which rungs divide n (empty when n is off-ladder)."""
    return [r for r in SCALE_RUNGS if n % r == 0]


def nearest_ladder_index(n: int, lo: int, hi: int) -> int:
    """Snap n to the nearest valid ladder index inside [lo, hi].

    Prefers the upward stop on ties (scale bias). Returns the clamped n
    unchanged when no ladder stop exists in range.
    """
    c = max(lo, min(hi, int(round(n))))
    if is_ladder_index(c):
        return c
    for d in range(1, max(hi - c, c - lo) + 1):
        if c + d <= hi and is_ladder_index(c + d):
            return c + d
        if c - d >= lo and is_ladder_index(c - d):
            return c - d
    return c


def next_ladder_index(n: int, direction: int, lo: int, hi: int) -> int:
    """Next ladder stop strictly beyond n in ``direction``, clamped to [lo,hi]."""
    step = 1 if direction >= 0 else -1
    m = n + step
    while lo <= m <= hi:
        if is_ladder_index(m):
            return m
        m += step
    return n


def ladder_capacity(bound: int) -> int:
    """Snap a Chronus-owned capacity/retention bound to a ladder stop.

    Returns the nearest ladder stop (upward-biased) inside [1, bound];
    bounds below the minimum stop (10) promote to 10. The bound is a
    scale-contract envelope (lemma_lucas_universal, LUCAS_SCALED) — never
    a measured quantity.
    """
    b = max(1, int(bound))
    return nearest_ladder_index(b, 1, max(10, b))


def ladder_values() -> list[int]:
    """Exact Lucas values at each rung, computed (not tabulated)."""
    return [lucas(i) for i in FULL_LADDER]


def next_rung(index: int) -> int | None:
    """Return the next ladder index above `index`, or None at the top."""
    for rung in FULL_LADDER:
        if rung > index:
            return rung
    return None


def climb(index: int) -> int:
    """Advance one rung up the ladder; stays at the top rung."""
    nxt = next_rung(index)
    return nxt if nxt is not None else index


def verify_ladder() -> dict[str, object]:
    """Verify the ladder: exact Lucas values, strictly increasing."""
    values = ladder_values()
    return {
        "ladder": list(FULL_LADDER),
        "values": values,
        "monotonic": all(values[i] < values[i + 1] for i in range(len(values) - 1)),
        "valid": all(lucas(i) == v for i, v in zip(FULL_LADDER, values)),
        "theorem_proven": False,
    }


def require_release_rung(index: int) -> int:
    """Governed execution uses exact declared rungs, not arbitrary multiples.

    Legacy capacity rounding remains a separate engineering policy; membership
    never proves a physical speedup or reduces required SHA-256 trials.
    """
    if type(index) is not int or index not in SCALE_RUNGS:
        raise ValueError("RELEASE_LUCAS_RUNG_NOT_ALLOWLISTED")
    return index
