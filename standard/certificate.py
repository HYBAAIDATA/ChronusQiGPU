"""Conformance certificate. Every invariant is proved, tested, modeled, assumed, or a gap."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Literal, Optional

ProofStatus = Literal["proved", "tested", "modeled", "benchmarked", "assumed", "gap"]
Method = Literal["formal", "property_based", "unit", "integration", "benchmark", "model", "manual"]
Blocker = Literal["none", "research", "hardware", "partnership", "regulation", "capital"]

INVARIANT_IDS = [
    "P1", "P2", "P3", "P4", "P4a", "P5",
    "B1", "B2", "B3", "B4", "B5",
    "K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8",
    "Q1", "Q2", "Q3", "Q4",
    "F1", "F2", "F3", "F4", "F4a", "F4b", "F4c", "F5", "F6", "F7",
    "H1", "H2", "H3",
    "AC1", "AC2", "AC3",
    "T1", "T2", "T3", "T4", "T5", "T6",
    "S1", "S2", "S3", "S4", "S5",
    "R1", "R2", "R3", "R4",
]


@dataclass
class Evidence:
    status: ProofStatus
    artifact: str
    checker: str
    method: Method
    cost: float
    falsifiable: bool
    detail: str = ""


@dataclass
class GapDeclaration:
    invariant: str
    reason: str
    path: List[str]
    cost_estimate: float
    blocker: Blocker
    falsifiable: bool


@dataclass
class ConformanceCertificate:
    repository: str
    commit: str
    standard_version: str
    claimed_level: str
    proved_level: str
    invariants: Dict[str, dict]
    gaps: Dict[str, dict]
    signature: str
    timestamp: str
    reproducible: bool

    def as_dict(self) -> dict:
        return asdict(self)


GAPS: Dict[str, GapDeclaration] = {
    "K5_SNARK": GapDeclaration(
        invariant="K5_SNARK",
        reason="Halo2/PLONK circuit is not in-tree. Host commitment path is modeled.",
        path=["Choose Halo2", "Circuit per kernel", "Prover + seam verifier", "Benchmark proof time"],
        cost_estimate=90 * 24 * 3600,
        blocker="research",
        falsifiable=True,
    ),
    "ASIC1": GapDeclaration(
        invariant="ASIC1",
        reason="xor_step.v is a sketch. No PDK, no tape-out.",
        path=["Partner fab", "Port PDK", "Tape-out", "Measure energy"],
        cost_estimate=365 * 24 * 3600,
        blocker="hardware",
        falsifiable=True,
    ),
    "TLC": GapDeclaration(
        invariant="Q3_TLC",
        reason="Python interleaving checker ships; TLC is not in CI.",
        path=["Install TLC", "Run distributed/queue_proof.tla in CI"],
        cost_estimate=2 * 24 * 3600,
        blocker="none",
        falsifiable=True,
    ),
}


def _sign(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _level(statuses: Dict[str, str], mode: str) -> str:
    values = list(statuses.values())
    n = len(values)
    if mode == "claimed":
        if all(s in {"proved", "tested", "modeled", "benchmarked"} for s in values):
            return "extended"
        if all(s in {"proved", "tested"} for s in values):
            return "core"
        return "minimal"
    proved = sum(1 for s in values if s == "proved")
    tested = sum(1 for s in values if s in {"proved", "tested"})
    if proved == n:
        return "full"
    if tested >= n * 0.8:
        return "extended"
    if tested >= n * 0.5:
        return "core"
    return "minimal"


def generate_certificate(
    repo: str = "QUANTUMDATA2/PYTHIAPhiMiner",
    commit: str = "feat/chronus-seam",
    standard_version: str = "1.0",
    checks: Optional[Dict[str, Evidence]] = None,
) -> ConformanceCertificate:
    from standard.check_invariants import check_all

    evidence = checks or check_all()
    inv = {k: asdict(v) for k, v in evidence.items()}
    statuses = {k: v.status for k, v in evidence.items()}
    gaps = {k: asdict(g) for k, g in GAPS.items()}
    body = json.dumps({"inv": inv, "gaps": gaps, "repo": repo, "commit": commit}, sort_keys=True)
    return ConformanceCertificate(
        repository=repo,
        commit=commit,
        standard_version=standard_version,
        claimed_level=_level(statuses, "claimed"),
        proved_level=_level(statuses, "proved"),
        invariants=inv,
        gaps=gaps,
        signature=_sign(body),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        reproducible=True,
    )
