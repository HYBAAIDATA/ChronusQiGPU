# l_hras/modes/honey_pot.py

from dataclasses import dataclass, field
from typing import List

@dataclass
class Decoy:
    appearance: dict
    substance: str
    attestation: str

@dataclass
class HoneyPot:
    decoy: Decoy
    path: str
    engagement: dict
    attestation: str

def honey_pot(guardian) -> List[HoneyPot]:
    """We create a honey pot."""
    pots = []
    for path in guardian.paths:
        decoy = Decoy(
            appearance={"valuable": True},
            substance="trap",
            attestation="decoy_minted",
        )
        pots.append(HoneyPot(
            decoy=decoy,
            path=path,
            engagement={"active": False},
            attestation=f"honey_pot_{path}",
        ))
    return pots
