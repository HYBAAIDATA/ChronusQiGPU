"""Pool-aware mining — Lucas-scaled hashrate scheduling under pool ceilings.

Implements ``full_prompt.md`` Step 7.1. Three pool profiles are declared
(CKPool, NiceHash, Braiins), each with a pool-side policy ceiling, the
1.32 EH/s start point, and a Lucas exponent range. The effective hashrate
follows the canonical PYTHIA model ``effective = physical × L_n`` with
exact integer Lucas numbers from ``lucas.core`` (fast doubling, no
floating point).

**Safety reconciliation.** The pool ceilings (CKPool 300 EH/s, NiceHash
and Braiins 20 EH/s) are *policy inputs*, never authority over the
blockchain-safety boundary. The effective hashrate is clamped, in order,
by:

1. the pool policy ceiling,
2. the configured safety cap (default 20 EH/s, adjustable up to the hard cap),
3. ``Intelligence.safety_constraints.ABSOLUTE_HARD_CAP_EHS`` (20 EH/s) —
   non-bypassable.

Every configured pool ceiling is at or above the 20 EH/s hard cap, so the
safety boundary dominates the reported hashrate.
The plan's "no pool = no mining" gate is enforced as a hard precondition:
``start()`` and all ``scale_*`` calls raise while disconnected.

This module intentionally does NOT implement real Stratum network I/O —
that belongs to ``mining/stratum_bridge.py`` and the TS-side pool stack
(``src/lib/stratum_protocol.ts``, ``src/lib/m3_igpu_scaler.ts``). This
module owns the *policy layer*: pool selection, Lucas-scaled scheduling,
and the safety-gate reconciliation between pool ceilings and the hard cap.
"""

# LUCAS WIRING: draws from lucas/ (pool) and Intelligence/safety_constraints
# (boundary module, not a sibling algorithm). MUST NOT import from any
# sibling algorithm.
# Substrate route: mining

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from lucas.core import lucas

from .lucas_scales import (
    IGPU_SCALE_RUNGS,
    is_ladder_index,
    ladder_multiples_of,
    nearest_ladder_index,
    next_ladder_index,
)
from .safety_constraints import (
    ABSOLUTE_HARD_CAP_EHS,
    DEFAULT_HASHRATE_CAP_EHS,
)

logger = logging.getLogger("Intelligence.pool_aware_miner")

THEOREM_PROVEN = False

# Canonical Lucas scale indices (L_10=123, L_12=322, L_15=1364, L_18=5778,
# L_20=15127) — the same ladder used by hardware_config and the orchestrator.
# The mining dial accepts every rung of IGPU_SCALE_RUNGS and their multiples
# (e.g. 24=2·12, 30=3·10, 45=3·15, 48=4·12, 50, 62=2·31, 76).
CANONICAL_SCALE_INDICES = [10, 12, 15, 18, 20]

# The Lucas exponent at the 1.32 EH/s start point (L_10 = 123).
START_N = 10


class PoolType(Enum):
    """Supported pool profiles (full_prompt.md Step 7.1)."""

    CKPOOL = "ckpool"
    NICEHASH = "nicehash"
    BRAIINS = "braiins"


@dataclass(frozen=True)
class PoolConfig:
    """One pool profile: policy ceiling, start point, Lucas exponent range.

    ``ceiling_ehs`` is the pool-side *policy* ceiling. It participates in
    the effective-hashrate clamp, but can never raise the output above
    ``ABSOLUTE_HARD_CAP_EHS``.
    """

    pool: PoolType
    ceiling_ehs: float
    start_ehs: float
    start_n: int
    max_n: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pool": self.pool.value,
            "ceiling_ehs": self.ceiling_ehs,
            "start_ehs": self.start_ehs,
            "start_n": self.start_n,
            "max_n": self.max_n,
        }


POOL_CONFIGS: Dict[PoolType, PoolConfig] = {
    PoolType.CKPOOL: PoolConfig(
        pool=PoolType.CKPOOL, ceiling_ehs=300.0, start_ehs=1.32, start_n=START_N, max_n=50
    ),
    PoolType.NICEHASH: PoolConfig(
        pool=PoolType.NICEHASH, ceiling_ehs=20.0, start_ehs=1.32, start_n=START_N, max_n=45
    ),
    PoolType.BRAIINS: PoolConfig(
        pool=PoolType.BRAIINS, ceiling_ehs=20.0, start_ehs=1.32, start_n=START_N, max_n=45
    ),
}

