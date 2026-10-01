# l_hras/asic/hash.py

import hashlib
from dataclasses import dataclass
from typing import List, Optional
from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.capability import ASICCapability

@dataclass
class Job:
    job_id: str
    header: bytes
    target: bytes
    window: List[int]
    circuit: Optional[Any] = None
    qubits: int = 0
    folded: Optional[Any] = None
    path: str = "classic"

    def with_classic_path(self):
        self.path = "classic"
        return self

    def with_fold_path(self):
        self.path = "fold"
        return self

    def has_fold_path(self) -> bool:
        return self.path == "fold"

@dataclass
class Share:
    nonce: int
    hash: bytes
    job_id: str
    attestation: Optional[str] = None
    certificate: Optional[Any] = None

def sha256d(data: bytes) -> bytes:
    """Double SHA-256."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def asic_hash(asic: ASICCapability, job: Job) -> 'Result':
    """
    The classic ASIC path. Pure SHA-256d.
    This always works.
    """
    if len(job.header) != 80 or len(job.target) != 32:
        return Err(ASICError.UNKNOWN)
    header = bytearray(job.header)
    for nonce in job.window:
        header[76:80] = nonce.to_bytes(4, 'little')
        h = sha256d(bytes(header))
        if h[::-1] < job.target:
            return Ok(Share(
                nonce=nonce,
                hash=h,
                job_id=job.job_id,
                attestation=f"share_{nonce}_{h.hex()[:16]}",
            ))
    return Err(ASICError.NO_SHARE_FOUND)

# Executable invariant catalogue; tests determine each outcome.
INVARIANTS = {
    'ASIC_H1': 'Every hash is double SHA-256.',
    'ASIC_H2': 'Every share meets the target.',
    'ASIC_H3': 'Every share is attested.',
    'ASIC_H4': 'The hash path always works, independent of the fold.',
}
