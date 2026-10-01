# l_hras/fold/klein.py

import numpy as np
from l_hras.experimental.blueprint.fold.vector11d import Vector11D, DIM

def fold_11d(x: Vector11D) -> Vector11D:
    """The Klein map: fold to the Poincaré ball."""
    n = x.phi_norm()
    return Vector11D(x.components / np.sqrt(1 + n))

def unfold_11d(y: Vector11D) -> Vector11D:
    """The inverse: unfold from the Poincaré ball."""
    n = y.phi_norm()
    if n >= 1:
        raise ValueError("privacy_violation: norm >= 1")
    return Vector11D(y.components / np.sqrt(1 - n))

# Verify: roundtrip to 10^-14
for _ in range(100):
    x = Vector11D(np.random.randn(DIM) * 0.5)
    y = fold_11d(x)
    x_back = unfold_11d(y)
    assert np.allclose(x.components, x_back.components, atol=1e-14)
