"""Generation-scoped nonce lease ledger.

Every search window — agentic or baseline fallback — must hold a lease before
it can reach the executor. A lease names one contiguous nonce range on one
header template (``extranonce2``) inside one Stratum work identity.

Invariants enforced here (never left to callers):
  * RESERVED/EXECUTING leases never overlap each other or completed coverage.
  * A lease belongs to exactly one work identity; rebinding invalidates all.
  * COMPLETE and INVALIDATED are terminal: neither can execute again.
  * An ``extranonce2`` returned twice by the allocator within one identity is
    refused — the work space is exhausted rather than silently duplicated.

Reordering nonces inside a lease is allowed; duplicating coverage is not.
The ledger never inspects hashes, targets or shares.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import Any, Callable, Hashable

from .search_plan import LeaseState, NonceLease

NONCE_SPACE = 1 << 32
LANE_ALIGN = 32
# How many recently worked header spaces keep their coverage across rebinds,
# and how many extranonce2 values may be skipped looking for a fresh one.
_WORK_SPACE_MEMORY = 8
_EXTRANONCE2_SKIP_LIMIT = 64


class LeaseConflict(RuntimeError):
    """The requested lease would duplicate or bypass leased coverage."""


class LeaseExhausted(RuntimeError):
    """No fresh work space remains in the bound identity."""


@dataclass(frozen=True)
class LeaseRecord:
    """Ledger entry; ``contract()`` yields the executor-facing ``NonceLease``."""

    lease_id: str
    identity_key: Hashable
    generation: int
    extranonce2: str
    start: int
    count: int
    state: LeaseState

    @property
    def end(self) -> int:
        return self.start + self.count

    def contract(self) -> NonceLease:
        return NonceLease(
            lease_id=self.lease_id,
            generation=self.generation,
            plan_id=self.lease_id,
            start=self.start,
            count=self.count,
            state=self.state,
        )


def lease_span(window: int) -> int:
    """Nonces a lane-aligned M32 sweep of ``window`` steps may touch."""
    if window <= 0:
        raise ValueError("window must be positive")
    return -(-window // LANE_ALIGN) * LANE_ALIGN


class NonceLeaseLedger:
    def __init__(self, *, max_active: int = 16, terminal_memory: int = 512) -> None:
        if max_active <= 0 or terminal_memory <= 0:
            raise ValueError("ledger bounds must be positive")
        self._max_active = max_active
        self._terminal_memory = terminal_memory
        self._identity_key: Hashable | None = None
        self._generation = 0
        self._active: dict[str, LeaseRecord] = {}
        self._terminal: OrderedDict[str, LeaseRecord] = OrderedDict()
        self._covered: dict[str, list[list[int]]] = {}
        self._units: list[str] = []
        self._cursor = 0
        self._work_space: Hashable | None = None
        self._carried: set[str] = set()
        self._history: OrderedDict[Hashable, tuple[set[str], dict[str, list[list[int]]]]] = (
            OrderedDict()
        )
        self.invalidated_total = 0
        self.completed_total = 0
        self.carried_units_total = 0

    # ------------------------------------------------------------------ #
    def bind(
        self, identity_key: Hashable, generation: int, *, work_space: Hashable | None = None
    ) -> int:
        """Bind to a Stratum identity; a different key invalidates everything.

        ``work_space`` names the header space (Stratum's job fingerprint).
        When a reconnect lands on a space already worked, its completed
        coverage and used extranonce2 values carry over, so no nonce range is
        hashed twice; leases themselves never carry over.
        """
        if identity_key == self._identity_key:
            return 0
        self._remember()
        invalidated = self._reset()
        self._identity_key = identity_key
        self._generation = generation
        self._work_space = work_space
        if work_space is not None and work_space in self._history:
            units, covered = self._history[work_space]
            self._carried = set(units)
            self._covered = {k: [list(iv) for iv in v] for k, v in covered.items()}
            self.carried_units_total += len(units)
        return invalidated

    def _remember(self) -> None:
        if self._work_space is None:
            return
        units = set(self._units) | self._carried
        if not units:
            return
        self._history[self._work_space] = (
            units,
            {k: [list(iv) for iv in v] for k, v in self._covered.items()},
        )
        self._history.move_to_end(self._work_space)
        while len(self._history) > _WORK_SPACE_MEMORY:
            self._history.popitem(last=False)

    def unbind(self) -> int:
        self._remember()
        invalidated = self._reset()
        self._identity_key = None
        self._generation = 0
        return invalidated

    def _reset(self) -> int:
        invalidated = 0
        for lease in list(self._active.values()):
            self._retire(replace(lease, state=LeaseState.INVALIDATED))
            invalidated += 1
        self._active.clear()
        self._covered.clear()
        self._units.clear()
        self._carried = set()
        self._work_space = None
        self._cursor = 0
        self.invalidated_total += invalidated
        return invalidated

    @property
    def bound(self) -> bool:
        return self._identity_key is not None

    # ------------------------------------------------------------------ #
    def allocate(
        self, lease_id: str, window: int, allocate_extranonce2: Callable[[], str]
    ) -> LeaseRecord:
        """Reserve the next fresh lane-aligned range covering ``window`` steps."""
        if self._identity_key is None:
            raise LeaseConflict("no Stratum work identity is bound")
        span = lease_span(window)
        if span > NONCE_SPACE:
            raise LeaseConflict("window exceeds the nonce space")
        if not self._units or self._cursor + span > NONCE_SPACE:
            seen = set(self._units) | set(self._covered) | self._carried
            seen |= {lease.extranonce2 for lease in self._active.values()}
            for _ in range(_EXTRANONCE2_SKIP_LIMIT):
                extranonce2 = allocate_extranonce2()
                if extranonce2 not in seen:
                    break
            else:
                raise LeaseExhausted("extranonce2 space exhausted for this generation")
            self._units.append(extranonce2)
            self._cursor = 0
        lease = self.reserve_range(lease_id, self._units[-1], self._cursor, span)
        self._cursor += span
        return lease

    def reserve_range(self, lease_id: str, extranonce2: str, start: int, count: int) -> LeaseRecord:
        if self._identity_key is None:
            raise LeaseConflict("no Stratum work identity is bound")
        if not lease_id or lease_id in self._active or lease_id in self._terminal:
            raise LeaseConflict(f"lease id {lease_id!r} is not fresh")
        if count <= 0 or start < 0 or start + count > NONCE_SPACE:
            raise LeaseConflict("lease range outside the uint32 nonce space")
        if start % LANE_ALIGN:
            raise LeaseConflict("lease start must be lane-aligned")
        if len(self._active) >= self._max_active:
            raise LeaseConflict("active lease bound reached")
        end = start + count
        for other in self._active.values():
            if other.extranonce2 == extranonce2 and start < other.end and other.start < end:
                raise LeaseConflict(f"overlaps {other.state.value} lease {other.lease_id}")
        for lo, hi in self._covered.get(extranonce2, ()):
            if start < hi and lo < end:
                raise LeaseConflict("overlaps completed coverage")
        lease = LeaseRecord(
            lease_id,
            self._identity_key,
            self._generation,
            extranonce2,
            start,
            count,
            LeaseState.RESERVED,
        )
        self._active[lease_id] = lease
        return lease

    def begin(self, lease_id: str, identity_key: Hashable) -> LeaseRecord:
        """RESERVED → EXECUTING, only for the currently bound identity."""
        lease = self._active.get(lease_id)
        if lease is None:
            terminal = self._terminal.get(lease_id)
            state = terminal.state.value if terminal else "UNKNOWN"
            raise LeaseConflict(f"lease {lease_id!r} cannot execute from {state}")
        if lease.state is not LeaseState.RESERVED:
            raise LeaseConflict(f"lease {lease_id!r} is already {lease.state.value}")
        if identity_key != self._identity_key or lease.identity_key != identity_key:
            raise LeaseConflict("lease belongs to a different work identity")
        lease = replace(lease, state=LeaseState.EXECUTING)
        self._active[lease_id] = lease
        return lease

    def complete(self, lease_id: str) -> bool:
        """EXECUTING → COMPLETE. False when the lease was invalidated meanwhile."""
        lease = self._active.get(lease_id)
        if lease is None:
            return False
        if lease.state is not LeaseState.EXECUTING:
            raise LeaseConflict(f"lease {lease_id!r} is {lease.state.value}, not EXECUTING")
        del self._active[lease_id]
        self._cover(lease.extranonce2, lease.start, lease.end)
        self._retire(replace(lease, state=LeaseState.COMPLETE))
        self.completed_total += 1
        return True

    def invalidate(self, lease_id: str) -> bool:
        lease = self._active.pop(lease_id, None)
        if lease is None:
            return False
        self._retire(replace(lease, state=LeaseState.INVALIDATED))
        self.invalidated_total += 1
        return True

    def invalidate_reserved(self) -> int:
        """Cancel speculative (RESERVED) leases; EXECUTING work may finish."""
        ids = [i for i, lease in self._active.items() if lease.state is LeaseState.RESERVED]
        for lease_id in ids:
            self.invalidate(lease_id)
        return len(ids)

    def get(self, lease_id: str) -> LeaseRecord | None:
        return self._active.get(lease_id) or self._terminal.get(lease_id)

    @staticmethod
    def new_fallback_id() -> str:
        return f"fallback:{uuid.uuid4()}"

    # ------------------------------------------------------------------ #
    def _cover(self, extranonce2: str, start: int, end: int) -> None:
        merged: list[list[int]] = []
        for lo, hi in sorted(self._covered.get(extranonce2, []) + [[start, end]]):
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        self._covered[extranonce2] = merged

    def _retire(self, lease: LeaseRecord) -> None:
        self._terminal[lease.lease_id] = lease
        while len(self._terminal) > self._terminal_memory:
            self._terminal.popitem(last=False)

    def snapshot(self) -> dict[str, Any]:
        states = [lease.state.value for lease in self._active.values()]
        return {
            "bound": self.bound,
            "generation": self._generation if self.bound else None,
            "reserved": states.count(LeaseState.RESERVED.value),
            "executing": states.count(LeaseState.EXECUTING.value),
            "completed_total": self.completed_total,
            "invalidated_total": self.invalidated_total,
            "work_units": len(self._units),
            "carried_units_total": self.carried_units_total,
            "covered_nonces": sum(hi - lo for iv in self._covered.values() for lo, hi in iv),
        }
