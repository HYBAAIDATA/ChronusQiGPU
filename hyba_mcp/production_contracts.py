"""Fail-closed restricted capability schemas and bounded public responses."""
import hashlib
import json
import math
import uuid

class ContractViolation(ValueError):
    pass

def bounded_json(value):
    count = 0
    def walk(v, depth=0):
        nonlocal count
        count += 1
        if depth > 20 or count > 20000: raise ContractViolation("complexity")
        if v is None or type(v) in (str, bool, int): return
        if type(v) is float and math.isfinite(v): return
        if type(v) is list:
            for child in v: walk(child, depth+1)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for child in v.values(): walk(child, depth+1)
            return
        raise ContractViolation("finite JSON required")
    walk(value)
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(text.encode()) > 262144: raise ContractViolation("payload")
        return text
    except (ValueError, OverflowError, UnicodeError) as exc:
        raise ContractViolation("serialization") from exc

def equal(a, b):
    if type(a) in (int, float) and type(b) in (int, float): return a == b
    return bounded_json(a) == bounded_json(b)

FAMILIES = {"object": {"properties", "required", "additionalProperties"},
    "array": {"items", "minItems", "maxItems"}, "string": {"minLength", "maxLength"},
    "number": {"minimum", "maximum"}}
KEYWORDS = {"type", "enum", "default", "title", "description"} | set().union(*FAMILIES.values())
TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}

def schema_contract(schema, depth=0):
    if depth == 0: bounded_json(schema)
    if depth > 20 or type(schema) is not dict or set(schema)-KEYWORDS:
        raise ContractViolation("unsupported schema")
    kinds = schema.get("type")
    kinds = kinds if type(kinds) is list else [kinds]
    if not kinds or any(type(k) is not str or k not in TYPES for k in kinds) or len(set(kinds)) != len(kinds):
        raise ContractViolation("invalid types")
    nonnull = set(kinds)-{"null"}
    if len(nonnull) > 1: raise ContractViolation("only nullable single-type unions supported")
    for family, keys in FAMILIES.items():
        allowed = {"integer", "number"} if family == "number" else {family}
        if set(schema) & keys and (not nonnull or not nonnull <= allowed):
            raise ContractViolation("keyword/type incompatibility")
    props = schema.get("properties", {})
    if type(props) is not dict: raise ContractViolation("properties")
    for child in props.values(): schema_contract(child, depth+1)
    required = schema.get("required", [])
    if type(required) is not list or any(type(k) is not str for k in required) or len(set(required)) != len(required) or not set(required) <= set(props):
        raise ContractViolation("required keys must be declared")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise ContractViolation("additionalProperties")
    if "items" in schema: schema_contract(schema["items"], depth+1)
    for low, high in (("minimum", "maximum"), ("minLength", "maxLength"), ("minItems", "maxItems")):
        for key in (low, high):
            if key in schema:
                v = schema[key]
                if low == "minimum":
                    if type(v) not in (int,float) or (type(v) is float and not math.isfinite(v)): raise ContractViolation("numeric bound")
                elif type(v) is not int or v < 0: raise ContractViolation("size bound")
        if low in schema and high in schema:
            if schema[low] > schema[high]: raise ContractViolation("contradictory bounds")
            if low == "minimum" and nonnull == {"integer"} and math.ceil(schema[low]) > math.floor(schema[high]):
                raise ContractViolation("no integer satisfies bounds")
    for annotation in ("title", "description"):
        if annotation in schema and type(schema[annotation]) is not str: raise ContractViolation("annotation")
    if "enum" in schema:
        values = schema["enum"]
        if type(values) is not list or not values: raise ContractViolation("enum")
        for i, value in enumerate(values):
            if any(equal(value, old) for old in values[:i]): raise ContractViolation("duplicate enum")
            _check(value, {k:v for k,v in schema.items() if k not in {"enum", "default"}})
    if "default" in schema: _check(schema["default"], schema)

def _check(value, schema):
    kind = {dict:"object", list:"array", str:"string", bool:"boolean", int:"integer", float:"number", type(None):"null"}.get(type(value))
    kinds = schema["type"] if type(schema["type"]) is list else [schema["type"]]
    if kind not in kinds and not (kind == "integer" and "number" in kinds): raise ContractViolation("type")
    if "enum" in schema and not any(equal(value,v) for v in schema["enum"]): raise ContractViolation("enum value")
    if kind == "object":
        props = schema.get("properties", {})
        if set(schema.get("required", []))-set(value): raise ContractViolation("missing field")
        if schema.get("additionalProperties") is False and set(value)-set(props): raise ContractViolation("extra field")
        for key, child in value.items():
            if key in props: _check(child, props[key])
    if kind == "array" and "items" in schema:
        for child in value: _check(child, schema["items"])
    if kind in ("number", "integer"):
        if "minimum" in schema and value < schema["minimum"]: raise ContractViolation("minimum")
        if "maximum" in schema and value > schema["maximum"]: raise ContractViolation("maximum")
    if kind in ("string", "array"):
        low, high = ("minLength", "maxLength") if kind == "string" else ("minItems", "maxItems")
        if low in schema and len(value) < schema[low]: raise ContractViolation("minimum length")
        if high in schema and len(value) > schema[high]: raise ContractViolation("maximum length")

def validate_value(value, schema):
    bounded_json(value); schema_contract(schema); _check(value, schema)

def public_output(value, schema):
    validate_value(value, schema)
    def project(v, rule):
        if type(v) is dict and "properties" in rule:
            return {k:project(v[k],s) for k,s in rule["properties"].items() if k in v}
        if type(v) is list and "items" in rule: return [project(x,rule["items"]) for x in v]
        return v
    result = project(value,schema)
    validate_value(result,schema)
    return json.loads(bounded_json(result))

ERRORS = {code:message for code,message in (
    ("invalid_contract","Request does not satisfy its contract."),
    ("unknown_capability","Capability is not registered."),
    ("unsupported_contract","Capability contract is unavailable or unsupported."),
    ("output_rejected","Execution completed but its output was rejected; do not retry automatically."),
    ("permission_denied","Execution was denied."),
    ("execution_failed","Invocation did not produce an accepted result; effects may have occurred."),
    ("audit_unavailable","Durable evidence could not be recorded."),
    ("internal_error","Request failed safely; quote the correlation ID."))}

def failure(code, correlation_id=None):
    return {"ok":False,"error":{"code":code,"message":ERRORS[code],"retryable":False,
        "correlation_id":correlation_id or uuid.uuid4().hex},"execution_authorized":False,"theorem_proven":False}

def capability_definition(entry):
    bounded_json(entry)
    for key in ("skill_id","source"):
        if type(entry.get(key)) is not str or not entry[key].strip(): raise ContractViolation("identity/source")
    for key in ("input_schema","output_schema"): schema_contract(entry.get(key))
    result = {"contract_version":"1.1","skill_id":entry["skill_id"],"source":entry["source"],
        "input_schema":entry["input_schema"],"output_schema":entry["output_schema"],
        "limitations":entry.get("limitations",[]),"authority":"deployment authorization required",
        "error_contract_version":"1.1","automatic_retry":False,"source_attested":False,
        "cost_estimate":entry.get("cost_estimate"),"cost_unit":"registry estimate; not currency","theorem_proven":False}
    result["contract_digest"] = hashlib.sha256(bounded_json(result).encode()).hexdigest()
    return json.loads(bounded_json(result))
