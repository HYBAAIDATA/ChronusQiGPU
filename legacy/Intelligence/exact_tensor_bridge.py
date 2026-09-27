"""TOE adapter for the canonical exact tensor — compatibility facade.

The exact witness layer (the F4 field Q(sqrt(2)) + i Q(sqrt(2)), the
``ExactStateVector`` algebra, and the ``ExactTOETensor`` adapter) lives in
the declared substrate module ``Intelligence.exact_tensor``.  This module
re-exports the adapter's public names so existing
``Intelligence.exact_tensor_bridge`` imports keep resolving.  No platform
``mla1517.quantum`` dependency remains in this path.
"""

from __future__ import annotations

from .exact_tensor import ExactTOETensor, canonical_digest

__all__ = ["ExactTOETensor", "canonical_digest"]
