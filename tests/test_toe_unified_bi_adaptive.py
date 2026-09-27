"""Grammar, dashboard order, and the signals the adaptive interface reads."""

import inspect

import pytest

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.adaptive import AdaptiveInterface
from toe.unified.bi import QueryError, parse


ACCEPTED = (
    "show revenue by region from accounts where revenue > 6",
    "count accounts where region = emea",
    "what drives risk",
    "quality of accounts",
    "quality",
    "health",
    "roi",
)


def test_grammar_accepts_and_rejects():
    for question in ACCEPTED:
        assert parse(question) == parse(question)
    with pytest.raises(QueryError):
        parse("drop the table")
    with pytest.raises(QueryError):
        parse("")


def test_dashboard_order_follows_use():
    platform = UnifiedAnalyticsPlatform()
    platform.feedback("ada", "risk", depth=1)
    platform.feedback("ada", "risk", depth=1)
    widgets = [{"id": "energy", "title": "Energy"}, {"id": "risk", "title": "Risk"}]
    spec = platform.dashboard_for("ada", "ops", widgets)
    assert [widget["id"] for widget in spec["widgets"]] == ["risk", "energy"]
    assert {widget["id"] for widget in spec["widgets"]} == {"risk", "energy"}


def test_adaptive_reads_only_declared_signals():
    parameters = list(inspect.signature(AdaptiveInterface.observe).parameters)
    assert parameters == ["self", "user", "widget", "depth", "at"]
