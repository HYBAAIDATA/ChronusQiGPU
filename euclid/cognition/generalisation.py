"""Held-out generalisation evidence for EUCLID cognition.

A single task family is never promoted into a generalisation claim. Evidence
must contain at least two distinct held-out families and preserves regressions
rather than averaging them away.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Iterable

from euclid.contracts import domain_hash
from euclid.evidence import atomic_write


SCHEMA = "euclid.held-out-generalisation/1"
SEAL_DOMAIN = "euclid.held-out-generalisation.seal.v1"


@dataclass(frozen=True)
class HeldOutGeneralisationTrial:
    family: str
    baseline_utility: float
    transfer_utility: float
    partition: str = "held-out"

    def __post_init__(self) -> None:
        if not self.family:
            raise ValueError("held-out trial family is required")
        if self.partition != "held-out":
            raise ValueError("generalisation evidence must be held-out")
        if not all(
            math.isfinite(float(value))
            for value in (self.baseline_utility, self.transfer_utility)
        ):
            raise ValueError("generalisation utilities must be finite")


def evaluate_held_out_generalisation(
    trials: Iterable[HeldOutGeneralisationTrial],
    *,
    minimum_families: int = 2,
    tolerance: float = 0.0,
    output: str | Path | None = None,
) -> dict:
    rows = tuple(trials)
    if minimum_families < 2:
        raise ValueError("minimum_families must be at least two")
    families = sorted({row.family for row in rows})
    by_family: dict[str, list[float]] = {}
    for row in rows:
        by_family.setdefault(row.family, []).append(
            float(row.transfer_utility) - float(row.baseline_utility)
        )
    family_delta = {
        family: sum(values) / len(values) for family, values in by_family.items()
    }
    enough_families = len(families) >= minimum_families
    non_regression = enough_families and all(
        delta >= -float(tolerance) for delta in family_delta.values()
    )
    improved = any(delta > float(tolerance) for delta in family_delta.values())
    mean_delta = (
        sum(family_delta.values()) / len(family_delta) if family_delta else 0.0
    )
    passed = bool(enough_families and non_regression and improved)
    body = {
        "schema": SCHEMA,
        "partition": "held-out",
        "minimum_families": minimum_families,
        "families": families,
        "family_delta": family_delta,
        "mean_delta": mean_delta,
        "passed": passed,
        "verdict": (
            "improved"
            if passed
            else "insufficient_families"
            if not enough_families
            else "regressed"
            if not non_regression
            else "no_change"
        ),
        "trials": [asdict(row) for row in rows],
        "claim_boundary": (
            "Measured multi-family held-out transfer evidence is not external "
            "validation or proof of universal general intelligence."
        ),
    }
    report = {**body, "seal": domain_hash(SEAL_DOMAIN, body)}
    if output is not None:
        atomic_write(Path(output), report)
    return report


def validate_generalisation_report(report: dict) -> bool:
    body = {key: value for key, value in report.items() if key != "seal"}
    if body.get("schema") != SCHEMA:
        return False
    if report.get("seal") != domain_hash(SEAL_DOMAIN, body):
        return False
    return (
        body.get("partition") == "held-out"
        and len(set(body.get("families") or ())) >= 2
        and body.get("passed") is True
    )


__all__ = [
    "HeldOutGeneralisationTrial",
    "evaluate_held_out_generalisation",
    "validate_generalisation_report",
]
