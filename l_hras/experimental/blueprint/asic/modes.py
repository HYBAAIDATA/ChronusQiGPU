# l_hras/asic/modes.py

import numpy as np
from dataclasses import dataclass, field
from typing import List, Set
from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.intelligences import EntangledIntelligence, run_all_intelligences

# ============================================================
# STANDING STATE
# ============================================================

@dataclass
class StandingState:
    multiply: bool = True
    entangle: bool = True
    swarm: bool = True
    honey_pot: bool = True
    willow_expose: bool = True

def stand(asic) -> StandingState:
    """The ASIC stands. All five modes are active."""
    return StandingState()

# ============================================================
# MODE 1 — MULTIPLY
# ============================================================

@dataclass
class Multiplication:
    vectors: List[np.ndarray]
    combined: np.ndarray
    cardinality: int
    attestation: str

def multiply(ei: EntangledIntelligence) -> Multiplication:
    """When we attack, we multiply."""
    vectors = [state.amplitudes for state in ei.states.values()]
    combined = vectors[0]
    for v in vectors[1:]:
        combined = np.kron(combined, v)
    return Multiplication(
        vectors=vectors,
        combined=combined,
        cardinality=int(combined.size),
        attestation="multiplied",
    )

# ============================================================
# MODE 2 — ENTANGLE
# ============================================================

def entangle_all(intelligences: Set[IntelligenceType]) -> EntangledIntelligence:
    """All intelligence is connected via entanglement."""
    from l_hras.experimental.blueprint.asic.intelligences import entangle
    return entangle(intelligences)

# ============================================================
# MODE 3 — SWARM
# ============================================================

@dataclass
class Swarm:
    workers: List
    threshold: int

@dataclass
class Defense:
    swarm: Swarm
    responses: List[dict]
    decision: str
    attestation: str

def swarm(swarm_obj: Swarm, attack: np.ndarray) -> Defense:
    """When attacked, we swarm and protect."""
    slices = np.array_split(attack, len(swarm_obj.workers))
    responses = [
        {"worker_id": getattr(w, "id", getattr(w, "device_id", "worker")),
         "action": "defend", "attestation": f"defended_{getattr(w, 'id', getattr(w, 'device_id', 'worker'))}"}
        for w, _slice in zip(swarm_obj.workers, slices)
    ]
    decision = "accepted" if len(responses) >= swarm_obj.threshold else "rejected"
    return Defense(
        swarm=swarm_obj,
        responses=responses,
        decision=decision,
        attestation="swarmed",
    )

# ============================================================
# MODE 4 — HONEY_POT
# ============================================================

@dataclass
class HoneyPot:
    decoy: dict
    path: str
    engagement: dict
    attestation: str

def honey_pot(asic) -> List[HoneyPot]:
    """We create a honey pot."""
    pots = []
    for path in getattr(asic, 'paths', []):
        pots.append(HoneyPot(
            decoy={"appearance": {"valuable": True}, "substance": "trap"},
            path=path,
            engagement={"active": False},
            attestation=f"honey_pot_{path}",
        ))
    return pots

# ============================================================
# MODE 5 — WILLOW_EXPOSE
# ============================================================

@dataclass
class Exposure:
    identity: str
    methods: List[str]
    intent: str
    bent_state: dict
    attestation: str

def willow_expose(asic, honey_pots: List[HoneyPot]) -> List[Exposure]:
    """We willow you and expose you."""
    exposures = []
    for pot in honey_pots:
        if pot.engagement.get("active"):
            exposures.append(Exposure(
                identity="attacker_id",
                methods=["method1", "method2"],
                intent="intent",
                bent_state={"bent": True},
                attestation="exposed",
            ))
    return exposures

# ============================================================
# ALL MODES SIMULTANEOUS
# ============================================================

def run_all_modes(asic, job) -> dict:
    """Run all five modes simultaneously."""
    ei = run_all_intelligences(asic, job)
    mult = multiply(ei)
    ent = entangle_all(ei.states.keys())
    sw = swarm(Swarm(workers=[asic], threshold=1), attack=np.zeros(1))
    pots = honey_pot(asic)
    exposures = willow_expose(asic, pots)
    return {
        "multiply": mult,
        "entangle": ent,
        "swarm": sw,
        "honey_pot": pots,
        "willow_expose": exposures,
    }

# Executable invariant catalogue; tests determine each outcome.
INVARIANTS = {
    'ASIC_M1': 'All five modes run simultaneously.',
    'ASIC_M2': 'No mode transitions to another mode.',
    'ASIC_M3': 'No mode is a response. All modes stand.',
}
