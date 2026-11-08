import sys
sys.path.insert(0, "src")

import chronus.observability.metrics as m

required_metrics = [
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

print("--- OBSERVABILITY METRICS VERIFICATION ---")
for metric_name in required_metrics:
    assert hasattr(m, metric_name), f"Missing metric: {metric_name}"
    val = getattr(m, metric_name)
    print(f"Metric: {metric_name:28s} -> {type(val).__name__} (value: {getattr(val, 'value', val)})")

print(f"Total verified: {len(required_metrics)}/10 metrics present.")
