"""chronus.igpu.tensor: the public export of the Chronus tensor representation.

The implementation lives in chronus.tensor; this module re-exports its public
API (the same objects) so iGPU-facing code and Chronus subsystems import it
from the iGPU namespace. TURING must not import it: the dependency runs from
Chronus to TURING, never the reverse. The representation is numerical (numpy)
and records truncation explicitly; it is not part of any exact path.
"""

from chronus import tensor as _tensor
from chronus.tensor.enhanced_representation import (
    EnhancedTensorRepresentation as EnhancedTensorRepresentation,
)

_PUBLIC = list(getattr(_tensor, "__all__", None) or [n for n in vars(_tensor) if not n.startswith("_")])
globals().update({_name: getattr(_tensor, _name) for _name in _PUBLIC})
__all__ = sorted(set(_PUBLIC) | {"EnhancedTensorRepresentation"})
