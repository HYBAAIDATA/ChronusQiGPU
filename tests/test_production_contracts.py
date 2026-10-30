import pytest
from hyba_mcp.production_contracts import ContractViolation, bounded_json, capability_definition, failure, validate_value

@pytest.mark.parametrize("value,schema", [
    (True, {"type":"integer"}),
    (1, {"type":"boolean"}),
    ("abcd", {"type":"string","maxLength":3}),
    ([1,2], {"type":"array","maxItems":1}),
    ({"x":1}, {"type":"object","additionalProperties":False}),
    ({}, {"type":"object","required":["x"]}),
    (1, {"type":"integer","enum":[True]}),
    (1, {"type":"integer","$ref":"anything"}),
    (float("nan"), {"type":"number"}),
])
def test_rejections(value,schema):
    with pytest.raises(ContractViolation): validate_value(value,schema)

def test_nested_validation():
    validate_value({"x":[1,2]}, {"type":"object","properties":{"x":{"type":"array","items":{"type":"integer"}}}})

def test_safe_failure():
    result=failure("internal_error")
    assert result["error"]["retryable"] is False
    assert len(result["error"]["correlation_id"])==32
    assert result["execution_authorized"] is False

def test_capability_digest():
    entry={"skill_id":"test", "source":"fixture", "input_schema":{"type":"object"}, "output_schema":{"type":"object"}}
    first=capability_definition(entry)
    assert first==capability_definition(entry)
    entry["source"]="changed"
    assert first["contract_digest"]!=capability_definition(entry)["contract_digest"]

def test_complexity_limit():
    with pytest.raises(ContractViolation): bounded_json([None]*20001)
