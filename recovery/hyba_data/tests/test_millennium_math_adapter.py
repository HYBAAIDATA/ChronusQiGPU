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


def test_millennium_api_rejects_parameters_outside_operation_contract():
    api = MillenniumMathsAPI(base_url="https://maths.example.test")
    result = api.run("riemann_primes", {"scale": "quick", "mission_id": "secret"})
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "unsupported_parameter"


def test_millennium_api_rejects_non_object_payload():
    api = MillenniumMathsAPI(base_url="https://maths.example.test")
    result = api.run("aggregate", ["not", "an", "object"])
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "invalid_payload"


def test_millennium_api_validates_aggregate_problem_filter():
    api = MillenniumMathsAPI(base_url="https://maths.example.test")
    result = api.run("aggregate", {"only": "riemann"})
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "invalid_parameter"


def test_millennium_api_does_not_coerce_string_proof_claim_to_true(monkeypatch):
    import json
    import hermes.offerings.millennium_math_adapter as module

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return json.dumps({
                "proof_claim": "true",
                "evidence_class": "FINITE_PROBE",
                "scope": "synthetic",
            }).encode()

    class FakeOpener:
        def open(self, request, timeout):
            return FakeResponse()

    monkeypatch.setattr(module, "build_opener", lambda handler: FakeOpener())
    result = MillenniumMathsAPI(base_url="https://maths.example.test").run("aggregate", {})
    assert result["status"] == "available"
    assert result["proof_claim"] is False
