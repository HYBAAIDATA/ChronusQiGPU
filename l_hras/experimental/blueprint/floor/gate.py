# l_hras/floor/gate.py

from l_hras.experimental.blueprint.floor.hashrate import Hashrate
from l_hras.experimental.blueprint.core.types import Ok, Err, Error

FLOOR = 10e18  # 10 EH/s

def enforce_floor(h: Hashrate) -> 'Result':
    """Enforce the 10 EH/s floor."""
    if h.total < FLOOR:
        return Err(Error.HASHRATE_BELOW_FLOOR)
    return Ok(h)
