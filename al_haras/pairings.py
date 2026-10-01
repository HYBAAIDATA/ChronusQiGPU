"""12.9 Pairings <-> Architecture: the pairings.yaml transport.

The registry records which substrate pairings are VERIFIED (with a
PairingTest record, matched baseline and reproducibility command), which
are PROHIBITED, which results are REFUTED, and which remain isolated
HYPOTHESIS. Admission control blocks unverified, refuted or untested
pairings before they enter the architecture.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml


class PairingStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PROHIBITED = "PROHIBITED"
    REFUTED = "REFUTED"
    HYPOTHESIS = "HYPOTHESIS"


@dataclass(frozen=True)
class PairingTest:
    test_command: str
    baseline: str
    reproduce_command: str


@dataclass(frozen=True)
class PairingRecord:
    name: str
    pair: tuple[str, ...]
    status: PairingStatus
    pairing_test: PairingTest | None = None
    negative_results_log: str = ""
    isolated_under: str = ""


@dataclass(frozen=True)
class PairingRegistry:
    version: int
    verified: tuple[PairingRecord, ...]
    prohibited: tuple[PairingRecord, ...]
    refuted_results: tuple[str, ...]
    hypothesis: tuple[PairingRecord, ...]


def _record(raw) -> PairingRecord:
    test = raw.get("pairing_test") or {}
    pairing_test = (
        PairingTest(
            test_command=str(test.get("test_command", "")),
            baseline=str(test.get("baseline", "")),
            reproduce_command=str(test.get("reproduce_command", "")),
        )
        if test
        else None
    )
    return PairingRecord(
        name=str(raw.get("name", "")),
        pair=tuple(str(p) for p in (raw.get("pair") or ())),
        status=PairingStatus(str(raw.get("status", "HYPOTHESIS"))),
        pairing_test=pairing_test,
        negative_results_log=str(raw.get("negative_results_log", "") or ""),
        isolated_under=str(raw.get("isolated_under", "") or ""),
    )


def load_pairings(path: str | Path) -> PairingRegistry:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PairingRegistry(
        version=int(document.get("version", 0) or 0),
        verified=tuple(_record(r) for r in (document.get("verified_pairings") or [])),
        prohibited=tuple(_record(r) for r in (document.get("prohibited_pairings") or [])),
        refuted_results=tuple(str(r) for r in (document.get("refuted_results") or [])),
        hypothesis=tuple(_record(r) for r in (document.get("hypothesis_pairings") or [])),
    )


class PairingRejected(ValueError):
    def __init__(self, reasons: tuple[str, ...]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


def admit_pairing(registry: PairingRegistry, candidate: PairingRecord) -> PairingRecord:
    """Architecture admission: a pairing enters only VERIFIED with its
    complete PairingTest record. Anything else is blocked with reasons."""
    reasons: list[str] = []
    names_prohibited = {p.name for p in registry.prohibited}
    names_refuted = {p.name for p in registry.prohibited} | set(registry.refuted_results)
    if candidate.name in names_prohibited or any(p in names_refuted for p in candidate.pair):
        reasons.append(f"pairing {candidate.name} is prohibited/refuted (F2)")
    if candidate.status is not PairingStatus.VERIFIED:
        reasons.append(f"pairing {candidate.name} is not VERIFIED (C1/F1)")
    test = candidate.pairing_test
    if test is None:
        reasons.append(f"pairing {candidate.name} lacks a PairingTest record (C2/F3)")
    else:
        if not test.baseline:
            reasons.append(f"pairing {candidate.name} lacks a matched baseline (C3)")
        if not test.reproduce_command:
            reasons.append(f"pairing {candidate.name} lacks a reproduce command (C4)")
        if not test.test_command:
            reasons.append(f"pairing {candidate.name} lacks a test command (C2)")
    if reasons:
        raise PairingRejected(tuple(reasons))
    return candidate


def architecture_violations(
    registry: PairingRegistry, source_paths: tuple[Path, ...]
) -> tuple[str, ...]:
    """F1–F3: prohibited or refuted pairing names must not appear in
    architecture sources (docs, specs, manifests)."""
    violations: list[str] = []
    banned = sorted({p.name for p in registry.prohibited} | set(registry.refuted_results))
    for path in source_paths:
        if not path.is_file():
            continue
        body = path.read_text(errors="replace")
        for line_no, line in enumerate(body.splitlines(), 1):
            low = line.casefold()
            if any(
                marker in low for marker in ("refuted", "prohibited", "must not", "do not pair")
            ):
                continue
            for name in banned:
                if name.casefold() in low:
                    violations.append(f"{path.name}:{line_no}: banned pairing {name}")
    return tuple(violations)


__all__ = [name for name in globals() if not name.startswith("_")]
