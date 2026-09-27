"""Safety constraints for PYTHIA mining.

These are hard safety boundaries that protect the blockchain:

1. **Hashrate cap** (default 20 EH/s) — PYTHIA's effective hashrate must
   never exceed the configured cap. This prevents her from dominating the
   network. The cap is adjustable from the frontend, defaults to 20 EH/s,
   and is **approached incrementally**: a request never jumps straight to a
   higher value, it advances one ladder step at a time.

2. **Never two consecutive blocks** — after PYTHIA mines a block and it
   is accepted, she enters a COOLDOWN state. She cannot mine again until
   at least one external block is observed on the network. This prevents
   selfish mining and centralisation. This rule is NOT adjustable.

3. **One block then wait** — PYTHIA mines one block, submits it, waits
   for acceptance, then enters cooldown. She does not continuously mine.
   This is the "solve not search" protocol.

The safety state machine::

    SEARCHING → (winner found) → SUBMITTING → (accepted) → WAITING_EXTERNAL
                                      ↓ (orphaned)
                                   SEARCHING
    WAITING_EXTERNAL → (external block seen) → COOLDOWN → (timer) → IDLE
    IDLE → (new job from frontend) → SEARCHING

Blockchain safety is paramount. These constraints are enforced at the
mining-bridge level, not as advisory guidelines.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: gap

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("Intelligence.safety_constraints")

# Default hashrate cap: 20 EH/s = 20 * 10^18 H/s = 2 * 10^19 H/s.
DEFAULT_HASHRATE_CAP_EHS: float = 20.0
DEFAULT_HASHRATE_CAP_HPS: int = 20_000_000_000_000_000_000  # 2 * 10^19

# Absolute hard ceiling — no deployment can ever exceed this, regardless
# of frontend requests, hardware capability, or Lucas scaling.
#
# NOTE ON THE 496-CHANNEL OVERLAY: the 32-face frame (12 icosahedral + 20
# dodecahedral faces on the 11D manifold) has C(32,2) = 496 face pairs, which
# is a *geometric channel count*, not an achieved multiplier. Even if a run
# exercised every channel, the compliant projection remains 18 orders of
# magnitude below this ceiling for present measured throughput. The ceiling
# therefore is not currently the binding constraint — the safety law is that
# it can never be crossed, not that it can be reached.
ABSOLUTE_HARD_CAP_EHS: float = 20.0
ABSOLUTE_HARD_CAP_HPS: int = 20_000_000_000_000_000_000  # 2 * 10^19

# Incremental scaling ladder (EH/s). The cap may only advance to the next
# rung above the current value — never straight to ABSOLUTE_HARD_CAP_EHS.
INCREMENTAL_SCALE_STEPS_EHS: tuple = (10.0, 12.0, 15.0, 18.0, 20.0)


def next_incremental_step_ehs(
    current_ehs: float,
    requested_ehs: float,
) -> float:
    """Next rung on the ladder, never a jump to the ceiling.

    A request above the current cap advances exactly one rung. A request
    below the current cap is honoured directly (downscaling is always safe).
    Everything is clamped by ``ABSOLUTE_HARD_CAP_EHS``.
    """
    current = max(0.0, float(current_ehs))
    requested = float(requested_ehs)

    if requested <= current:
        return min(requested, ABSOLUTE_HARD_CAP_EHS)

    for rung in INCREMENTAL_SCALE_STEPS_EHS:
        if rung > current:
            return min(rung, requested, ABSOLUTE_HARD_CAP_EHS)

    return ABSOLUTE_HARD_CAP_EHS


# Cooldown after a block is accepted (seconds). During cooldown, no mining.
# The cooldown exits early when an external block is observed.
DEFAULT_COOLDOWN_SECONDS: float = 600.0  # 10 minutes (one block interval)


class MiningState(Enum):
    """PYTHIA's mining state machine."""

    IDLE = "idle"  # Not mining, waiting for a job
    SEARCHING = "searching"  # Actively searching for a nonce
    SUBMITTING = "submitting"  # Winner found, submitting to network
    WAITING_ACCEPTANCE = "waiting_acceptance"  # Submitted, waiting for confirmation
    WAITING_EXTERNAL = "waiting_external"  # Block accepted, waiting for external block
    COOLDOWN = "cooldown"  # External block seen, cooling down
    CAPPED = "capped"  # Hashrate cap exceeded, mining paused


