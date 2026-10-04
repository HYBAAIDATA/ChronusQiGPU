"""Compatibility surface for the canonical 11-D Poincare-golden substrate.

The implementation moved to :mod:`toe.poincare_golden_11d`.  Keeping a full
copy here previously allowed the two modules to drift and, critically, left a
silent Float64-to-Float32 ``to_gpu_input`` path reachable through the
``millennium`` namespace.  Re-exporting the canonical owner preserves legacy
imports while enforcing one precision and authority policy everywhere.
"""

from toe.poincare_golden_11d import *  # noqa: F401,F403
from toe.poincare_golden_11d import _FIB_TABLE  # noqa: F401
