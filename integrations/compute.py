"""Proof 2: the seam runs real compute work."""

from __future__ import annotations

from chronus.seam import Result, run
from chronus.seam.types import Err, KernelName, Ok, SeamError


def run_matmul(a, b, fleet=None) -> Result[bytes]:
    job = {
        "job_id": "matmul",
        "kernels": [KernelName.reversible_matmul_f4.value],
        "args": {"a": a, "b": b},
        "span": 1,
    }
    result = run(job, fleet)
    if isinstance(result, Err):
        return result
    if not result.value.results:
        return Err(SeamError.verification_failed, "no compute result")
    return Ok(result.value.results[0].outputs[0])


def run_qfi(psi, generator, fleet=None) -> Result[bytes]:
    job = {
        "job_id": "qfi",
        "kernels": [KernelName.reversible_qfi_pure.value],
        "span": 1,
    }
    return run(job, fleet)
