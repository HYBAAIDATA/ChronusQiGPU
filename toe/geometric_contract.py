"""Twelve geometric checks on a realized TOE candidate.

Contract 2 in toe.system stays the candidate matrix.
This module is the fold / certificate / chain layer named beside it.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

import numpy as np

from kellogg.scales import cassini_verify, lucas, pisot_drift
from toe.phi_klein import HOROSPHERES, klein_identity, phi_norm
from toe.poincare_golden_11d import cassini_unimodular_det


def check_twelve(
    *,
    seed,
    folded,
    unfolded,
    certificate: Mapping[str, Any],
    candidate: Mapping[str, Any],
    theorems: Mapping[str, bool],
    ledger_ok: bool,
    n_anchor: int = 7,
) -> Dict[str, bool]:
    seed_a = np.asarray(seed, dtype=np.float64).reshape(11)
    folded_a = np.asarray(folded, dtype=np.float64).reshape(11)
    mask = int(certificate.get("non_adjacent_mask", 0))
    return {
        "G1_cassini": bool(theorems.get("T1_cassini_identity")) and cassini_verify(n_anchor),
        "G2_pisot_decay": bool(theorems.get("T2_pisot_decay")),
        "G3_lucas_trace": lucas(10) == 123
        and lucas(n_anchor) == lucas(n_anchor - 1) + lucas(n_anchor - 2),
        "G4_lucas_pisot": bool(theorems.get("T4_lucas_pisot_scaling")),
        "G5_zeckendorf": bool(certificate.get("is_valid")) and (mask & (mask << 1)) == 0,
        "G6_born_floor": bool(theorems.get("T11_born_rule_threshold")),
        "G7_galois_bound": bool(theorems.get("T12_galois_bound")),
        "G8_fold_unfold": bool(np.allclose(unfolded, seed_a, rtol=1e-9, atol=1e-12)),
        "G9_horosphere": len(HOROSPHERES) == 11 and HOROSPHERES[10] == 123,
        "G10_norm_ball": phi_norm(folded_a) < 1.0 and klein_identity(seed_a),
        "G11_certificate": bool(str(certificate.get("token_hex", "")).startswith("ZECK-")),
        "G12_provenance": bool(ledger_ok),
    }


def cassini_table_ok(k: int = 5) -> bool:
    return cassini_unimodular_det(k) == ((-1) ** k)
