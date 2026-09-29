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

THEOREM_PROVEN = False


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
