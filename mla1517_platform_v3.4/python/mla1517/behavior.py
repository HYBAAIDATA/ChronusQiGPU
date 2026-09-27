from __future__ import annotations
import json
from pathlib import Path

DEFAULT_BEHAVIOR = {
    "product": "PRIME-DB + MLA1517 GPU/iGPU",
    "mode": "mla1517_gpu",
    "own_gpu_preferred": True,
    "host_gpu_role": "optional_scale_assist",
    "allow_host_gpu": True,
    "lanes": 17,
    "allow_cpu_fallback": True,
    "require_host_gpu": False,
    "require_proof_before_commit": True,
    "promote_only_verified_pairings": True,
    "performance_claim_policy": "measured_only",
    "scaling_claim": "candidate_exponential_measured_only",
    "unlimited_speed_or_capacity_claim": False,
}


def load_behavior(path: str | None = None) -> dict:
    if path is None:
        return dict(DEFAULT_BEHAVIOR)
    data = json.loads(Path(path).read_text())
    out = dict(DEFAULT_BEHAVIOR)
    out.update(data)
    if out["lanes"] < 1:
        raise ValueError("lanes must be >= 1")
    if out["unlimited_speed_or_capacity_claim"]:
        raise ValueError("unlimited speed/capacity claims are prohibited until measured")
    return out
