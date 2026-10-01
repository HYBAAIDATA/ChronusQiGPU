"""Re-export of the mining tensor-advisory contract.

The canonical implementation stays in ``hyba.hybrid.tensor_advisor`` (it is
imported throughout the mining stack already); this module exists so that
``tensor`` is a complete, self-contained logical surface without forking the
advisory boundary logic. See that module's docstring for the enforced rule:
a ranker may only *reorder* an already certified set of nonce windows.
"""

from __future__ import annotations

from hyba.hybrid.tensor_advisor import (
    IdentityWindowRanker,
    TensorAdviceEvidence,
    TensorAdviceViolation,
    WindowRanker,
    apply_tensor_advice,
)

__all__ = [
    "IdentityWindowRanker",
    "TensorAdviceEvidence",
    "TensorAdviceViolation",
    "WindowRanker",
    "apply_tensor_advice",
]
