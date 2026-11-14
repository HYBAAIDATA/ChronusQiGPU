# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""HERMES-style lease scheduling for the fleet.

* Capability-weighted apportionment: a job's tiles are grouped into lease
  groups and dealt to node queues in proportion to each node's measured
  throughput for that kernel (items per second from timed runs). A node with
  no measurement gets weight 1 and is labelled unmeasured; no weight is ever
  taken from a datasheet or a claimed core count.
* Leases expire. A lease is renewed by its node's heartbeats up to a hard
  maximum age; an expired lease returns its group for blind-check recovery.
* Work stealing: an idle node first takes its own queue, then unassigned
  groups, then steals from the tail of other nodes' queues in order of H4
  crossbar distance (see ``chronus.fleet.crossbar``).
* Disaggregated pools (spec 2.1, P3): each work unit draws on the prefill or
  decode pool. A pool may hold at most ratio x tier lanes of tiles in flight;
  PREFILL_RATIO + DECODE_RATIO must not exceed 1.

This module is a data structure; the coordinator serialises access with its
lock. (The ``chronus.hermes`` namespace remains the acceleration namespace
from PR #29; the fleet scheduler lives here.)
"""

from __future__ import annotations

import secrets
from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Iterable, Mapping

from chronus.fleet.crossbar import H4Crossbar
from chronus.fleet.errors import TierGateRejected
from chronus.fleet.workunit import POOL_DECODE, POOL_PREFILL, POOLS, ROUTE_AUTO

PREFILL_RATIO = Fraction(1, 4)
DECODE_RATIO = Fraction(3, 4)
GROUPS_PER_NODE = 4


def pool_budgets(tier_lanes: int, prefill: Fraction = PREFILL_RATIO, decode: Fraction = DECODE_RATIO) -> dict[str, int]:
    """Lanes (tiles in flight) each pool may hold; the spec's P3 assertion included."""
    prefill, decode = Fraction(prefill), Fraction(decode)
    if prefill < 0 or decode < 0:
        raise TierGateRejected("pool ratios must be non-negative")
    if prefill + decode > 1:
        raise TierGateRejected(f"PREFILL_RATIO + DECODE_RATIO = {prefill + decode} > 1.0 (P3)")
    budgets = {POOL_PREFILL: int(tier_lanes * prefill), POOL_DECODE: int(tier_lanes * decode)}
    if budgets[POOL_PREFILL] + budgets[POOL_DECODE] > tier_lanes:
        raise TierGateRejected("pools exceed the tier lanes")
    return budgets


@dataclass
class NodeInfo:
    node_id: str
    label: str
    owner: str
    resident_units: int
    warps: int
    lanes: int
    routes: dict[str, dict[str, Any]]
    kernels: dict[str, str]
    vertex: int
    joined_at: str
    last_seen_ns: int
    throughput: dict[tuple[str, str], int] = field(default_factory=dict)
    alive: bool = True
    quarantined: str | None = None
    state: str = "active"
    backend: dict[str, Any] = field(default_factory=dict)
    host_capacity: dict[str, Any] = field(default_factory=dict)
    join_sequence: int = 0

    def verified_routes(self, kernel: str) -> list[str]:
        return [r for r, info in self.routes.items() if kernel in info.get("verified_kernels", ())]

    def offers(self, kernel: str, version: str, route: str) -> bool:
        """Whether this live machine offers the route for the kernel, admitted or waiting."""
        if not self.alive or self.quarantined or self.kernels.get(kernel) != version:
            return False
        verified = self.verified_routes(kernel)
        return bool(verified) if route == ROUTE_AUTO else route in verified

    def eligible(self, kernel: str, version: str, route: str, excluded: Iterable[str] = ()) -> bool:
        if not self.alive or self.quarantined or self.state == "waiting" or self.node_id in set(excluded):
            return False
        if self.kernels.get(kernel) != version:
            return False
        verified = self.verified_routes(kernel)
        return bool(verified) if route == ROUTE_AUTO else route in verified

    def weight(self, kernel: str, route: str) -> tuple[int, bool]:
        """(weight, measured). Unmeasured nodes weigh 1."""
        routes = self.verified_routes(kernel) if route == ROUTE_AUTO else [route]
        rates = [self.throughput.get((kernel, r)) for r in routes]
        rates = [r for r in rates if r]
        if not rates:
            return 1, False
        return max(rates), True

    def public(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "owner": self.owner,
            "state": self.state,
            "alive": self.alive,
            "quarantined": self.quarantined,
            "resident_virtual_units": self.resident_units,
            "logical_warps": self.warps,
            "logical_lanes": self.lanes,
            "crossbar_vertex": self.vertex,
            "joined_at": self.joined_at,
            "routes": self.routes,
            "kernels": self.kernels,
            "measured_items_per_second": {f"{k}/{r}": v for (k, r), v in sorted(self.throughput.items())},
            "backend": dict(self.backend),
            "host_capacity": dict(self.host_capacity) or None,
        }


@dataclass
class LeaseGroup:
    job_id: str
    first_tile: int
    stop_tile: int
    pool: str = POOL_DECODE
    incident: str | None = None
    attempt: int = 0
    excluded: frozenset[str] = frozenset()

    @property
    def size(self) -> int:
        return self.stop_tile - self.first_tile

    def tiles(self) -> range:
        return range(self.first_tile, self.stop_tile)


@dataclass
class Lease:
    lease_id: str
    group: LeaseGroup
    node_id: str
    issued_ns: int
    expires_ns: int
    deadline_ns: int


def split_groups(job_id: str, tiles: int, groups: int, pool: str) -> list[LeaseGroup]:
    groups = max(1, min(groups, tiles))
    base, extra = divmod(tiles, groups)
    out, start = [], 0
    for i in range(groups):
        size = base + (1 if i < extra else 0)
        out.append(LeaseGroup(job_id, start, start + size, pool))
        start += size
    return out


def apportion(weights: Mapping[str, int], count: int) -> dict[str, int]:
    """Largest-remainder apportionment of count items by integer weight."""
    total = sum(weights.values())
    if count <= 0 or total <= 0:
        return {node: 0 for node in weights}
    quotas = {node: Fraction(count * w, total) for node, w in weights.items()}
    shares = {node: int(q) for node, q in quotas.items()}
    left = count - sum(shares.values())
    for node in sorted(quotas, key=lambda n: (-(quotas[n] - shares[n]), n))[:left]:
        shares[node] += 1
    return shares


class LeaseScheduler:
    def __init__(
        self,
        crossbar: H4Crossbar,
        lease_ttl_ns: int,
        max_lease_age_ns: int,
        pool_lanes: Mapping[str, int],
    ) -> None:
        self.crossbar = crossbar
        self.lease_ttl_ns = lease_ttl_ns
        self.max_lease_age_ns = max_lease_age_ns
        self.pool_lanes = dict(pool_lanes)
        self.pool_inflight = {pool: 0 for pool in POOLS}
        self.queues: dict[str, deque[LeaseGroup]] = {}
        self.unassigned: deque[LeaseGroup] = deque()
        self.inflight: dict[str, Lease] = {}

    # -- nodes ---------------------------------------------------------------
    def add_node(self, node_id: str) -> None:
        self.queues.setdefault(node_id, deque())

    def drop_node(self, node_id: str) -> list[LeaseGroup]:
        """Remove a node; its queued (not yet started) groups go back to the unassigned queue."""
        queued = list(self.queues.pop(node_id, deque()))
        for group in queued:
            self.unassigned.append(group)
        return queued

    # -- planning ------------------------------------------------------------
    def plan(
        self, job_id: str, tiles: int, pool: str, weights: Mapping[str, int], min_groups: int = 1
    ) -> dict[str, list[LeaseGroup]]:
        """Split a job's tiles into groups and deal them to node queues by weight."""
        if not weights:
            groups = split_groups(job_id, tiles, max(1, min_groups), pool)
            self.unassigned.extend(groups)
            return {}
        groups = split_groups(job_id, tiles, max(min_groups, GROUPS_PER_NODE * len(weights)), pool)
        shares = apportion(weights, len(groups))
        dealt: dict[str, list[LeaseGroup]] = {}
        cursor = 0
        for node in sorted(shares, key=lambda n: (self.crossbar.vertex_of(n) if self.crossbar.placed(n) else 0, n)):
            take = groups[cursor : cursor + shares[node]]
            cursor += shares[node]
            if take:
                self.queues.setdefault(node, deque()).extend(take)
                dealt[node] = take
        return dealt

    def requeue(self, group: LeaseGroup, node_id: str | None = None, front: bool = True) -> None:
        target = self.queues.get(node_id) if node_id is not None else None
        queue = target if target is not None else self.unassigned
        if front:
            queue.appendleft(group)
        else:
            queue.append(group)

    def discard_job(self, job_id: str) -> None:
        for queue in list(self.queues.values()) + [self.unassigned]:
            keep = [g for g in queue if g.job_id != job_id]
            queue.clear()
            queue.extend(keep)
        for lease_id in [i for i, lease in self.inflight.items() if lease.group.job_id == job_id]:
            self.release(lease_id)

    # -- leasing -------------------------------------------------------------
    def _fits_pool(self, group: LeaseGroup) -> bool:
        return self.pool_inflight[group.pool] + group.size <= self.pool_lanes.get(group.pool, 0)

    def _take(self, queue: deque, usable: Callable[[LeaseGroup], bool], from_tail: bool) -> LeaseGroup | None:
        order = range(len(queue) - 1, -1, -1) if from_tail else range(len(queue))
        for index in order:
            group = queue[index]
            if usable(group) and self._fits_pool(group):
                del queue[index]
                return group
        return None

    def acquire(self, node_id: str, usable: Callable[[LeaseGroup], bool], now_ns: int) -> tuple[Lease, str] | None:
        """Next lease for node_id: own queue, then unassigned, then steal. Returns (lease, source)."""
        source = "own-queue"
        group = self._take(self.queues.setdefault(node_id, deque()), usable, from_tail=False)
        if group is None:
            source = "unassigned"
            group = self._take(self.unassigned, usable, from_tail=False)
        if group is None:
            victims = {
                other: self.crossbar.vertex_of(other)
                for other, queue in self.queues.items()
                if other != node_id and queue and self.crossbar.placed(other)
            }
            for victim in self.crossbar.steal_order(node_id, victims):
                group = self._take(self.queues[victim], lambda g: g.incident is None and usable(g), from_tail=True)
                if group is not None:
                    source = f"stolen-from:{victim}"
                    break
        if group is None:
            return None
        lease = Lease(
            lease_id=secrets.token_hex(12),
            group=group,
            node_id=node_id,
            issued_ns=now_ns,
            expires_ns=now_ns + self.lease_ttl_ns,
            deadline_ns=now_ns + self.max_lease_age_ns,
        )
        self.inflight[lease.lease_id] = lease
        self.pool_inflight[group.pool] += group.size
        return lease, source

    def renew(self, node_id: str, lease_ids: Iterable[str], now_ns: int) -> int:
        renewed = 0
        for lease_id in lease_ids:
            lease = self.inflight.get(lease_id)
            if lease is not None and lease.node_id == node_id and now_ns <= lease.expires_ns:
                lease.expires_ns = min(now_ns + self.lease_ttl_ns, lease.deadline_ns)
                renewed += 1
        return renewed

    def release(self, lease_id: str) -> Lease | None:
        lease = self.inflight.pop(lease_id, None)
        if lease is not None:
            self.pool_inflight[lease.group.pool] -= lease.group.size
        return lease

    def expired(self, now_ns: int) -> list[Lease]:
        gone = [lease_id for lease_id, lease in self.inflight.items() if lease.expires_ns < now_ns]
        return [lease for lease in (self.release(i) for i in gone) if lease is not None]

    def leases_of(self, node_id: str) -> list[Lease]:
        return [lease for lease in self.inflight.values() if lease.node_id == node_id]

    def queue_lengths(self) -> dict[str, int]:
        lengths = {node: len(queue) for node, queue in self.queues.items()}
        lengths["unassigned"] = len(self.unassigned)
        return lengths
