# l_hras/mining/candidate.py

import hashlib
from dataclasses import dataclass
from l_hras.experimental.blueprint.mining.job import Job

@dataclass
class Candidate:
    header: bytes
    job: Job

def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def build_candidate(job: Job, extranonce1: str, extranonce2: str) -> Candidate:
    """Build the block header."""
    coinbase = bytes.fromhex(job.coinb1 + extranonce1 + extranonce2 + job.coinb2)
    coinbase_hash = sha256d(coinbase)
    root = coinbase_hash
    for branch in job.merkle_branch:
        root = sha256d(root + bytes.fromhex(branch))
    header = (
        bytes.fromhex(job.version)[::-1] +
        bytes.fromhex(job.prevhash)[::-1] +
        root +
        bytes.fromhex(job.ntime)[::-1] +
        bytes.fromhex(job.nbits)[::-1] +
        b'\x00\x00\x00\x00'  # nonce placeholder
    )
    return Candidate(header=header, job=job)
