"""Offline share conversion and response binding.

Network transport is intentionally not enabled without explicit pool
configuration and protocol validation. This module tests the wire contract.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from .lucas_datapath import LucasShare, SpatialLucasPipeline

@dataclass(frozen=True)
class StratumJob:
    job_id: str
    ntime: str
    extranonce2_size: int

@dataclass(frozen=True)
class StratumSubmission:
    worker: str
    job_id: str
    extranonce2: str
    ntime: str
    nonce: int
    certificate_digest: str

@dataclass(frozen=True)
class ShareResponse:
    accepted: bool
    response_id: str
    error: str | None = None
    certificate_digest: str | None = None

def lucas_to_stratum(share: LucasShare, job: StratumJob, worker: str) -> StratumSubmission:
    mask_hex = format(share.record.zeckendorf_mask, "x").rjust(job.extranonce2_size * 2, "0")[-job.extranonce2_size * 2:]
    return StratumSubmission(worker, job.job_id, mask_hex, job.ntime, share.record.rung % (1 << 32), share.record.certificate)

def bind_response(submission: StratumSubmission, response: ShareResponse) -> ShareResponse:
    return ShareResponse(response.accepted, response.response_id, response.error, submission.certificate_digest)
