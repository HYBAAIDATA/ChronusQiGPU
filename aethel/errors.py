"""Typed exception hierarchy for the Aethel substrate.

Every declared failure mode maps to a typed exception — no silent
fallbacks, no bare ``Exception`` escapes at tier boundaries.

    STORAGE   InvalidAddress, GapDetected, SegmentMissing, AbiVersionMismatch
    ENCODING  FoldDomainOverflow, EncodingError
    HANDOFF   HandoffRejection
"""

from __future__ import annotations


class AethelError(RuntimeError):
    """Base class for every Aethel failure."""


# -- STORAGE (Fibonacci + Cassini) -------------------------------------------


class InvalidAddress(AethelError):
    """An address was forged, regressed, or is not on the true Fibonacci
    sequence — raised at write/register time, never at read time."""


class GapDetected(AethelError):
    """The ledger stream is missing an entry — a removed or uncommitted
    index — detected before retrieval is allowed to proceed."""


class SegmentMissing(AethelError):
    """A shared-memory region or journal file expected at attach time does
    not exist. Raised instead of silently creating fresh state."""


class AbiVersionMismatch(AethelError):
    """The mapped region's ABI version differs from ``AETHEL_ABI_VERSION``."""


# -- ENCODING (Binet + Zeckendorf) --------------------------------------------


class EncodingError(AethelError):
    """Generic encoding-layer failure."""


class FoldDomainOverflow(EncodingError):
    """Payload exceeds the declared fold domain (``max_fold_len``).
    Raised in place of any silent truncation or extension."""


class ZeckendorfInvariantError(EncodingError):
    """A Zeckendorf vector violated non-adjacency or failed to decode to a
    canonical value — declared unreachable; its appearance means corruption."""


# -- HANDOFF (geodesic-engine adapter) -----------------------------------------


class HandoffRejection(AethelError):
    """The geodesic engine rejected an adapter-produced point, or a point
    failed to round-trip back to the originating storage block."""


class EngineUnavailable(HandoffRejection):
    """The geodesic engine modules could not be imported in this
    environment — the handoff is declared, not faked."""
