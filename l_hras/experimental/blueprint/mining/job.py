# l_hras/mining/job.py

from dataclasses import dataclass
from typing import List

@dataclass
class Job:
    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: List[str]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool

def parse_job(params: list) -> Job:
    """Parse mining.notify params."""
    return Job(
        job_id=params[0],
        prevhash=params[1],
        coinb1=params[2],
        coinb2=params[3],
        merkle_branch=params[4],
        version=params[5],
        nbits=params[6],
        ntime=params[7],
        clean_jobs=params[8],
    )
