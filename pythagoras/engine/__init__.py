"""Production PYTHAGORAS engine components.

The executable production search lives in :mod:`pythagoras.engine.evolution`.
Historical staged engines are intentionally not part of this package surface.
"""

# The delivered final evolution implementation still imports four former staged
# module paths internally.  Map those names to the version-neutral component
# modules while the implementation itself is normalized; no V6 files are shipped.
import sys

from . import geometry as _geometry
from . import primitive_discovery as _primitive_discovery
from . import primitive_repository as _primitive_repository
from . import surrogate as _surrogate

sys.modules[f"{__name__}.v6_1_surrogate"] = _surrogate
sys.modules[f"{__name__}.v6_2_geometry"] = _geometry
sys.modules[f"{__name__}.v6_3_primitive_discovery"] = _primitive_discovery
sys.modules[f"{__name__}.v6_4_cross_file_reuse"] = _primitive_repository

__all__ = []
