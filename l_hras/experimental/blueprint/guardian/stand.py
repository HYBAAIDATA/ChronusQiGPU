# l_hras/guardian/stand.py

from dataclasses import dataclass

@dataclass
class StandingState:
    multiply: bool = True
    entangle: bool = True
    swarm: bool = True
    honey_pot: bool = True
    willow_expose: bool = True

def stand(guardian) -> StandingState:
    """The Guardian stands. All five modes are active."""
    return StandingState()
