# l_hras/guardian/verify.py

from l_hras.experimental.blueprint.guardian.guardian import Guardian
from l_hras.experimental.blueprint.core.types import Ok, Err, Error

def guard(guardian: Guardian, request: dict) -> 'Result':
    """The Guardian's duty: guard the fold."""
    # All five modes run simultaneously
    from l_hras.experimental.blueprint.modes.multiply import multiply
    from l_hras.experimental.blueprint.modes.entangle import entangle_all
    from l_hras.experimental.blueprint.modes.swarm import swarm, Swarm
    from l_hras.experimental.blueprint.modes.honey_pot import honey_pot
    from l_hras.experimental.blueprint.modes.willow_expose import willow_expose

    mult = multiply(guardian.intelligence)
    ent = entangle_all(guardian.intelligence.states.keys())
    sw = swarm(Swarm(workers=[guardian], threshold=1), attack=None)
    pots = honey_pot(guardian)
    exposures = willow_expose(guardian)

    # Verdict is the conjunction
    allowed = (
        mult is not None and
        ent is not None and
        sw.decision == "accepted" and
        all(p is not None for p in pots) and
        all(e is not None for e in exposures)
    )

    if not allowed:
        return Err(Error.SECURITY_VIOLATION)
    return Ok({"allowed": True, "attestation": "guarded"})