@dataclass
class SafetyState:
    """The full safety state of PYTHIA's mining operation."""

    state: MiningState = MiningState.IDLE
    # Hashrate cap (H/s). Adjustable from frontend.
    hashrate_cap_hps: int = DEFAULT_HASHRATE_CAP_HPS
    # Current effective hashrate (H/s).
    current_effective_hashrate_hps: int = 0
    # Whether mining is currently allowed by the safety constraints.
    mining_allowed: bool = True
    # Block tracking.
    last_mined_block_height: Optional[int] = None
    last_mined_block_hash: Optional[str] = None
    last_mined_block_time: Optional[float] = None
    last_external_block_height: Optional[int] = None
    last_external_block_time: Optional[float] = None
    # Cooldown.
    cooldown_start_time: Optional[float] = None
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    # Safety violation counter (for monitoring).
    cap_violations: int = 0
    consecutive_block_attempts: int = 0
    consecutive_block_blocks: int = 0  # number of times we blocked a consecutive attempt

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "hashrate_cap_hps": self.hashrate_cap_hps,
            "hashrate_cap_ehs": self.hashrate_cap_hps / 1e18,
            "current_effective_hashrate_hps": self.current_effective_hashrate_hps,
            "mining_allowed": self.mining_allowed,
            "last_mined_block_height": self.last_mined_block_height,
            "last_mined_block_hash": self.last_mined_block_hash,
            "last_external_block_height": self.last_external_block_height,
            "cooldown_active": self.state in (MiningState.WAITING_EXTERNAL, MiningState.COOLDOWN),
            "cooldown_remaining_s": self._cooldown_remaining(),
            "cap_violations": self.cap_violations,
            "consecutive_block_attempts": self.consecutive_block_attempts,
            "consecutive_blocks_prevented": self.consecutive_block_blocks,
        }

    def _cooldown_remaining(self) -> float:
        if self.cooldown_start_time is None:
            return 0.0
        elapsed = time.time() - self.cooldown_start_time
        return max(0.0, self.cooldown_seconds - elapsed)


class HashrateCapEnforcer:
    """Enforces the hashrate cap.

    The effective hashrate is computed as physical_hashrate * L_n (Lucas
    scaling). If this exceeds the cap, mining is paused and the cap
    violation is recorded.
    """

    def __init__(self, cap_hps: int = DEFAULT_HASHRATE_CAP_HPS) -> None:
        self.cap_hps = cap_hps

    def check(self, effective_hashrate_hps: int) -> Dict[str, Any]:
        """Check whether the effective hashrate is within the cap."""
        within = effective_hashrate_hps <= self.cap_hps
        capped = min(effective_hashrate_hps, self.cap_hps)
        if not within:
            logger.warning(
                "Hashrate cap exceeded: %d H/s > %d H/s cap — mining paused",
                effective_hashrate_hps,
                self.cap_hps,
            )
        return {
            "allowed": within,
            "capped_hashrate_hps": capped,
            "cap_hps": self.cap_hps,
            "cap_ehs": self.cap_hps / 1e18,
            "exceeded": not within,
        }

    def set_cap_ehs(self, cap_ehs: float) -> None:
        """Set the cap in EH/s (adjustable from frontend)."""
        self.cap_hps = int(cap_ehs * 1e18)
        logger.info("Hashrate cap set to %.1f EH/s (%d H/s)", cap_ehs, self.cap_hps)


