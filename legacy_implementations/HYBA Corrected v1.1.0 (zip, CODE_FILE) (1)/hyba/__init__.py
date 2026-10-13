"""
HYBA Infrastructure — φ-Substrate Compute Layer (Corrected)
Version: 1.1.0

Fixes applied:
  Bug 1: HYBACore class — already fixed in v1.0
  Bug 2: Cassini integrity — added structural validation (symmetry, a-d=b, non-negativity)
  Bug 3: Storage signed delta — struct.pack('<q') instead of '<I'
  Bug 4: Memory allocation — gap >= size instead of gap² >= size
  Bug 5: Lifting integer enforcement — TypeError on float inputs, round-half-away-from-zero
  NEW:   Odd-length fold — pass-through trailing element instead of padding
  EFF:   bits_per_value — removed +1 safety bit
"""

from .core import HYBACore
from .memory import HYBAMemory
from .storage import HYBAStorage
from .compute import HYBACompute
from .infrastructure import HYBAInfrastructure
from .invariants import HYBAInvariants

__version__ = "1.1.0"
__all__ = [
    "HYBACore",
    "HYBAMemory",
    "HYBAStorage",
    "HYBACompute",
    "HYBAInfrastructure",
    "HYBAInvariants",
]
