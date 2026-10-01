"""Proof 1: the seam runs real mining work."""

from __future__ import annotations

from typing import Any

from chronus.seam import Result, run
from chronus.seam.fleet import JobResult, run_hybrid_stratum
from chronus.seam.types import KernelName


def run_stratum(job: dict, fleet=None) -> Result[JobResult]:
    payload = dict(job)
    payload.setdefault("kernels", [KernelName.sha256d_verify.value])
    return run(payload, fleet)


def run_hybrid(job: Any, gpu: Any, asic: Any = None) -> Result[dict]:
    return run_hybrid_stratum(job, gpu, asic)