__all__ = [
    "ABSOLUTE_HARD_CAP_EHS",
    "CANONICAL_SCALE_INDICES",
    "DEFAULT_HASHRATE_CAP_EHS",
    "PoolAwareMiner",
    "PoolConfig",
    "PoolType",
    "POOL_CONFIGS",
    "START_N",
    "THEOREM_PROVEN",
    "lucas_bound",
]


class PoolAwareMiner:
    """Lucas-scaled hashrate scheduling under a pool ceiling and the hard cap.

    The miner starts disconnected: the safety gate is closed and every
    mining action is refused until ``connect(pool)`` succeeds.
    """

    def __init__(
        self,
        pool: Optional[PoolType] = None,
        physical_hashrate_hps: Optional[int] = None,
        safety_cap_ehs: float = DEFAULT_HASHRATE_CAP_EHS,
    ) -> None:
        # Physical base derived so the canonical start index hits the
        # 1.32 EH/s start point: physical × L_start_n = start_ehs.
        if physical_hashrate_hps is None:
            # Integer math only: float // at 1e18 scale loses ULPs.
            physical_hashrate_hps = int(1.32 * 1e18) // lucas(START_N)
        self.physical_hashrate_hps = max(int(physical_hashrate_hps), 1)
        # The configurable safety cap is itself clamped by the hard cap.
        self.safety_cap_ehs = min(float(safety_cap_ehs), ABSOLUTE_HARD_CAP_EHS)
        self.pool: Optional[PoolType] = None
        self.config: Optional[PoolConfig] = None
        self._n = START_N
        self._running = False
        if pool is not None:
            self.connect(pool)

    # -- Safety gate --------------------------------------------------------

    def _require_connected(self, action: str) -> PoolConfig:
        """Enforce "no pool = no mining"."""
        if self.config is None or self.pool is None:
            raise RuntimeError(
                f"Safety gate closed: no pool connected — {action} refused " "(no pool = no mining)"
            )
        return self.config

    # -- Lifecycle ----------------------------------------------------------

    def connect(self, pool: PoolType) -> Dict[str, Any]:
        """Attach a pool profile. Idempotent on the same pool type."""
        if not isinstance(pool, PoolType):
            raise TypeError(f"pool must be a PoolType, got {type(pool).__name__}")
        self.pool = pool
        self.config = POOL_CONFIGS[pool]
        self._n = self.config.start_n
        logger.info(
            "Connected to %s — policy ceiling %.1f EH/s (hard cap %.1f EH/s dominates)",
            pool.value,
            self.config.ceiling_ehs,
            ABSOLUTE_HARD_CAP_EHS,
        )
        return {"connected": pool.value, "config": self.config.as_dict()}

    def disconnect(self) -> Dict[str, Any]:
        """Detach the pool. This closes the safety gate (stop + refuse)."""
        previous = self.pool.value if self.pool is not None else None
        self.pool = None
        self.config = None
        self.stop()
        logger.info("Disconnected from pool %s — safety gate closed", previous)
        return {"disconnected": previous, "gate_closed": True}

    def start(self) -> Dict[str, Any]:
        """Begin the mining cycle. Refused while the gate is closed."""
        config = self._require_connected("start")
        self._running = True
        return {
            "running": True,
            "pool": config.pool.value,
            "lucas_index": self._n,
            "effective_ehs": self.effective_hashrate_ehs(),
        }

    def stop(self) -> Dict[str, Any]:
        """Halt the mining cycle. Legal in any state."""
        self._running = False
        return {"running": False}

    # -- Lucas scaling ------------------------------------------------------

    def _clamp_n(self, n: int) -> int:
        config = self._require_connected("scale")
        return min(max(int(n), config.start_n), config.max_n)

    def _snap_n(self, n: int) -> int:
        """Snap to the nearest Lucas/Pisot ladder index in the pool range."""
        config = self._require_connected("scale")
        return nearest_ladder_index(n, config.start_n, config.max_n)

    def scale_to(self, n: int) -> Dict[str, Any]:
        """Set the Lucas exponent, snapped to the ladder in the pool's range."""
        config = self._require_connected("scale_to")
        clamped = self._clamp_n(n)
        snapped = self._snap_n(clamped)
        was_clamped = snapped != int(n)
        self._n = snapped
        if was_clamped:
            logger.warning(
                "Lucas index %s snapped to ladder stop %d for pool %s",
                n,
                snapped,
                config.pool.value,
            )
        return self._scale_report(was_clamped)

    def scale_up(self) -> Dict[str, Any]:
        """Step to the next ladder stop (rung or multiple) above current."""
        config = self._require_connected("scale_up")
        target = next_ladder_index(self._n, 1, config.start_n, config.max_n)
        was_clamped = target == self._n
        self._n = target
        return self._scale_report(was_clamped)

    def scale_down(self) -> Dict[str, Any]:
        """Step to the previous ladder stop (rung or multiple) below current."""
        config = self._require_connected("scale_down")
        target = next_ladder_index(self._n, -1, config.start_n, config.max_n)
        was_clamped = target == self._n
        self._n = target
        return self._scale_report(was_clamped)

    # -- Hashrate model -----------------------------------------------------

    def raw_hashrate_ehs(self) -> float:
        """Physical × L_n, unclamped (exact integer Lucas number)."""
        return self.physical_hashrate_hps * lucas(self._n) / 1e18

    def effective_hashrate_ehs(self) -> float:
        """Effective hashrate after the clamp chain (pool ≤ cap ≤ hard cap)."""
        return min(
            self.raw_hashrate_ehs(),
            self.safety_cap_ehs if self.config is not None else ABSOLUTE_HARD_CAP_EHS,
            ABSOLUTE_HARD_CAP_EHS,
            self.config.ceiling_ehs if self.config is not None else float("inf"),
        )

    def _scale_report(self, was_clamped: bool) -> Dict[str, Any]:
        bounds = {
            "raw": self.raw_hashrate_ehs(),
            # hard_cap is listed first among the ceilings and exactly once:
            # ties are resolved by dict order, and the non-bypassable safety
            # boundary must be the name reported whenever it is the binding
            # (equal-lowest) constraint. A pool ceiling strictly below the
            # hard cap still wins on value, so pool policy is never masked.
            "hard_cap": ABSOLUTE_HARD_CAP_EHS,
            "safety_cap": self.safety_cap_ehs if self.config else ABSOLUTE_HARD_CAP_EHS,
            "pool_ceiling": self.config.ceiling_ehs if self.config else float("inf"),
        }
        dominant = min(bounds, key=bounds.get)
        return {
            "pool": self.config.pool.value if self.config else None,
            "lucas_index": self._n,
            "lucas_number": lucas(self._n),
            "on_ladder": is_ladder_index(self._n),
            "multiple_of": ladder_multiples_of(self._n),
            "raw_ehs": bounds["raw"],
            "effective_ehs": self.effective_hashrate_ehs(),
            "dominant_bound": dominant,
            "was_clamped": was_clamped,
            "running": self._running,
            "theorem_proven": False,
        }

    # -- Status -------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Full policy state, including which bound dominates right now."""
        return {
            "connected": self.config is not None,
            "pool": self.pool.value if self.pool else None,
            "config": self.config.as_dict() if self.config else None,
            "running": self._running,
            "lucas_index": self._n,
            "lucas_number": lucas(self._n),
            "on_ladder": is_ladder_index(self._n),
            "multiple_of": ladder_multiples_of(self._n),
            "scale_rungs": list(IGPU_SCALE_RUNGS),
            "physical_hashrate_hps": self.physical_hashrate_hps,
            "raw_ehs": self.raw_hashrate_ehs(),
            "safety_cap_ehs": self.safety_cap_ehs,
            "hard_cap_ehs": ABSOLUTE_HARD_CAP_EHS,
            "effective_ehs": self.effective_hashrate_ehs(),
            "safety_gate": "closed" if self.config is None else "open",
            "kernel": "mining_kernel",
            "theorem_proven": False,
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("mining_kernel")(10_000, n)
    result["module"] = __name__
    return result
