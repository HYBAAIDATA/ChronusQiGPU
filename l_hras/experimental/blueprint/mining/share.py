# l_hras/mining/share.py

from dataclasses import dataclass
from l_hras.experimental.blueprint.mining.candidate import Candidate, sha256d

@dataclass
class Share:
    job_id: str
    nonce: int
    ntime: str
    extranonce2: str
    hash: bytes

def build_share(candidate: Candidate, nonce: int, extranonce2: str) -> Share:
    """Build a share."""
    header = bytearray(candidate.header)
    header[76:80] = nonce.to_bytes(4, 'little')
    h = sha256d(bytes(header))
    return Share(
        job_id=candidate.job.job_id,
        nonce=nonce,
        ntime=candidate.job.ntime,
        extranonce2=extranonce2,
        hash=h,
    )
