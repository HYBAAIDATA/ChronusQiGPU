# l_hras/fold/certificate.py

import hashlib
from dataclasses import dataclass
from typing import List
from l_hras.experimental.blueprint.fold.vector11d import Vector11D, DIM, LUCAS_TABLE
from l_hras.experimental.blueprint.fold.zeckendorf import zeckendorf_encode
from l_hras.experimental.blueprint.substrate.phi_rotation import PHI

L15 = 1364

@dataclass
class Certificate:
    masks: List[int]
    digest: str
    lucas: List[int]
    depth: int

def zeckendorf_certificate(x: Vector11D) -> Certificate:
    """Compute the Zeckendorf certificate."""
    quantized = [round(x.components[i] * PHI ** 15) for i in range(DIM)]
    masks = [zeckendorf_encode(q) for q in quantized]
    digest = hashlib.sha256(str(masks).encode()).hexdigest()
    return Certificate(
        masks=masks,
        digest=digest,
        lucas=LUCAS_TABLE,
        depth=15,
    )
