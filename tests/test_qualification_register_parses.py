"""Release qualification manifest must parse and never self-promote.

This validates metadata integrity only; it does not run or pass the external
release gates, and does not change the human qualification verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.simulated


def test_production_qualification_register_is_valid_json_and_fail_closed():
    repo_root = Path(__file__).resolve().parents[1]
    with (repo_root / "PRODUCTION_QUALIFIED.json").open(encoding="utf8") as f:
        manifest=json.load(f)
    assert manifest["status"]=="NOT_QUALIFIED"
    assert manifest["external_release_evidence"]["status"]=="MISSING"
    assert manifest["signature"] is None
    evidence=manifest["external_release_evidence"]["required"]
    assert isinstance(evidence,list) and len(evidence)==8
    assert "owner-approval.json" in evidence
