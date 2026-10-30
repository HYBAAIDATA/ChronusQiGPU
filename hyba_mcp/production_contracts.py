"""Versioned definitions, bounded validation and safe failures; no authority grants."""
import hashlib
import json
import math
import uuid

class ContractViolation(ValueError):
    pass

def bounded_json(value):
    count = 0
    def walk(item, depth=0):
        nonlocal count
        count += 1
        if depth > 20 or count > 20000:
            raise ContractViolation("JSON complexity limit")
        if item is None or type(item) in (bool, int, str): return
        if type(item) is float and math.isfinite(item): return
        if type(item) is list:
            for child in item: walk(child, depth + 1)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values(): walk(child, depth + 1)
            return
        raise ContractViolation("Finite JSON required")
    walk(value)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > 262144:
            raise ContractViolation("Payload limit")
    except (ValueError, OverflowError, UnicodeError) as exc:
        raise ContractViolation("JSON serialization failed") from exc
    return encoded

KEYWORDS = {"type", "properties", "required", "additionalProperties", "items", "enum",
    "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems",
    "description", "title", "default"}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}

def schema_contract(schema, depth=0):
    if depth > 20 or type(schema) is not dict or set(schema) - KEYWORDS:
        raise ContractViolation("Unsupported schema")
    kinds = schema.get("type")
    kinds = kinds if type(kinds) is list else [kinds]
    if not kinds or any(type(k) is not str or k not in TYPES for k in kinds):
        raise ContractViolation("Explicit supported schema type required")
    if "properties" in schema:
        if type(schema["properties"]) is not dict:
            raise ContractViolation("Invalid properties")
        for child in schema["properties"].values(): schema_contract(child, depth + 1)
    if "items" in schema: schema_contract(schema["items"], depth + 1)
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise ContractViolation("Only boolean additionalProperties supported")
    if "required" in schema:
        required = schema["required"]
        if type(required) is not list or any(type(k) is not str for k in required) or len(set(required)) != len(required):
            raise ContractViolation("Invalid required keys")
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise ContractViolation("Invalid size bound")
    for key in ("minimum", "maximum"):
        if key in schema and (type(schema[key]) not in (int, float) or (type(schema[key]) is float and not math.isfinite(schema[key]))):
            raise ContractViolation("Invalid numeric bound")
    if "enum" in schema and (type(schema["enum"]) is not list or not schema["enum"]):
        raise ContractViolation("Invalid enum")

def validate_value(value, schema):
    bounded_json(value); bounded_json(schema); schema_contract(schema)
    def check(item, rule):
        kind = {dict: "object", list: "array", str: "string", bool: "boolean", int: "integer", float: "number", type(None): "null"}[type(item)]
        kinds = rule["type"] if type(rule["type"]) is list else [rule["type"]]
        if kind not in kinds and not (kind == "integer" and "number" in kinds):
            raise ContractViolation("Type mismatch")
        if "enum" in rule and not any(bounded_json(item) == bounded_json(v) for v in rule["enum"]):
            raise ContractViolation("Enum mismatch")
        if kind == "object":
            props = rule.get("properties", {})
            if set(rule.get("required", [])) - set(item): raise ContractViolation("Required field missing")
            if rule.get("additionalProperties") is False and set(item) - set(props): raise ContractViolation("Unknown field")
            for key, child in item.items():
                if key in props: check(child, props[key])
        if kind == "array" and "items" in rule:
            for child in item: check(child, rule["items"])
        if kind in ("integer", "number"):
            if "minimum" in rule and item < rule["minimum"]: raise ContractViolation("Below minimum")
            if "maximum" in rule and item > rule["maximum"]: raise ContractViolation("Above maximum")
        if kind in ("string", "array"):
            low, high = ("minLength", "maxLength") if kind == "string" else ("minItems", "maxItems")
            if low in rule and len(item) < rule[low]: raise ContractViolation("Below length minimum")
            if high in rule and len(item) > rule[high]: raise ContractViolation("Above length maximum")
    check(value, schema)

ERRORS = {
    "invalid_contract": "Request does not satisfy its contract.",
    "unknown_capability": "Capability is not registered.",
    "unsupported_contract": "Capability contract is unsupported or unavailable.",
    "invalid_output": "Capability output failed validation.",
    "permission_denied": "Execution is not authorized.",
    "execution_failed": "Capability execution failed; no automatic retry was performed.",
    "timeout": "Capability execution exceeded its time limit.",
    "internal_error": "Request failed safely; quote the correlation ID to the operator.",
}

def failure(code):
    return {"ok": False, "error": {"code": code, "message": ERRORS[code],
        "retryable": False, "correlation_id": uuid.uuid4().hex},
        "execution_authorized": False, "theorem_proven": False}

def capability_definition(entry):
    bounded_json(entry)
    for field in ("skill_id", "source"):
        if type(entry.get(field)) is not str or not entry[field].strip():
            raise ContractViolation("Capability identity/source required")
    for field in ("input_schema", "output_schema"):
        schema_contract(entry.get(field))
    result = {"contract_version": "1.0", "skill_id": entry["skill_id"],
        "source": entry["source"], "input_schema": entry["input_schema"],
        "output_schema": entry["output_schema"], "limitations": entry.get("limitations", []),
        "authority": "advisory; deployment authorization required",
        "error_contract_version": "1.0", "automatic_retry": False,
        "cost_estimate": entry.get("cost_estimate"), "cost_unit": "registry estimate; not currency",
        "source_attested": False, "theorem_proven": False}
    result["contract_digest"] = hashlib.sha256(bounded_json(result).encode()).hexdigest()
    return json.loads(bounded_json(result))
