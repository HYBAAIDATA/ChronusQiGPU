"""Cost model from the unified-analytics program.

Figures are computed from the baseline the operator supplies. The document
scenario is one named input set, not a measurement of this repository.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostBaseline:
    systems: int
    license_per_system: float
    integration: float
    maintenance: float
    infrastructure: float

    def __post_init__(self) -> None:
        for name, value in (
            ("systems", self.systems),
            ("license_per_system", self.license_per_system),
            ("integration", self.integration),
            ("maintenance", self.maintenance),
            ("infrastructure", self.infrastructure),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True)
class PlatformCost:
    annual: float
    implementation: float

    def __post_init__(self) -> None:
        if self.annual < 0 or self.implementation < 0:
            raise ValueError("platform costs must be >= 0")


@dataclass(frozen=True)
class ROIResult:
    licensing: float
    current_annual: float
    unified_annual: float
    annual_savings: float
    implementation: float
    payback_months: float | None
    npv: float
    roi_3y: float | None
    discount_rate: float

    def as_dict(self) -> dict:
        return {
            "licensing": self.licensing,
            "current_annual": self.current_annual,
            "unified_annual": self.unified_annual,
            "annual_savings": self.annual_savings,
            "implementation": self.implementation,
            "payback_months": self.payback_months,
            "npv": self.npv,
            "roi_3y": self.roi_3y,
            "discount_rate": self.discount_rate,
        }


def assess(baseline: CostBaseline, platform: PlatformCost, *, discount_rate: float = 0.10, years: int = 5) -> ROIResult:
    if discount_rate < 0:
        raise ValueError("discount_rate must be >= 0")
    licensing = baseline.systems * baseline.license_per_system
    current = licensing + baseline.integration + baseline.maintenance + baseline.infrastructure
    savings = current - platform.annual
    if savings <= 0:
        payback = None
    else:
        payback = platform.implementation / (savings / 12.0)
    if discount_rate == 0:
        annuity = float(years)
    else:
        annuity = (1 - (1 + discount_rate) ** (-years)) / discount_rate
    npv = -platform.implementation + savings * annuity
    three_year = savings * 3 - platform.implementation
    roi = (three_year / platform.implementation) if platform.implementation else None
    return ROIResult(
        licensing=licensing,
        current_annual=current,
        unified_annual=platform.annual,
        annual_savings=savings,
        implementation=platform.implementation,
        payback_months=payback,
        npv=npv,
        roi_3y=roi,
        discount_rate=discount_rate,
    )


def document_fortune500_scenario(*, discount_rate: float = 0.10) -> dict:
    """The Harvard-draft scenario: 19 systems and the published cost ranges.

    Low pairs the bottom of every current-cost range with a $10M platform
    and a $5M implementation. High pairs the top of every current-cost
    range with a $20M platform and a $15M implementation. Savings are
    $58M and $145M.
    """
    low = assess(
        CostBaseline(19, 2_000_000, 10_000_000, 15_000_000, 5_000_000),
        PlatformCost(10_000_000, 5_000_000),
        discount_rate=discount_rate,
    )
    high = assess(
        CostBaseline(19, 5_000_000, 25_000_000, 30_000_000, 15_000_000),
        PlatformCost(20_000_000, 15_000_000),
        discount_rate=discount_rate,
    )
    return {"low": low.as_dict(), "high": high.as_dict(), "source": "unified analytics program draft"}


def financial_services_case(*, discount_rate: float = 0.10) -> ROIResult:
    """23-system book. Current cost 55M, platform 10M, savings 45M."""
    return assess(
        CostBaseline(23, 1_000_000, 12_000_000, 15_000_000, 5_000_000),
        PlatformCost(10_000_000, 5_000_000),
        discount_rate=discount_rate,
    )
