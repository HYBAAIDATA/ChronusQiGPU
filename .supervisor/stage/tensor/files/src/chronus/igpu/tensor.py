"""chronus.igpu.tensor: the public export of the Chronus tensor representation.

The implementation lives in chronus.tensor; this module re-exports its public
API (the same objects) so iGPU-facing code and Chronus subsystems import it
from the iGPU namespace. TURING must not import it: the dependency runs from
Chronus to TURING, never the reverse. The representation is numerical (numpy)
and records truncation explicitly; it is not part of any exact path.

The exact lane is ``chronus.igpu.tensor.exact``: the ``turing.tensor`` module
of the hyba-turing distribution (exact field entries, CR factorisation in
place of truncated SVD, refusal instead of truncation). It is imported on
first access only, so this module and the rest of hyba-chronus keep working
without hyba-turing installed; accessing ``exact`` without it raises
ImportError.
"""

import importlib

from chronus import tensor as _tensor
from chronus.tensor.enhanced_representation import (
    EnhancedTensorRepresentation as EnhancedTensorRepresentation,
)

_PUBLIC = list(getattr(_tensor, "__all__", None) or [n for n in vars(_tensor) if not n.startswith("_")])
globals().update({_name: getattr(_tensor, _name) for _name in _PUBLIC})
__all__ = sorted(set(_PUBLIC) | {"EnhancedTensorRepresentation"})

_EXACT_LANE = "turing.tensor"
_EXACT_LANE_MISSING = (
    "the exact tensor lane needs the hyba-turing distribution, which provides turing.tensor; "
    "install the internal hyba-turing wheel next to hyba-chronus"
)


def __getattr__(name):
    # "exact" is deliberately not in __all__, so "from chronus.igpu.tensor import *" never needs TURING.
    if name == "exact":
        try:
            module = importlib.import_module(_EXACT_LANE)
        except ImportError as error:
            raise ImportError(_EXACT_LANE_MISSING, name=_EXACT_LANE) from error
        if not hasattr(module, "ExactMPS"):
            raise ImportError(f"{_EXACT_LANE_MISSING}; the installed turing package has no exact tensor layer",
                              name=_EXACT_LANE)
        globals()["exact"] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
