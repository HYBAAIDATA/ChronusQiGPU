"""Scholarship ledger: the split sums, and recognize_value writes it."""

import pytest

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.impact import INSTITUTIONS


def test_split_sums_to_allocation():
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.1)
    entry = platform.recognize_value(1000.0, "contract-7")
    shares = platform.ledger.by_institution()
    assert entry.allocated == 100.0
    assert set(shares) == set(INSTITUTIONS)
    assert sum(shares.values()) == pytest.approx(100.0)
    assert len(platform.ledger.entries()) == 1


def test_recognize_value_flow():
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.05)
    platform.recognize_value(200.0, "contract-8")
    assert platform.ledger.committed() == pytest.approx(10.0)
    assert sum(platform.ledger.by_institution().values()) == pytest.approx(10.0)
