# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Blind-check fault recovery (spec 2.3, P2a/P2b/P2c).

When a worker dies, leaves, lets a lease expire or reports a failed lease,
its unfinished lease groups become a ``FaultedState``. Two channels then act:

CHANNEL A, ``RecoveryChannel`` (recovery). Sees only the faulted state and the
surviving nodes' measured weights. It constructs the recovery path, applies it
(the groups are re-leased to survivors) and, once every tile is back, commits
to the recovered outputs with a Merkle root.

CHANNEL B, ``BaselineChannel`` (baseline). Holds the reference route and its
own randomness. Only after receiving channel A's commitment does it draw the
verification set V (a random subset of the recovered tiles, never empty),
recompute V on the reference and return pass or fail with counts. Channel A
has no reference to channel B or to V, and V does not exist until A has
committed, so the recovery path cannot have been built to satisfy V.

P2a decision: candidate (i). The recovery path is a deterministic
re-execution circuit: an assignment of each orphaned group to a surviving
node, weighted by measured throughput. P2b: because (i) is a circuit there is
no action functional, so the minimum-action assertion is deleted.
ONE_CYCLE is one recovery round; a blind-check failure opens a second round on
other nodes and the receipt records ``one_cycle: false``.
"""

from __future__ import annotations

import secrets
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from chronus.fleet.canonical import digest_json, iso_utc, merkle_root, sha256_hex
from chronus.fleet.errors import RecoveryError
from chronus.fleet.scheduler import LeaseGroup, apportion

ONE_CYCLE = 1
TileKey = tuple[str, int]


@dataclass(frozen=True)
class FaultedState:
    incident_id: str
    failed_node: str
    cause: str
    groups: tuple[LeaseGroup, ...]
    detected_at: str

    def tiles(self) -> list[TileKey]:
        return [(g.job_id, t) for g in self.groups for t in g.tiles()]

    def describe(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "failed_node": self.failed_node,
            "cause": self.cause,
            "orphaned_groups": [[g.job_id, g.first_tile, g.stop_tile] for g in self.groups],
            "orphaned_tiles": len(self.tiles()),
            "detected_at": self.detected_at,
        }


@dataclass(frozen=True)
class RecoveryPath:
    """P2a (i): which surviving node re-executes each orphaned group."""

    incident_id: str
    assignments: tuple[tuple[LeaseGroup, str], ...]

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "re-execution circuit (P2a candidate i)",
            "assignments": [[g.job_id, g.first_tile, g.stop_tile, node] for g, node in self.assignments],
        }


@dataclass(frozen=True)
class BlindCheckResult:
    passed: bool
    checked: int
    failed: int
    commitment: str
    verification_set_digest: str
    failed_nodes: tuple[str, ...] = ()
    corrected: Mapping[TileKey, bytes] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "tiles_checked": self.checked,
            "tiles_failed": self.failed,
            "commitment": self.commitment,
            "verification_set_digest": self.verification_set_digest,
            "verification_set_drawn": "after commitment, by the baseline channel",
            "failed_nodes": list(self.failed_nodes),
        }


def commitment_of(recovered: Mapping[TileKey, tuple[str, bytes]]) -> str:
    """Merkle root over (job, tile, node, output digest) in sorted tile order."""
    leaves = [
        sha256_hex(f"{job}:{tile}:{recovered[(job, tile)][0]}:{sha256_hex(recovered[(job, tile)][1])}".encode())
        for job, tile in sorted(recovered)
    ]
    return merkle_root(leaves)


class RecoveryChannel:
    """CHANNEL A: builds and applies the recovery path from the faulted state alone."""

    def construct_recovery_path(self, faulted: FaultedState, survivors: Mapping[str, int]) -> RecoveryPath:
        if not faulted.groups:
            raise RecoveryError("faulted state has no orphaned work")
        candidates = {n: w for n, w in survivors.items() if n != faulted.failed_node and w > 0}
        if not candidates:
            raise RecoveryError("no surviving node can take the orphaned work")
        shares = apportion(candidates, len(faulted.groups))
        order = [node for node in sorted(candidates) for _ in range(shares[node])]
        assignments = tuple(
            (LeaseGroup(g.job_id, g.first_tile, g.stop_tile, g.pool, faulted.incident_id, g.attempt + 1,
                        g.excluded | {faulted.failed_node}), node)
            for g, node in zip(faulted.groups, order)
        )
        return RecoveryPath(faulted.incident_id, assignments)

    def apply(self, path: RecoveryPath, requeue: Callable[[LeaseGroup, str], None]) -> int:
        for group, node in path.assignments:
            requeue(group, node)
        return len(path.assignments)

    def commit(self, recovered: Mapping[TileKey, tuple[str, bytes]]) -> str:
        if not recovered:
            raise RecoveryError("nothing recovered to commit")
        return commitment_of(recovered)


class BaselineChannel:
    """CHANNEL B: draws V after the commitment and checks it on the reference route."""

    def __init__(self, reference: Callable[[str, int], bytes], sample_ppm: int = 500_000, minimum: int = 1) -> None:
        if not 0 < sample_ppm <= 1_000_000:
            raise ValueError("recovery sample must be in (0, 1000000] parts per million")
        self.__reference = reference
        self.__sample_ppm = sample_ppm
        self.__minimum = max(1, minimum)

    def evaluate(self, commitment: str, recovered: Mapping[TileKey, tuple[str, bytes]]) -> BlindCheckResult:
        if commitment_of(recovered) != commitment:
            raise RecoveryError("recovered outputs do not match channel A's commitment")
        tiles = sorted(recovered)
        size = max(self.__minimum, -(-len(tiles) * self.__sample_ppm // 1_000_000))
        size = min(size, len(tiles))
        verification_set = sorted(_draw(tiles, size))
        failed_nodes: set[str] = set()
        corrected: dict[TileKey, bytes] = {}
        failures = 0
        for key in verification_set:
            node, output = recovered[key]
            expected = self.__reference(*key)
            if sha256_hex(expected) != sha256_hex(output):
                failures += 1
                failed_nodes.add(node)
                corrected[key] = expected
        return BlindCheckResult(
            passed=failures == 0,
            checked=len(verification_set),
            failed=failures,
            commitment=commitment,
            verification_set_digest=digest_json([[job, tile] for job, tile in verification_set]),
            failed_nodes=tuple(sorted(failed_nodes)),
            corrected=corrected,
        )


def _draw(items: list[TileKey], size: int) -> list[TileKey]:
    return random.SystemRandom().sample(items, size)


@dataclass
class Incident:
    faulted: FaultedState
    path: RecoveryPath | None = None
    round: int = 1
    retry_of: str | None = None
    recovered: dict[TileKey, tuple[str, bytes]] = field(default_factory=dict)
    expected: set[TileKey] = field(default_factory=set)
    commitment: str | None = None
    result: BlindCheckResult | None = None
    status: str = "recovering"
    opened_at: str = field(default_factory=iso_utc)
    closed_at: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.expected) and self.expected <= set(self.recovered)

    def jobs(self) -> set[str]:
        return {g.job_id for g in self.faulted.groups}

    def describe(self) -> dict[str, Any]:
        return {
            **self.faulted.describe(),
            "round": self.round,
            "retry_of": self.retry_of,
            "recovery_path": self.path.describe() if self.path else None,
            "recovered_tiles": len(self.recovered),
            "commitment": self.commitment,
            "blind_check": self.result.describe() if self.result else None,
            "status": self.status,
            "one_cycle": self.round <= ONE_CYCLE and self.status == "verified",
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
        }


def new_incident_id() -> str:
    return "inc-" + secrets.token_hex(6)


def survivors_from(nodes: Iterable[Any], kernel: str, version: str, route: str, failed: str) -> dict[str, int]:
    """Measured weights of nodes eligible to re-run a kernel, excluding the failed node."""
    out = {}
    for node in nodes:
        if node.node_id != failed and node.eligible(kernel, version, route):
            out[node.node_id] = node.weight(kernel, route)[0]
    return out
