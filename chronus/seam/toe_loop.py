"""Chronus scale enters TOE: Klein fold, certificate, bridge, theorem packs."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from .scale import ChronusScale, scale_job
from toe.geometric_contract import check_twelve
from toe.manifold_bridge import ManifoldBridge
from toe.phi_klein import PUNCH_ISA, fold, phi_norm, unfold
from toe.poincare_golden_11d import compute_zeckendorf_certificate
from toe.system import TOESystem


def realize(job_id: str, requested: int, payload: str = "") -> Dict[str, Any]:
    scale: ChronusScale = scale_job(job_id, requested, payload)
    vector = np.asarray(scale.t11, dtype=np.float64)
    folded, reflections = fold(vector)
    unfolded = unfold(folded)
    certificate = compute_zeckendorf_certificate(folded, context_id=job_id)
    nonce = int(certificate.canonical_int & 0xFFFFFFFF)
    bridge = ManifoldBridge()
    candidate = bridge.store_candidate(
        nonce=nonce,
        header_template=job_id.encode("utf-8")[:32].ljust(32, b"\0"),
        born_prob=0.95,
        n_anchor=7,
    )
    toe = TOESystem(bridge=bridge)
    passed, theorems = toe.verify_12_theorems_candidate(candidate, n_anchor=7)
    record = toe.record_decision(
        phase_name="chronus_scale_realize",
        intelligence_name="geometric",
        action="fold_certify_verify",
        params={
            "job_id": job_id,
            "work_items": scale.work_items,
            "nonce": nonce,
        },
        contract_no=2,
        verified=passed,
    )
    geometric = check_twelve(
        seed=vector,
        folded=folded,
        unfolded=unfolded,
        certificate=certificate.to_dict(),
        candidate=candidate.to_dict(),
        theorems=theorems,
        ledger_ok=toe.verify_provenance(),
        n_anchor=7,
    )
    return {
        "product": "Chronus",
        "compute_substrate": "Turing",
        "scale": scale.as_dict(),
        "norm_phi_sq": phi_norm(folded),
        "reflections": reflections,
        "roundtrip_ok": geometric["G8_fold_unfold"],
        "certificate": certificate.to_dict(),
        "device_punches": certificate.gpu_dispatch_info(),
        "punch_isa": PUNCH_ISA,
        "candidate": candidate.to_dict(),
        "theorems": theorems,
        "geometric": geometric,
        "passed": passed and all(geometric.values()),
        "provenance": record.to_dict(),
        "ledger_ok": geometric["G12_provenance"],
    }
