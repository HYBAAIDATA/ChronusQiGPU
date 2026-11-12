# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Value-share reconciliation from verified fleet contribution (spec 4.1).

P7a decision: participants are owners (the ``owner`` a worker joins with and
the ``submitter`` of a job). ``V[i][j]`` is the number of work items that
participant i's devices executed, and that were accepted after verification,
for jobs submitted by participant j during the closed period. Entries are
measured counts taken from signed receipts, never estimates.

P7b: choice (a) as the spec states, the right Perron eigenvector of V
(V s = rho s), normalised to sum 1. Computed in float64 with numpy and
compared with an absolute tolerance of 1e-9.

P11: exactly four designated participants, each at 0.25, and every other
participant at 0. Because the Perron vector of an irreducible matrix is
strictly positive, V must contain only the four designated participants, and
their shares come out equal only when the value they contributed is balanced.
As written, the rule is therefore a balance check, not an allocation; see
docs/fleet/DECISIONS.md. Reconciliation runs in Tier 4 and the Scale tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from chronus.fleet.errors import TierGateRejected, VerificationError
from chronus.fleet.phase import TIER_4, Tier

TOLERANCE = 1e-9
DESIGNATED_COUNT = 4
DESIGNATED_SHARE = 0.25


@dataclass(frozen=True)
class Contribution:
    executor: str
    consumer: str
    verified_items: int


def contributions_from_receipts(receipts: Iterable[Mapping[str, Any]]) -> list[Contribution]:
    """Verified items per (device owner, job submitter) from signed receipts."""
    out = []
    for receipt in receipts:
        consumer = str(receipt.get("submitter") or "unknown")
        for device in receipt.get("devices", []):
            share = int(device.get("items", 0))
            if device.get("measured") is True and share > 0:
                out.append(Contribution(str(device.get("owner") or "unknown"), consumer, share))
    return out


def build_value_share_matrix(contributions: Iterable[Contribution], participants: Sequence[str]) -> list[list[int]]:
    """P7a: V[i][j] = verified items participant i executed for participant j."""
    index = {p: i for i, p in enumerate(participants)}
    if len(index) != len(participants):
        raise VerificationError("participants must be distinct")
    matrix = [[0] * len(participants) for _ in participants]
    for c in contributions:
        if c.verified_items < 0:
            raise VerificationError("contributions are non-negative counts")
        if c.executor not in index or c.consumer not in index:
            raise VerificationError(f"contribution names an unlisted participant: {c.executor} -> {c.consumer}")
        matrix[index[c.executor]][index[c.consumer]] += c.verified_items
    return matrix


def is_irreducible(matrix: Sequence[Sequence[int]]) -> bool:
    """Strong connectivity of the graph i -> j for V[i][j] > 0 (a 1x1 matrix needs V[0][0] > 0)."""
    n = len(matrix)
    if n == 0:
        return False
    if n == 1:
        return matrix[0][0] > 0

    def reach(edges: Callable[[int], list[int]]) -> set[int]:
        seen, stack = {0}, [0]
        while stack:
            u = stack.pop()
            for v in edges(u):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen

    forward = reach(lambda u: [v for v in range(n) if matrix[u][v] > 0])
    backward = reach(lambda u: [v for v in range(n) if matrix[v][u] > 0])
    return len(forward) == n and len(backward) == n



def perron_vector(matrix: Sequence[Sequence[int]]) -> tuple[float, list[float]]:
    """(Perron root, right Perron vector normalised to sum 1)."""
    import numpy as np

    values, vectors = np.linalg.eig(np.array(matrix, dtype=float))
    k = int(np.argmax(values.real))
    vector = np.abs(vectors[:, k].real)
    total = float(vector.sum())
    if total <= 0:
        raise VerificationError("Perron vector is degenerate")
    return float(values[k].real), [float(x) / total for x in vector]


@dataclass(frozen=True)
class ValueShareResult:
    participants: tuple[str, ...]
    matrix: tuple[tuple[int, ...], ...]
    perron_root: float
    shares: tuple[float, ...]
    designated: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": "P7b (a): right Perron eigenvector of V",
            "participants": list(self.participants),
            "matrix": [list(row) for row in self.matrix],
            "perron_root": self.perron_root,
            "shares": dict(zip(self.participants, self.shares)),
            "designated": list(self.designated),
        }


def reconcile_value_share(
    tier: Tier,
    participants: Sequence[str],
    contributions: Iterable[Contribution],
    designated: Sequence[str],
    period_closed: bool,
) -> ValueShareResult:
    if tier.number < TIER_4.number:
        raise TierGateRejected("value-share reconciliation is a Tier 4 (and Scale) capability")
    if not period_closed:
        raise VerificationError("the period must be closed before reconciliation")
    if len(set(designated)) != DESIGNATED_COUNT:
        raise VerificationError(f"P11: exactly {DESIGNATED_COUNT} designated participants are required")
    matrix = build_value_share_matrix(contributions, participants)
    if any(value < 0 for row in matrix for value in row):
        raise VerificationError("V must be non-negative")
    if not is_irreducible(matrix):
        raise VerificationError("V must be irreducible for a unique Perron vector")
    root, shares = perron_vector(matrix)
    if root <= 0:
        raise VerificationError("Perron root must be positive")
    if abs(sum(shares) - 1.0) > TOLERANCE:
        raise VerificationError("shares do not sum to 1")
    for name, share in zip(participants, shares):
        target = DESIGNATED_SHARE if name in designated else 0.0
        if abs(share - target) > TOLERANCE:
            raise VerificationError(f"P11: {name} has share {share:.12f}, required {target}")
    return ValueShareResult(
        tuple(participants), tuple(tuple(r) for r in matrix), root, tuple(shares), tuple(designated)
    )
