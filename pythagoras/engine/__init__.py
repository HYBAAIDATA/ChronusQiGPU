"""Production PYTHAGORAS engine components.

The executable production search lives in :mod:`pythagoras.engine.evolution`.
Historical staged engine files are intentionally not part of this package surface.
"""

# The delivered final evolution implementation and a small number of experiment
# fixtures still resolve the historical module names during the cleanup transition.
# These are in-memory module aliases only; no versioned V6 implementation files ship.
import sys

from . import geometry as _geometry
from . import primitive_discovery as _primitive_discovery
from . import primitive_repository as _primitive_repository
from . import surrogate as _surrogate

sys.modules[f"{__name__}.v6_1_surrogate"] = _surrogate
sys.modules[f"{__name__}.v6_2_geometry"] = _geometry
sys.modules[f"{__name__}.v6_3_primitive_discovery"] = _primitive_discovery
sys.modules[f"{__name__}.v6_4_cross_file_reuse"] = _primitive_repository

from . import evolution as _evolution

sys.modules[f"{__name__}.v6_5_manifold_escape"] = _evolution

__all__ = []
