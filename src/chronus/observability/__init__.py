"""
Chronus Observability Package.
"""

from chronus.observability.metrics import (
    REGISTRY,
    shares_found_total,
    shares_submitted_total,
    shares_dropped_local_total,
    blocks_found_total,
    stratum_reconnects_total,
    pool_difficulty,
    hashrate_5m,
    nonce_range_covered_total,
    gatekeeper_reject_reason,
    stale_share_rate,
)

__all__ = [
    "REGISTRY",
    "shares_found_total",
    "shares_submitted_total",
    "shares_dropped_local_total",
    "blocks_found_total",
    "stratum_reconnects_total",
    "pool_difficulty",
    "hashrate_5m",
    "nonce_range_covered_total",
    "gatekeeper_reject_reason",
    "stale_share_rate",
]
