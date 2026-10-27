from hermes.offerings.millennium_math_adapter import MillenniumMathsAPI


def test_millennium_api_is_explicitly_unavailable_without_config():
    api = MillenniumMathsAPI(base_url="")
    result = api.run("aggregate", {"scale": "quick"})
    assert result["status"] == "unavailable"
    assert result["proof_claim"] is False
    assert result["error"]["code"] == "api_not_configured"


def test_millennium_api_rejects_unlisted_operation():
    api = MillenniumMathsAPI(base_url="https://maths.example.test")
    result = api.run("../arbitrary", {})
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "unsupported_operation"


def test_millennium_api_rejects_nonlocal_plain_http():
    api = MillenniumMathsAPI(base_url="http://maths.example.test")
    result = api.run("aggregate", {})
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "api_not_configured"
