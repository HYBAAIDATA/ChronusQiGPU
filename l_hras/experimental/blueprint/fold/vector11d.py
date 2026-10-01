# l_hras/fold/vector11d.py

import numpy as np
from dataclasses import dataclass
from l_hras.experimental.blueprint.substrate.phi_rotation import PHI

DIM = 11
LUCAS_TABLE = [2, 1, 3, 4, 7, 11, 18, 29, 47, 76, 123]

@dataclass
class Vector11D:
    components: np.ndarray

    def __post_init__(self):
        assert self.components.shape == (DIM,)

    def phi_norm(self) -> float:
        """The golden-weighted norm on R^11."""
        return sum(
            PHI ** (-(i + 1)) * self.components[i] ** 2
            for i in range(DIM)
        )
