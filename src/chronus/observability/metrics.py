"""
Chronus Stratum Mining Observability & Metrics Registry.

Exposes the ten canonical protocol metrics:
1. shares_found_total: Counter
2. shares_submitted_total: Counter
3. shares_dropped_local_total: Counter
4. blocks_found_total: Counter
5. stratum_reconnects_total: Counter
6. pool_difficulty: Gauge
7. hashrate_5m: Gauge
8. nonce_range_covered_total: Counter
9. gatekeeper_reject_reason: LabeledCounter (counts per DropReason)
10. stale_share_rate: Gauge (computed percentage: (stale / submitted) * 100)
"""

from typing import Dict, Any


class Metric:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


class Counter(Metric):
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.value: int = 0

    def inc(self, amount: int = 1) -> None:
        self.value += amount

    def reset(self) -> None:
        self.value = 0


class Gauge(Metric):
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.value: float = 0.0

    def set(self, val: float | int) -> None:
        self.value = float(val)


class LabeledCounter(Metric):
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.counts: Dict[str, int] = {}

    def inc(self, label: str, amount: int = 1) -> None:
        self.counts[label] = self.counts.get(label, 0) + amount

    def get(self, label: str) -> int:
        return self.counts.get(label, 0)


class StaleShareRateGauge(Gauge):
    def __init__(self, registry: "MetricsRegistry"):
        super().__init__("stale_share_rate", "Network stale share rate as percentage (stale / submitted * 100)")
        self._registry = registry

    @property
    def value(self) -> float:
        submitted = self._registry.shares_submitted_total.value
        if submitted == 0:
            return 0.0
        return (self._registry._stale_shares_total.value / submitted) * 100.0

    @value.setter
    def value(self, val: float) -> None:
        pass


class MetricsRegistry:
    def __init__(self):
        self.shares_found_total = Counter("shares_found_total", "Total candidate shares discovered locally")
        self.shares_submitted_total = Counter("shares_submitted_total", "Total shares transmitted to pool")
        self.shares_dropped_local_total = Counter("shares_dropped_local_total", "Total shares dropped by local gatekeeper")
        self.blocks_found_total = Counter("blocks_found_total", "Total valid Bitcoin mainnet block solutions discovered")
        self.stratum_reconnects_total = Counter("stratum_reconnects_total", "Total Stratum connection drops and reconnects")
        self.pool_difficulty = Gauge("pool_difficulty", "Current active mining difficulty assigned by pool")
        self.hashrate_5m = Gauge("hashrate_5m", "5-minute rolling average hashrate in H/s")
        self.nonce_range_covered_total = Counter("nonce_range_covered_total", "Total count of 32-bit nonces scanned")
        self.gatekeeper_reject_reason = LabeledCounter("gatekeeper_reject_reason", "Counts of local drops partitioned by DropReason")
        self._stale_shares_total = Counter("stale_shares_total", "Internal count of stale shares")
        self.stale_share_rate = StaleShareRateGauge(self)

    def record_stale_share(self) -> None:
        self._stale_shares_total.inc()
        self.gatekeeper_reject_reason.inc("STALE_JOB")

    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "shares_found_total": self.shares_found_total.value,
            "shares_submitted_total": self.shares_submitted_total.value,
            "shares_dropped_local_total": self.shares_dropped_local_total.value,
            "blocks_found_total": self.blocks_found_total.value,
            "stratum_reconnects_total": self.stratum_reconnects_total.value,
            "pool_difficulty": self.pool_difficulty.value,
            "hashrate_5m": self.hashrate_5m.value,
            "nonce_range_covered_total": self.nonce_range_covered_total.value,
            "gatekeeper_reject_reason": dict(self.gatekeeper_reject_reason.counts),
            "stale_share_rate": self.stale_share_rate.value,
        }


# Global registry instance
REGISTRY = MetricsRegistry()

# Module-level exports for the 10 canonical metrics
shares_found_total = REGISTRY.shares_found_total
shares_submitted_total = REGISTRY.shares_submitted_total
shares_dropped_local_total = REGISTRY.shares_dropped_local_total
blocks_found_total = REGISTRY.blocks_found_total
stratum_reconnects_total = REGISTRY.stratum_reconnects_total
pool_difficulty = REGISTRY.pool_difficulty
hashrate_5m = REGISTRY.hashrate_5m
nonce_range_covered_total = REGISTRY.nonce_range_covered_total
gatekeeper_reject_reason = REGISTRY.gatekeeper_reject_reason
stale_share_rate = REGISTRY.stale_share_rate
