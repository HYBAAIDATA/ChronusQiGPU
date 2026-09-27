"""The cost model is deterministic and reproduces the draft scenario."""

from toe.unified.economics import CostBaseline, PlatformCost, assess, document_fortune500_scenario


def test_document_scenario_numbers():
    scenario = document_fortune500_scenario()
    assert scenario["low"]["licensing"] == 38_000_000
    assert scenario["high"]["licensing"] == 95_000_000
    assert scenario["low"]["current_annual"] == 68_000_000
    assert scenario["high"]["current_annual"] == 165_000_000
    assert scenario["low"]["annual_savings"] == 58_000_000
    assert scenario["high"]["annual_savings"] == 145_000_000


def test_assess_is_deterministic():
    baseline = CostBaseline(2, 10, 1, 1, 1)
    platform = PlatformCost(5, 3)
    assert assess(baseline, platform).as_dict() == assess(baseline, platform).as_dict()
