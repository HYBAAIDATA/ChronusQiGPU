# l_hras/modes/swarm.py

from dataclasses import dataclass, field
from typing import List
import numpy as np

@dataclass
class Swarm:
    workers: List['Guardian']
    threshold: int

@dataclass
class DefenseResponse:
    worker_id: str
    action: str
    attestation: str

@dataclass
class Defense:
    swarm: Swarm
    responses: List[DefenseResponse]
    decision: str
    attestation: str

def swarm(swarm: Swarm, attack: np.ndarray) -> Defense:
    """When attacked, we swarm and protect."""
    slices = np.array_split(attack, len(swarm.workers))
    responses = [
        DefenseResponse(
            worker_id=w.id,
            action="defend",
            attestation=f"defended_{w.id}",
        )
        for w, s in zip(swarm.workers, slices)
    ]
    # Consensus
    decision = "accepted"
    return Defense(
        swarm=swarm,
        responses=responses,
        decision=decision,
        attestation="swarmed",
    )
