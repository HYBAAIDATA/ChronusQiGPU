"""Layer 4. One deterministic call per claim, plus the economics identities."""

import pytest

from toe.unified.claims import CLAIMS
from toe.unified.economics import CostBaseline, PlatformCost, assess

from tests.test_toe_unified_invariants import SEED, exercise, load_cost_sheet, load_iris

TOUCHED = {claim.id for claim in CLAIMS}
assert SEED == 1517


@pytest.mark.parametrize("claim", CLAIMS, ids=[claim.id for claim in CLAIMS])
def test_unit_claim(claim):
    exercise(claim, load_iris())


def test_unit_economics_sheet_matches_the_functions():
    sheet = {row["scenario"]: row for row in load_cost_sheet()}
    low = assess(
        CostBaseline(19, int(sheet["low"]["license_each"]), int(sheet["low"]["integration"]), int(sheet["low"]["maintenance"]), int(sheet["low"]["infrastructure"])),
        PlatformCost(int(sheet["low"]["platform_annual"]), int(sheet["low"]["implementation"])),
    )
    high = assess(
        CostBaseline(19, int(sheet["high"]["license_each"]), int(sheet["high"]["integration"]), int(sheet["high"]["maintenance"]), int(sheet["high"]["infrastructure"])),
        PlatformCost(int(sheet["high"]["platform_annual"]), int(sheet["high"]["implementation"])),
    )
    bank = assess(
        CostBaseline(23, int(sheet["bank"]["license_each"]), int(sheet["bank"]["integration"]), int(sheet["bank"]["maintenance"]), int(sheet["bank"]["infrastructure"])),
        PlatformCost(int(sheet["bank"]["platform_annual"]), int(sheet["bank"]["implementation"])),
    )
    assert low.annual_savings == 58_000_000
    assert high.annual_savings == 145_000_000
    assert bank.annual_savings == 45_000_000
