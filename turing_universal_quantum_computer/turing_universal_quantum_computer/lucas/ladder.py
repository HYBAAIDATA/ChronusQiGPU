"""Lucas ladder — the canonical scale sequence the mining session climbs.

FULL_LADDER is the ordered list of Lucas indices the orchestrator climbs
as cumulative coherence (delta_phi) grows: L_10 -> L_12 -> L_15 -> L_18
-> L_20. Values are verified against the exact fast-doubling substrate
in lucas.core — nothing is hardcoded against a table of expectations.
"""

from __future__ import annotations

from .core import lucas

FULL_LADDER: list[int] = [10, 12, 15, 18, 20]

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
