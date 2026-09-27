"""Industry functions return the declared schema on fixtures."""

from toe.unified import UnifiedAnalyticsPlatform


def test_finance_schemas():
    platform = UnifiedAnalyticsPlatform()
    risk = platform.run_application("risk", rows=[{"score": 0.2}, {"score": 0.9}])
    assert risk == {"count": 2, "mean": 0.55, "high": 1}
    fraud = platform.run_application("fraud", rows=[{"fraud": 1}, {"fraud": 0}, {"fraud": 1}])
    assert fraud["rate"] == 2 / 3
    report = platform.run_application(
        "regulatory",
        rows=[{"jurisdiction": "UK", "amount": 2}, {"jurisdiction": "UK", "amount": 3}],
    )
    assert report == [{"jurisdiction": "UK", "amount": 5.0, "rows": 2}]
    view = platform.run_application(
        "customer_360",
        tables={"accounts": [{"customer_id": "c1", "region": "emea"}]},
    )
    assert view[0]["customer_id"] == "c1"


def test_manufacturing_schemas():
    platform = UnifiedAnalyticsPlatform()
    trend = platform.run_application("maintenance", rows=[{"reading": 1.0}, {"reading": 3.0}])
    assert trend["direction"] == "rising"
    quality = platform.run_application("quality", rows=[{"defect": 1}, {"defect": 0}])
    assert quality["metric"] == "defect_rate"
    stock = platform.run_application("inventory", rows=[{"sku": "a", "qty": 2}, {"sku": "a", "qty": 3}])
    assert stock == [{"sku": "a", "qty": 5.0}]
    power = platform.run_application("energy", rows=[{"meter": "m", "kwh": 4.0}])
    assert power["total_kwh"] == 4.0


def test_healthcare_pack_uses_numeric_risk():
    platform = UnifiedAnalyticsPlatform()
    pack = platform.industry("healthcare")
    assert pack["applications"] == ("risk", "customer_360")
    same = platform.run_application("risk", rows=[{"score": 1.0}])
    assert same["high"] == 1
