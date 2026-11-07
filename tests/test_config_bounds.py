"""Runtime bounds are environment-configurable, never hardcoded."""

import json

import pytest

from chronus.config import runtime_bounds
from chronus.execution import ExecutionRouter
from chronus.execution.mining import partition_nonce_range


def test_defaults_match_documented_architecture():
    bounds = runtime_bounds()
    assert bounds["search_lanes"] == 32
    assert bounds["storage_lanes"] == 32
    assert bounds["max_pv_order"] == 360


def test_env_override_changes_behavior(monkeypatch):
    monkeypatch.setenv("CHRONUS_SEARCH_LANES", "8")
    lanes = partition_nonce_range(0, 800)
    assert len(lanes) == 8
    monkeypatch.setenv("CHRONUS_MAX_METALLIC_M", "2")
    with pytest.raises(ValueError, match="between 1 and 2"):
        ExecutionRouter().execute(json.dumps({"m": 3, "index": 1}).encode(), "METALLIC_SCALE")


def test_invalid_env_values_fail_closed(monkeypatch):
    monkeypatch.setenv("CHRONUS_SEARCH_LANES", "not-a-number")
    with pytest.raises(ValueError, match="must be an integer"):
        runtime_bounds()
    monkeypatch.setenv("CHRONUS_SEARCH_LANES", "0")
    with pytest.raises(ValueError, match="must be positive"):
        runtime_bounds()
