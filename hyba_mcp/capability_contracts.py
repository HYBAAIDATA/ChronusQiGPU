"""Bounded structural capability planning; no inference or execution authority."""
from __future__ import annotations
import hashlib
import json
import math
from copy import deepcopy

VERSION = "1.0"
MAX_BYTES = 262144
MAX_NODES = 64

class ContractError(ValueError):
    """Invalid or unsupported contract."""

def canonical(value):
    def check(item, depth=0):
        if depth > 20:
            raise ContractError("maximum nesting depth exceeded")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                check(child, depth + 1)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values():
                check(child, depth + 1)
            return
        raise ContractError("finite JSON values with string object keys required")
    check(value)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ContractError("contract exceeds byte limit")
    return encoded

def fields(value, required, optional=()):
    if type(value) is not dict:
        raise ContractError("object required")
    if set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ContractError("missing or unsupported contract fields")

def label(value):
    if type(value) is not str or not value.strip() or len(value) > 2048:
        raise ContractError("nonempty bounded string required")
    return value

def labels(value):
    if type(value) is not list or len(value) > MAX_NODES:
        raise ContractError("bounded string array required")
    for item in value:
        label(item)
    if len(set(value)) != len(value):
        raise ContractError("duplicate identifier")
    return value

def validate_plan(plan, catalog):
    """Validate DAG and declared coverage; no semantic or execution guarantee.

    Literal inputs only. The MCP boundary applies existing skill input schemas.
    Catalog digests pin declared contracts, not executable source or deployment.
    """
    canonical(plan)
    fields(plan, ("contract_version", "goal", "criteria", "nodes"))
    if plan["contract_version"] != VERSION:
        raise ContractError("unsupported contract version")
    label(plan["goal"])
    criteria = labels(plan["criteria"])
    if not criteria:
        raise ContractError("acceptance criteria required")
    nodes = plan["nodes"]
    if type(nodes) is not list or not 1 <= len(nodes) <= MAX_NODES:
        raise ContractError("one to 64 nodes required")
    by_id, covered, pins = {}, set(), {}
    for node in nodes:
        fields(node, ("id", "skill_id", "arguments", "depends_on", "covers"))
        node_id = label(node["id"])
        if node_id in by_id:
            raise ContractError("duplicate node ID")
        skill = label(node["skill_id"])
        if skill not in catalog:
            raise ContractError("unavailable skill: " + skill)
        if type(node["arguments"]) is not dict:
            raise ContractError("literal argument object required")
        dependencies = labels(node["depends_on"])
        coverage = labels(node["covers"])
        if node_id in dependencies:
            raise ContractError("self dependency")
        if not set(coverage) <= set(criteria):
            raise ContractError("unknown acceptance criterion")
        covered.update(coverage)
        by_id[node_id] = node
        pins[skill] = hashlib.sha256(canonical(catalog[skill]).encode()).hexdigest()
    if covered != set(criteria):
        raise ContractError("uncovered acceptance criteria")
    for node in nodes:
        if not set(node["depends_on"]) <= set(by_id):
            raise ContractError("missing dependency")
    remaining, order = set(by_id), []
    while remaining:
        ready = sorted(i for i in remaining if set(by_id[i]["depends_on"]) <= set(order))
        if not ready:
            raise ContractError("cyclic plan")
        order.extend(ready)
        remaining.difference_update(ready)
    digest = hashlib.sha256(canonical({"plan": plan, "capability_digests": pins}).encode()).hexdigest()
    return {"valid": True, "plan_hash": digest, "order": order,
            "capability_digests": pins, "criteria": criteria,
            "verification_status": "not_run", "execution_authorized": False,
            "theorem_proven": False}

def decompose_goal(goal, catalog):
    """Normalize explicit subgoals rather than infer a plan from prose."""
    canonical(goal)
    fields(goal, ("goal", "criteria"), ("subgoals",))
    label(goal["goal"])
    if not labels(goal["criteria"]):
        raise ContractError("acceptance criteria required")
    if "subgoals" not in goal:
        return {"status": "needs_clarification", "missing": [
            "explicit subgoals with registered skill IDs, literal arguments, dependencies and criterion coverage"
        ], "execution_authorized": False, "theorem_proven": False}
    plan = {"contract_version": VERSION, "goal": goal["goal"],
            "criteria": deepcopy(goal["criteria"]), "nodes": deepcopy(goal["subgoals"])}
    validation = validate_plan(plan, catalog)
    return {"status": "proposed", "plan": plan, "validation": validation,
            "decomposition_method": "explicit_structured_subgoals",
            "limitations": ["Structural coverage is not evidence of criterion satisfaction.",
                            "No execution, permission grant, artifact binding or semantic inference."]}