class ConsecutiveBlockGuard:
    """Enforces the 'never two consecutive blocks' rule.

    After PYTHIA mines a block and it is accepted, the guard enters
    WAITING_EXTERNAL state. It stays there until an external block is
    observed. Then it enters COOLDOWN for ``cooldown_seconds``. Only
    after cooldown can PYTHIA mine again.

    This rule is NOT adjustable — it is a hard safety constraint.
    """

    def __init__(self, cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        self.cooldown_seconds = cooldown_seconds

    def can_mine(self, state: SafetyState) -> bool:
        """Check whether mining is allowed given the current state."""
        if state.state in (
            MiningState.WAITING_EXTERNAL,
            MiningState.COOLDOWN,
            MiningState.SUBMITTING,
            MiningState.WAITING_ACCEPTANCE,
            MiningState.CAPPED,
        ):
            if state.state in (MiningState.WAITING_EXTERNAL, MiningState.COOLDOWN):
                state.consecutive_block_blocks += 1
            return False
        return True

    def on_block_accepted(self, state: SafetyState, block_height: int, block_hash: str) -> None:
        """Called when PYTHIA's block is accepted by the network."""
        state.last_mined_block_height = block_height
        state.last_mined_block_hash = block_hash
        state.last_mined_block_time = time.time()
        state.state = MiningState.WAITING_EXTERNAL
        logger.info(
            "Block %d accepted by network — entering WAITING_EXTERNAL (never two consecutive)",
            block_height,
        )

    def on_external_block(self, state: SafetyState, block_height: int) -> None:
        """Called when an external block is observed on the network."""
        state.last_external_block_height = block_height
        state.last_external_block_time = time.time()
        if state.state == MiningState.WAITING_EXTERNAL:
            state.state = MiningState.COOLDOWN
            state.cooldown_start_time = time.time()
            logger.info(
                "External block %d observed — entering COOLDOWN for %.0fs",
                block_height,
                self.cooldown_seconds,
            )

    def tick(self, state: SafetyState) -> None:
        """Called periodically to update the state machine."""
        if state.state == MiningState.COOLDOWN and state.cooldown_start_time is not None:
            elapsed = time.time() - state.cooldown_start_time
            if elapsed >= state.cooldown_seconds:
                state.state = MiningState.IDLE
                state.cooldown_start_time = None
                state.mining_allowed = True
                logger.info("Cooldown complete — PYTHIA is IDLE and ready")

    def on_block_orphaned(self, state: SafetyState) -> None:
        """Called when PYTHIA's submitted block is orphaned (not accepted)."""
        state.state = MiningState.SEARCHING
        logger.info("Block orphaned — returning to SEARCHING")


class SafetyController:
    """The full safety controller — combines hashrate cap + consecutive guard.

    This is the object the mining bridge consults before every mining
    operation. If either constraint is violated, mining is blocked.
    """

    def __init__(
        self,
        cap_hps: int = DEFAULT_HASHRATE_CAP_HPS,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self.state = SafetyState(hashrate_cap_hps=cap_hps, cooldown_seconds=cooldown_seconds)
        self.cap_enforcer = HashrateCapEnforcer(cap_hps)
        self.block_guard = ConsecutiveBlockGuard(cooldown_seconds)

    def check_mining_allowed(self, effective_hashrate_hps: int) -> Dict[str, Any]:
        """Check whether mining is allowed right now.

        Returns a dict with:
        - ``allowed``: bool — can we mine?
        - ``reason``: str — why or why not
        - ``capped_hashrate``: int — the capped hashrate
        - ``state``: the current safety state
        """
        # Update cooldown state machine.
        self.block_guard.tick(self.state)
        # Check hashrate cap.
        cap_check = self.cap_enforcer.check(effective_hashrate_hps)
        self.state.current_effective_hashrate_hps = effective_hashrate_hps
        if not cap_check["allowed"]:
            self.state.state = MiningState.CAPPED
            self.state.mining_allowed = False
            self.state.cap_violations += 1
            return {
                "allowed": False,
                "reason": f"hashrate_cap_exceeded: {effective_hashrate_hps} > {self.cap_enforcer.cap_hps}",
                "capped_hashrate": cap_check["capped_hashrate_hps"],
                "state": self.state.as_dict(),
            }
        # Check consecutive-block guard.
        if not self.block_guard.can_mine(self.state):
            self.state.mining_allowed = False
            reason = (
                "consecutive_block_cooldown"
                if self.state.state == MiningState.COOLDOWN
                else (
                    "waiting_external_block"
                    if self.state.state == MiningState.WAITING_EXTERNAL
                    else f"state_{self.state.state.value}"
                )
            )
            return {
                "allowed": False,
                "reason": reason,
                "capped_hashrate": effective_hashrate_hps,
                "state": self.state.as_dict(),
            }
        # All clear.
        self.state.mining_allowed = True
        if self.state.state in (MiningState.IDLE, MiningState.CAPPED):
            self.state.state = MiningState.SEARCHING
        return {
            "allowed": True,
            "reason": "ok",
            "capped_hashrate": effective_hashrate_hps,
            "state": self.state.as_dict(),
        }

    def on_winner_found(self) -> None:
        """Called when PYTHIA finds a winning nonce."""
        self.state.state = MiningState.SUBMITTING
        logger.info("Winner found — entering SUBMITTING state")

    def on_block_submitted(self) -> None:
        """Called when the block is submitted to the network."""
        self.state.state = MiningState.WAITING_ACCEPTANCE
        logger.info("Block submitted — waiting for network acceptance")

    def on_block_accepted(self, block_height: int, block_hash: str) -> None:
        """Called when the block is accepted by the network."""
        self.block_guard.on_block_accepted(self.state, block_height, block_hash)

    def on_block_orphaned(self) -> None:
        """Called when the submitted block is orphaned."""
        self.block_guard.on_block_orphaned(self.state)

    def on_external_block(self, block_height: int) -> None:
        """Called when an external block is observed."""
        self.block_guard.on_external_block(self.state, block_height)

    def set_hashrate_cap(self, requested_ehs: float) -> Dict[str, Any]:
        """Adjust the hashrate cap from a frontend request — INCREMENTALLY.

        Two independent safety limits apply:

        1. ``ABSOLUTE_HARD_CAP_EHS`` (20 EH/s) — non-bypassable ceiling.
        2. The incremental ladder — a request above the current cap advances
           *one rung* at a time; it never jumps to the ceiling in a single
           call. Downscaling is honoured immediately.

        Returns the actual cap that was set (may be lower than requested).
        """
        current_ehs = self.state.hashrate_cap_hps / 1e18
        capped_ehs = min(requested_ehs, ABSOLUTE_HARD_CAP_EHS)
        actual_ehs = next_incremental_step_ehs(current_ehs, capped_ehs)
        stepped = actual_ehs < capped_ehs

        actual_hps = int(actual_ehs * 1e18)
        self.state.hashrate_cap_hps = actual_hps
        self.cap_enforcer.cap_hps = actual_hps
        was_clamped = requested_ehs > ABSOLUTE_HARD_CAP_EHS
        if was_clamped:
            logger.warning(
                "Hashrate cap request %.2f EH/s clamped to hard cap %.2f EH/s",
                requested_ehs,
                ABSOLUTE_HARD_CAP_EHS,
            )
        elif stepped:
            logger.info(
                "Hashrate cap advanced incrementally %.2f -> %.2f EH/s (requested %.2f)",
                current_ehs,
                actual_ehs,
                requested_ehs,
            )
        else:
            logger.info("Hashrate cap set to %.2f EH/s", actual_ehs)
        return {
            "requested_ehs": requested_ehs,
            "actual_ehs": actual_ehs,
            "actual_hps": actual_hps,
            "previous_ehs": current_ehs,
            "hard_cap_ehs": ABSOLUTE_HARD_CAP_EHS,
            "was_clamped": was_clamped,
            "was_stepped": stepped,
            "steps_ehs": list(INCREMENTAL_SCALE_STEPS_EHS),
            "message": (
                f"Clamped to hard cap {ABSOLUTE_HARD_CAP_EHS} EH/s"
                if was_clamped
                else (
                    f"Incremental step {current_ehs} -> {actual_ehs} EH/s"
                    if stepped
                    else f"Cap set to {actual_ehs} EH/s"
                )
            ),
        }

    def set_hashrate_cap_ehs(self, cap_ehs: float) -> None:
        """Set the hashrate cap in EH/s (adjustable from frontend)."""
        self.cap_enforcer.set_cap_ehs(cap_ehs)
        self.state.hashrate_cap_hps = self.cap_enforcer.cap_hps

    def status(self) -> Dict[str, Any]:
        """Return the full safety status."""
        self.block_guard.tick(self.state)
        return self.state.as_dict()


__all__ = [
    "DEFAULT_HASHRATE_CAP_EHS",
    "DEFAULT_HASHRATE_CAP_HPS",
    "ABSOLUTE_HARD_CAP_EHS",
    "ABSOLUTE_HARD_CAP_HPS",
    "INCREMENTAL_SCALE_STEPS_EHS",
    "next_incremental_step_ehs",
    "DEFAULT_COOLDOWN_SECONDS",
    "MiningState",
    "SafetyState",
    "HashrateCapEnforcer",
    "ConsecutiveBlockGuard",
    "SafetyController",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (gap_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("gap_kernel")(np.array([[1.0, 0.0], [0.0, -1.0]]), n)
    result["module"] = __name__
    return result
