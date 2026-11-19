"""Deterministic arithmetic fixtures, not customer or production telemetry."""
import copy
import json
from fractions import Fraction

import pytest

from chronus.service.ipmvp import digest, issue_report, verify_report


def fixture_inputs():
    boundary = "TEST-ONLY tenant"
    base = ["2026-01-01", "2026-02-01"]
    report = ["2026-02-01", "2026-03-01"]

    def artifact(kind, period, lines):
        payload = {"kind": kind, "boundary": boundary, "period": period,
                   "currency": "GBP", "source_reference": "arithmetic test fixture",
                   "lines": lines}
        return {"payload": payload, "sha256": digest(payload)}

    return {"measurement_boundary": boundary, "currency": "GBP",
            "baseline_period": base, "reporting_period": report,
            "contract_version": "hermiten-net-avoided/1", "option": "C",
            "artifacts": {
                "baseline": artifact("customer_invoices", base, [
                    {"id": "a", "minor_units": 101}, {"id": "b", "minor_units": 200}]),
                "actual": artifact("tenant_metered_spend", report, [
                    {"id": "c", "minor_units": 102}]),
                "adjustments": artifact("adjustments", report, [
                    {"id": "d", "minor_units": -4, "reason": "test correction"}]),
            }}


def test_recompute_from_certificate_inputs_alone():
    certificate = json.loads(json.dumps(issue_report(fixture_inputs())))
    inputs = certificate["content"]["inputs"]
    artifacts = inputs["artifacts"]
    # Independent arithmetic; do not call the implementation's recompute.
    baseline, actual, adjustment = [
        sum(row["minor_units"] for row in artifacts[key]["payload"]["lines"])
        for key in ("baseline", "actual", "adjustments")]
    counterfactual = baseline + adjustment
    avoided = max(0, counterfactual - actual)
    expected = dict(baseline_spend=baseline, adjustments=adjustment,
                    counterfactual_spend=counterfactual, actual_spend=actual,
                    net_avoided=avoided, value_share=Fraction(avoided, 4),
                    customer_retained=Fraction(avoided * 3, 4))
    assert verify_report(certificate) == {k: str(Fraction(v)) for k, v in expected.items()}
    assert certificate["content"]["lines"] == {k: str(Fraction(v)) for k, v in expected.items()}


@pytest.mark.parametrize("mutation", ["amount", "tenant", "line", "option", "missing"])
def test_tampering_or_missing_input_fails_closed(mutation):
    cert = issue_report(fixture_inputs())
    body = cert["content"]
    inputs = body["inputs"]
    artifacts = inputs["artifacts"]
    if mutation == "amount":
        artifacts["actual"]["payload"]["lines"][0]["minor_units"] += 1
    elif mutation == "tenant":
        p = artifacts["actual"]["payload"]
        p["boundary"] = "other tenant"
        artifacts["actual"]["sha256"] = digest(p)
    elif mutation == "line":
        body["lines"]["value_share"] = "0"
    elif mutation == "option":
        inputs["option"] = "D"
    else:
        del artifacts["baseline"]
    cert["sha256"] = digest(body)
    with pytest.raises(ValueError):
        verify_report(cert)


def test_no_avoided_cost_means_no_value_share():
    inputs = copy.deepcopy(fixture_inputs())
    actual = inputs["artifacts"]["actual"]
    actual["payload"]["lines"][0]["minor_units"] = 999
    actual["sha256"] = digest(actual["payload"])
    lines = verify_report(issue_report(inputs))
    assert lines["net_avoided"] == lines["value_share"] == lines["customer_retained"] == "0"
