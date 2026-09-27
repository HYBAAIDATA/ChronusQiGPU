"""Phase gates open and close on the thresholds the platform actually reads."""

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.economics import CostBaseline, PlatformCost


def _gate(platform, name):
    return next(gate for gate in platform.phases() if gate.name == name)


def test_closed_gates_on_an_empty_platform():
    platform = UnifiedAnalyticsPlatform()
    assert _gate(platform, "connectors_integrated").passed is False
    assert _gate(platform, "satisfaction").passed is False
    assert _gate(platform, "roi_positive").passed is False
    assert _gate(platform, "enterprise_systems").passed is False
    assert _gate(platform, "processing_reduction").passed is False
    assert _gate(platform, "roi_400").passed is False
    assert _gate(platform, "patents").passed is False


def test_satisfaction_gate():
    platform = UnifiedAnalyticsPlatform()
    platform.feedback("ada", "risk", rating=0.94)
    assert _gate(platform, "satisfaction").passed is False
    platform.feedback("ada", "risk", rating=1.0)
    assert _gate(platform, "satisfaction").passed is True


def test_downtime_gate():
    platform = UnifiedAnalyticsPlatform()
    assert _gate(platform, "downtime").passed is True
    platform.operations.unplanned_downtime = 1
    assert _gate(platform, "downtime").passed is False
    platform.operations.unplanned_downtime = 0
    assert _gate(platform, "downtime").passed is True
    platform.economics(CostBaseline(1, 10, 0, 0, 0), PlatformCost(1, 0))
    assert _gate(platform, "roi_positive").passed is True
