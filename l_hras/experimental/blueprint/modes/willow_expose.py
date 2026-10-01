# l_hras/modes/willow_expose.py

from dataclasses import dataclass
from typing import List

@dataclass
class Exposure:
    identity: str
    methods: List[str]
    intent: str
    bent_state: dict
    attestation: str

def willow_expose(guardian) -> List[Exposure]:
    """We willow you and expose you."""
    exposures = []
    for pot in guardian.honey_pots:
        if pot.engagement.get("active"):
            exposure = Exposure(
                identity="attacker_id",
                methods=["method1", "method2"],
                intent="intent",
                bent_state={"bent": True},
                attestation="exposed",
            )
            exposures.append(exposure)
    return exposures
