"""Mining safety FSM — the four-state cycle that governs every block.

CANONICITY: legacy block-lifecycle FSM used by the ``hyba/operating_model``
harness only; it is not the canonical production operational state
machine. The canonical cycle (STARTUP/SCAN -> PLAN -> MINE -> VERIFY ->
SUBMIT -> ACKNOWLEDGE -> EVALUATE/HEAL -> NEXT_CYCLE) is
``chronus.mla1517.mining.cycle_fsm``, driven by the production
coordinator. The persisted production block lifecycle lives in
``chronus.mla1517.mining.session.MiningSession``.


    SEARCHING → SUBMITTING → WAITING_EXTERNAL → COOLDOWN → SEARCHING

The machine may only transition through the declared edge table — no
ad-hoc state jumps. The binding invariant: **never two consecutive
blocks**. After a submitted block is accepted, at least one external
block must be observed (the WAITING_EXTERNAL → COOLDOWN leg) before the
machine will permit another mining attempt.
"""

# LUCAS WIRING: draws from lucas/ (pool). MUST NOT import from any
# sibling algorithm. Substrate route: step (4 machine states <= L_n).

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

THEOREM_PROVEN = False


class MiningState(Enum):
    """The four — and only four — mining safety states."""

    SEARCHING = "searching"
    SUBMITTING = "submitting"
    WAITING_EXTERNAL = "waiting_external"
    COOLDOWN = "cooldown"


# Declared edge table — the only legal transitions.
EDGES: Dict[MiningState, tuple[MiningState, ...]] = {
    MiningState.SEARCHING: (MiningState.SUBMITTING,),
    MiningState.SUBMITTING: (MiningState.WAITING_EXTERNAL,),
    MiningState.WAITING_EXTERNAL: (MiningState.COOLDOWN,),
    MiningState.COOLDOWN: (MiningState.SEARCHING,),
}


class IllegalTransition(Exception):
    """Raised when a transition is requested outside the edge table."""


class SafetyFSM:
    """Deterministic four-state mining safety machine.

    The invariant ``never two consecutive blocks`` is enforced by
    ``can_mine``: once a block is accepted, the machine must observe at
    least one external block before ``begin_search`` will admit a new
    attempt. Violation attempts are counted, not executed.
    """

    def __init__(self) -> None:
        self.state: MiningState = MiningState.SEARCHING
        self.last_mined_height: Optional[int] = None
        self._external_since_mine: int = 0
        self.consecutive_blocks_prevented: int = 0
        self.illegal_attempts: int = 0
        self.history: List[str] = [self.state.value]

    # -- transitions (edge-table only) -----------------------------------

    def _go(self, target: MiningState) -> None:
        if target not in EDGES[self.state]:
            self.illegal_attempts += 1
            raise IllegalTransition(f"{self.state.value} -> {target.value} is not a declared edge")
        self.state = target
        self.history.append(target.value)

    # -- events ------------------------------------------------------------

    def can_mine(self) -> bool:
        """True only in SEARCHING with the never-two-consecutive rule met."""
        if self.state is not MiningState.SEARCHING:
            return False
        return self.last_mined_height is None or self._external_since_mine >= 1

    def begin_search(self) -> bool:
        """Ask permission to search. Never grants two consecutive blocks."""
        if not self.can_mine():
            self.consecutive_blocks_prevented += 1
            return False
        return True

    def on_winner_found(self) -> None:
        """A winning nonce was found while SEARCHING -> SUBMITTING."""
        self._go(MiningState.SUBMITTING)

    def on_block_accepted(self, block_height: int) -> None:
        """Submitted block accepted -> WAITING_EXTERNAL."""
        self._go(MiningState.WAITING_EXTERNAL)
        self.last_mined_height = block_height
        self._external_since_mine = 0

    def on_block_orphaned(self) -> None:
        """An unsuccessful submission still waits for external work."""
        self._go(MiningState.WAITING_EXTERNAL)

    def on_external_block(self, block_height: int) -> None:
        """External block observed -> COOLDOWN (from WAITING_EXTERNAL)."""
        if self.state is MiningState.WAITING_EXTERNAL:
            if (
                type(block_height) is not int
                or block_height < 0
                or (self.last_mined_height is not None and block_height <= self.last_mined_height)
            ):
                raise ValueError("external block must advance the mined height")
            self._external_since_mine += 1
            self._go(MiningState.COOLDOWN)

    def cooldown_complete(self) -> None:
        """Cooldown leg finishes -> SEARCHING."""
        if self.state is MiningState.COOLDOWN:
            self._go(MiningState.SEARCHING)

    # -- introspection -----------------------------------------------------

    def visited(self) -> List[str]:
        """Ordered list of every state entered since boot."""
        return list(self.history)

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "mining_allowed": self.can_mine(),
            "last_mined_block_height": self.last_mined_height,
            "external_blocks_since_mine": self._external_since_mine,
            "consecutive_blocks_prevented": self.consecutive_blocks_prevented,
            "illegal_transition_attempts": self.illegal_attempts,
            "states_declared": [s.value for s in MiningState],
            "states_visited": self.visited(),
            "theorem_proven": False,
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    The bounded quantity is the machine's declared state count (4), which
    must sit under the step_kernel ceiling L_n.
    """
    from lucas.pool import get as _lucas_get

    result = _lucas_get("step_kernel")({"states": len(MiningState)}, n)
    result["module"] = __name__
    return result
