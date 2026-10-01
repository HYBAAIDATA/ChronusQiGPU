"""Axioms A1–A8. Invariants are theorems of these axioms."""

from __future__ import annotations

from typing import Dict, List

AXIOMS: Dict[str, str] = {
    "A1": "There exist physical devices that compute.",
    "A2": "measured_hps(d, k) is a well-defined Distribution and can be sampled.",
    "A3": "For any computation c there exists a proof \u03c0(c) a verifier can check.",
    "A4": "For any computation c there exists a reversible c* that uncomputes garbage.",
    "A5": "Erasing one bit dissipates at least kT ln 2.",
    "A6": "Adiabatic dissipation E = CV\u00b2(RC/t) approaches 0 as t \u2192 \u221e.",
    "A7": "Computations and attestations compose.",
    "A8": "Unmeasured quantities are declared unmeasured. Silence is not a value.",
}


def axiom_ids() -> List[str]:
    return list(AXIOMS)
