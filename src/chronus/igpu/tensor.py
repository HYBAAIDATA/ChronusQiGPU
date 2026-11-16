"""chronus.igpu.tensor: iGPU-facing re-export of the Chronus tensor surface.

The implementation lives in chronus.tensor; this module re-exports its public
API so iGPU-facing code imports from the iGPU namespace. TURING must not
import it: the dependency runs from Chronus to TURING, never the reverse
(see ``docs/system-update/quantum-package-taxonomy.md``). The numerical
representation is complex128 NumPy with explicit truncation ledgers; the
exact integer/rational paths (``exact_rational_tt``, lattice folds) are
separate and bounded.
"""

from chronus import tensor as _tensor
from chronus.tensor.enhanced_representation import (
    EnhancedTensorRepresentation as EnhancedTensorRepresentation,
)

_PUBLIC = list(getattr(_tensor, "__all__", None) or [n for n in vars(_tensor) if not n.startswith("_")])
globals().update({_name: getattr(_tensor, _name) for _name in _PUBLIC})
__all__ = sorted(set(_PUBLIC) | {"EnhancedTensorRepresentation"})
