"""Structural planning regression tests; no external services required."""
from copy import deepcopy
import pytest
from hyba_mcp.capability_contracts import ContractError, canonical, decompose_goal, validate_plan

CATALOG = {"test.skill": {"input_schema": {"type": "object"}, "source": "fixture", "limitations": []}}

def plan():
    return {"contract_version": "1.0", "goal": "Assess supplied telemetry", "criteria": ["C1"], "nodes": [
        {"id": "A", "skill_id": "test.skill", "arguments": {}, "depends_on": [], "covers": ["C1"]},
        {"id": "B", "skill_id": "test.skill", "arguments": {}, "depends_on": ["A"], "covers": []}]}

def test_order_and_no_authority():
    result = validate_plan(plan(), CATALOG)
    assert result["order"] == ["A", "B"]
    assert result["execution_authorized"] is False
    assert result["verification_status"] == "not_run"

def test_digest_changes_with_contract():
    original = validate_plan(plan(), CATALOG)["plan_hash"]
    changed = deepcopy(CATALOG)
    changed["test.skill"]["limitations"] = ["updated"]
    assert validate_plan(plan(), changed)["plan_hash"] != original
    assert validate_plan(plan(), CATALOG)["plan_hash"] == original

@pytest.mark.parametrize("case", ["cycle", "duplicate", "unknown", "uncovered", "forgery", "missing", "self"])
def test_reject_invalid_graph(case):
    p = plan()
    if case == "cycle": p["nodes"][0]["depends_on"] = ["B"]
    if case == "duplicate": p["nodes"][1]["id"] = "A"
    if case == "unknown": p["nodes"][0]["skill_id"] = "absent"
    if case == "uncovered": p["criteria"].append("C2")
    if case == "forgery": p["execution_authorized"] = True
    if case == "missing": p["nodes"][1]["depends_on"] = ["absent"]
    if case == "self": p["nodes"][0]["depends_on"] = ["A"]
    with pytest.raises(ContractError): validate_plan(p, CATALOG)

@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "bad"}, object()])
def test_non_json(value):
    with pytest.raises(ContractError): canonical({"value": value})

def test_prose_requires_clarification():
    result = decompose_goal({"goal": "Build onboarding", "criteria": ["C1"]}, CATALOG)
    assert result["status"] == "needs_clarification"

def test_decomposition_copies_inputs():
    p = plan()
    result = decompose_goal({"goal": p["goal"], "criteria": p["criteria"], "subgoals": p["nodes"]}, CATALOG)
    p["nodes"][0]["id"] = "changed"
    assert result["plan"]["nodes"][0]["id"] == "A"
