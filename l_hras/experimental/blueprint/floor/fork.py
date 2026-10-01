# l_hras/floor/fork.py

from dataclasses import dataclass

@dataclass
class ForkResistance:
    pool_share: float
    solo_share: float
    network_share: float
    fork_threshold: float

def compute_fork_resistance(fr: ForkResistance) -> float:
    """Compute fork resistance."""
    return fr.pool_share * fr.solo_share * (1 - fr.network_share) * fr.fork_threshold
