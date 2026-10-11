"""Third-party conformance suite against any seam-shaped implementation."""

from __future__ import annotations

from typing import Dict, List

LEVELS: Dict[str, List[str]] = {
    "minimal": ["P1", "P2", "B1", "B2", "K1", "K4", "Q1", "S1"],
    "core": ["P1", "P2", "P3", "B1", "B2", "B3", "K1", "K2", "K3", "K4", "Q1", "Q2", "S1", "S4"],
    "hash": ["P1", "P2", "P3", "B1", "B2", "B3", "K1", "K2", "K3", "K4", "Q1", "Q2", "S1", "S4", "F1", "F2", "F5", "T1", "T2"],
    "extended": [
        "P1", "P2", "P3", "P4", "P4a", "P5",
        "B1", "B2", "B3", "B4", "B5",
        "K1", "K2", "K3", "K4", "K6", "K7", "K8",
        "Q1", "Q2", "Q4",
        "F1", "F2", "F3", "F4", "F5", "F6", "F7",
        "H1", "H2", "H3",
        "AC1", "AC2", "AC3",
        "T1", "T2", "T3", "T4", "T5", "T6",
        "S1", "S2", "S3", "S4", "S5",
        "R1", "R2", "R3", "R4",
    ],
    "full": [],
}


def check_conformance(level: str = "core") -> Dict[str, bool]:
    from standard.check_invariants import check_all
    from standard.certificate import INVARIANT_IDS

    if not LEVELS["full"]:
        LEVELS["full"] = list(INVARIANT_IDS)
    evidence = check_all()
    required = LEVELS[level]
    return {inv: evidence[inv].status in {"proved", "tested", "modeled", "benchmarked"} for inv in required}


def certify(level: str = "core") -> bool:
    return all(check_conformance(level).values())
