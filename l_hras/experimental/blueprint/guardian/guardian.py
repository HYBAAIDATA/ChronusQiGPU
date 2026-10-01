# l_hras/guardian/guardian.py

from dataclasses import dataclass, field
from typing import List, Dict, Set
from l_hras.experimental.blueprint.intelligences.entangled import EntangledIntelligence
from l_hras.experimental.blueprint.modes.honey_pot import HoneyPot
from l_hras.experimental.blueprint.modes.willow_expose import Exposure
from l_hras.experimental.blueprint.fold.vector11d import Vector11D
from l_hras.experimental.blueprint.fold.certificate import Certificate

@dataclass
class Guardian:
    id: str
    intelligence: EntangledIntelligence
    modes: Set[str] = field(default_factory=lambda: {"multiply", "entangle", "swarm", "honey_pot", "willow_expose"})
    honey_pots: List[HoneyPot] = field(default_factory=list)
    exposures: List[Exposure] = field(default_factory=list)
    fold: Vector11D = None
    certificate: Certificate = None
    paths: List[str] = field(default_factory=list)
