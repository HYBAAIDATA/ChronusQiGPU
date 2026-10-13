"""Native registry for algorithms that cannot be elevated from the Lucas pool.

Every native entry records the algorithm name, the reason elevation is
impossible, and its inline Lucas bound. The registry is append-only.
"""

from __future__ import annotations

from typing import Any

THEOREM_PROVEN = False

_REGISTRY: list[dict[str, Any]] = []


def register(
    algorithm: str,
    reason: str,
    lucas_bound: int,
    substrate: str = "native",
) -> None:
    """Register a native-path algorithm."""
    _REGISTRY.append(
        {
            "algorithm": algorithm,
            "native": True,
            "reason_no_elevation": reason,
            "lucas_bound": lucas_bound,
            "substrate": substrate,
            "theorem_proven": False,
        }
    )


def entries() -> list[dict[str, Any]]:
    """Return all native registry entries."""
    return list(_REGISTRY)


# Mining subsystems with no Lucas substrate — one-line justification each.
# Everything else in the mining loop routes through one of the seven pool
# kernels; see lucas/routing.md.
register(
    "entropy_codec",
    "zlib entropy coding inside folded artifacts is a measured storage "
    "codec, not a quantum operator; compression ratio is recorded, not "
    "algebraically bounded",
    lucas_bound=0,
)
register(
    "wall_clock_cooldown",
    "the safety cooldown timer waits on external network blocks — a "
    "real-time wait, not an algebraic search quantity",
    lucas_bound=0,
)
