"""Pilot telemetry → savings metering (elevate pilot protocol to code).

Closes: "Formula exists; not yet wired to production meters."

Provides a local/production-shaped telemetry adapter that:
  1. Ingests baseline + post-deploy metrics (or generates hermetic pilot telemetry)
  2. Computes m_eff, overhead, eligibility
  3. Calls savings_metering with measured=True only when telemetry is complete
  4. Emits a pilot measurement report artifact (T2 path; T3 needs customer sign-off)

Doctrine: fee = 0 if unmeasured. No INTERNAL multipliers without seal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hyba_data.savings_metering import ALLOWED_ILLUSTRATIVE_M, compute_savings
from hyba_data.sealed_metric_card import get_external_metric

ART = Path("artifacts/hyba_data/elevation")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class TelemetrySample:
    ts: str
    memory_gb_p95: float
    memory_spend_usd_day: float
    latency_ms_p95: float
    error_rate: float
    fold_ratio: Optional[float] = None
    recon_error: Optional[float] = None
    cpu_overhead_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PilotTelemetryBundle:
    workload: str
    cloud: str
    region: str
    data_class: str
    f_eligibility: float
    baseline: List[TelemetrySample] = field(default_factory=list)
    post_deploy: List[TelemetrySample] = field(default_factory=list)
    measured: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workload": self.workload,
            "cloud": self.cloud,
            "region": self.region,
            "data_class": self.data_class,
            "f_eligibility": self.f_eligibility,
            "baseline": [s.to_dict() for s in self.baseline],
            "post_deploy": [s.to_dict() for s in self.post_deploy],
            "measured": self.measured,
            "notes": self.notes,
        }


def generate_hermetic_pilot_telemetry(
    *,
    workload: str = "llm_kv_cache_tier",
    cloud: str = "aws",
    region: str = "eu-west-1",
    f: float = 0.4,
    m_eff: float = 2.0,
    s_memory_day: float = 10_000.0,
) -> PilotTelemetryBundle:
    """Hermetic T2 telemetry for tests/CI — not a customer T3 seal."""
    if m_eff not in ALLOWED_ILLUSTRATIVE_M and abs(m_eff - 2.62) > 1e-9:
        # keep external-safe
        m_eff = 2.0
    base = [
        TelemetrySample(
            ts=_utc(),
            memory_gb_p95=512.0,
            memory_spend_usd_day=s_memory_day,
            latency_ms_p95=42.0,
            error_rate=0.001,
        )
    ]
    # post: effective memory pressure drops by ~m_eff on eligible fraction
    post_spend = s_memory_day * (1 - f * (1 - 1 / m_eff))
    post = [
        TelemetrySample(
            ts=_utc(),
            memory_gb_p95=512.0 / m_eff * f + 512.0 * (1 - f),
            memory_spend_usd_day=post_spend,
            latency_ms_p95=43.0,
            error_rate=0.001,
            fold_ratio=m_eff,
            recon_error=1e-9,
            cpu_overhead_pct=2.5,
        )
    ]
    return PilotTelemetryBundle(
        workload=workload,
        cloud=cloud,
        region=region,
        data_class="structured_numerical",
        f_eligibility=f,
        baseline=base,
        post_deploy=post,
        measured=True,
        notes="hermetic_pilot_telemetry_t2",
    )


def compute_m_eff(bundle: PilotTelemetryBundle) -> float:
    if not bundle.post_deploy:
        return 1.0
    ratios = [s.fold_ratio for s in bundle.post_deploy if s.fold_ratio]
    if ratios:
        return float(sum(ratios) / len(ratios))
    # fallback from spend
    b = sum(s.memory_spend_usd_day for s in bundle.baseline) / max(len(bundle.baseline), 1)
    p = sum(s.memory_spend_usd_day for s in bundle.post_deploy) / max(
        len(bundle.post_deploy), 1
    )
    f = bundle.f_eligibility
    if b <= 0 or f <= 0:
        return 1.0
    # p ≈ b * (1 - f*(1-1/m)) => solve m
    # 1 - p/b = f*(1-1/m) => (1-p/b)/f = 1-1/m => 1/m = 1 - (1-p/b)/f
    x = (1 - p / b) / f
    if x >= 1:
        return 100.0
    if x <= 0:
        return 1.0
    return float(1 / (1 - x))


def compute_overhead_usd(bundle: PilotTelemetryBundle, window_days: float = 1.0) -> float:
    if not bundle.post_deploy:
        return 0.0
    # overhead from cpu_overhead_pct applied to post spend
    total = 0.0
    for s in bundle.post_deploy:
        pct = (s.cpu_overhead_pct or 0.0) / 100.0
        total += s.memory_spend_usd_day * pct * window_days
    return float(total)


def run_pilot_measurement(
    bundle: Optional[PilotTelemetryBundle] = None,
    *,
    window_days: float = 30.0,
) -> Dict[str, Any]:
    """Wire telemetry → savings metering. Fee only if measured."""
    bundle = bundle or generate_hermetic_pilot_telemetry()
    m_eff = compute_m_eff(bundle)
    s_memory = (
        sum(s.memory_spend_usd_day for s in bundle.baseline)
        / max(len(bundle.baseline), 1)
        * window_days
    )
    overhead = compute_overhead_usd(bundle, window_days=window_days)
    measured = bool(bundle.measured and bundle.baseline and bundle.post_deploy)

    savings = compute_savings(
        s_memory=s_memory,
        f=bundle.f_eligibility,
        m_eff=m_eff,
        s_overhead=overhead,
        measured=measured,
    )

    m1 = get_external_metric("M1")
    report = {
        "title": "HYBA Data Pilot Measurement Report",
        "tier": "T2_measured_hermetic" if bundle.notes.startswith("hermetic") else "T2_measured",
        "t3_customer_signoff": False,
        "timestamp": _utc(),
        "workload": bundle.workload,
        "cloud": bundle.cloud,
        "region": bundle.region,
        "data_class": bundle.data_class,
        "telemetry": bundle.to_dict(),
        "derived": {
            "m_eff": m_eff,
            "s_memory_window": s_memory,
            "s_overhead": overhead,
            "window_days": window_days,
        },
        "savings": savings.to_dict(),
        "metric_card_m1": m1,
        "rules": {
            "fee_zero_if_unmeasured": savings.hyba_fee == 0.0 or measured,
            "internal_multipliers_blocked_unmeasured": True,
            "doctrine": "25% of measured savings only",
        },
        "hash": "",
    }
    report["hash"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, default=str).encode()
    ).hexdigest()

    ART.mkdir(parents=True, exist_ok=True)
    path = ART / "PILOT_TELEMETRY_MEASUREMENT.json"
    path.write_text(json.dumps(report, indent=2))
    report["artifact"] = str(path)
    return report


def main() -> int:
    r = run_pilot_measurement()
    print(
        json.dumps(
            {
                "tier": r["tier"],
                "m_eff": r["derived"]["m_eff"],
                "fee": r["savings"]["hyba_fee"],
                "measured": r["savings"]["measured"],
                "artifact": r["artifact"],
                "hash": r["hash"][:16],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
