#!/usr/bin/env python3
"""Job dispatch bridge: /api/jobs/* -> unified_punch OpenCL iGPU backend.

Reads one job JSON object on stdin:

    {"job_id": "...", "name": "...", "payload": {"work_items": N, ...}}

Snaps the requested work-item count onto the Lucas/Pisot scale ladder
(lucas_scales.IGPU_SCALE_RUNGS — the hardware-scaling dial), derives a
deterministic n x 11 float vector from the job digest, and dispatches the
phi_filter_score punch (0x1A — the Stage-A mining resonance filter) to the
OpenCL iGPU via UnifiedPunchHost.

Prints one JSON object on stdout — the honest execution evidence that is
persisted onto the job record:

    ok, job_id, backend, device, kernel_ms, dispatch_ms,
    lucas_scale, ladder_rungs, punch, work_items, hits, score stats

Rule 7 (strict honest measurement): backend/device/kernel_ms come from
the punch host's own dispatch provenance — never assumed. When no OpenCL
device enumerates, the dispatch fails loudly (ok:false + gpu_error); it
never silently hashes on the CPU fallback.
"""

import hashlib
import json
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np

from Intelligence.unified_punch import UnifiedPunchHost, DIM
from Intelligence.lucas_scales import (
    IGPU_SCALE_RUNGS,
    PISOT_EXACT_N,
    ladder_multiples_of,
    nearest_ladder_index,
)

PUNCH_PHI_FILTER = 0x1A
PHI_FILTER_THRESHOLD = 0.5  # Stage-B pass threshold (workflow §3.02)
DEFAULT_WORK_ITEMS = PISOT_EXACT_N  # 76 — the Pisot collapse rung
MAX_WORK_ITEMS = 65536


def _derive_vectors(job_id: str, payload: dict, n: int) -> np.ndarray:
    """Deterministic n x DIM float32 vectors from the job digest."""
    seed_src = json.dumps(
        {"job_id": job_id, "payload": payload}, sort_keys=True, default=str
    ).encode()
    seed = hashlib.sha256(seed_src).digest()
    out = np.zeros((n, DIM), dtype=np.float32)
    for i in range(n):
        block = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        vals = np.frombuffer(block, dtype=np.uint8)[:DIM].astype(np.float32)
        out[i] = (vals - 127.5) / 127.5  # centred [-1, 1]
    return out.reshape(-1)


def dispatch(job: dict) -> dict:
    job_id = str(job.get("job_id") or "")
    payload = job.get("payload") or {}
    requested = int(payload.get("work_items", DEFAULT_WORK_ITEMS))
    # Lucas/Pisot enforcement: the dispatched batch size is a ladder stop.
    n = nearest_ladder_index(requested, lo=1, hi=MAX_WORK_ITEMS)

    host = UnifiedPunchHost()
    evidence = {
        "ok": False,
        "job_id": job_id,
        "punch": "phi_filter_score",
        "punch_id": PUNCH_PHI_FILTER,
        "requested_work_items": requested,
        "lucas_scale": n,
        "ladder_rungs": ladder_multiples_of(n),
        "scale_rungs": list(IGPU_SCALE_RUNGS),
    }
    if not host.use_opencl:
        evidence["error"] = (
            "no OpenCL device enumerated — refusing silent CPU dispatch"
        )
        evidence["gpu_error"] = host.gpu_error
        evidence["backend"] = host.last_dispatch_backend
        return evidence

    vec = _derive_vectors(job_id, payload, n)
    t0 = time.perf_counter()
    res = host.run_punch_batch(PUNCH_PHI_FILTER, in_float=vec, n=n)
    dispatch_ms = (time.perf_counter() - t0) * 1000.0

    scores = np.asarray(res["float"], dtype=np.float64)[::DIM][:n]
    hits = int(np.count_nonzero(scores >= PHI_FILTER_THRESHOLD))

    evidence.update(
        {
            "ok": True,
            "backend": host.last_dispatch_backend,  # the backend that ran
            "device": dict(host.device_info),
            "kernel_ms": host.last_kernel_ms,
            "dispatch_ms": round(dispatch_ms, 3),
            "work_items": n,
            "hits": hits,
            "score_min": float(scores.min()) if n else 0.0,
            "score_max": float(scores.max()) if n else 0.0,
            "score_mean": float(scores.mean()) if n else 0.0,
        }
    )
    return evidence


def main() -> int:
    try:
        job = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"malformed job JSON: {exc}"}))
        return 2
    try:
        evidence = dispatch(job)
    except Exception as exc:  # honest failure surface — no silent fallback
        print(json.dumps({"ok": False, "error": str(exc), "job_id": job.get("job_id")}))
        return 1
    print(json.dumps(evidence))
    return 0 if evidence.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
