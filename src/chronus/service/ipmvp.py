"""Offline Hermiten M&V report arithmetic; no billing side effects.

Option C-style cost adaptation only. A digest establishes integrity, not
customer authorship, actual payment, or IPMVP certification.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from fractions import Fraction

SCHEMA = "chronus.hermiten.mv/1"
CONTRACT = "hermiten-net-avoided/1"
SHARE = Fraction(1, 4)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty text required")
    return value


def _period(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("period requires start and exclusive end")
    start, end = (date.fromisoformat(_text(x)) for x in value)
    if start >= end:
        raise ValueError("invalid period")
    return start, end


def _amount(value, signed=False):
    if type(value) is not int or (value < 0 and not signed):
        raise ValueError("integer minor currency units required")
    return value


def _artifact(artifact, kind, boundary, period, currency):
    payload = artifact["payload"]
    if artifact["sha256"] != digest(payload):
        raise ValueError("input digest mismatch")
    if (payload["kind"], payload["boundary"], payload["period"], payload["currency"]) != (
            kind, boundary, period, currency):
        raise ValueError("input scope mismatch")
    _text(payload["source_reference"])
    rows = payload["lines"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing source lines")
    seen = set()
    total = 0
    for row in rows:
        key = _text(row["id"])
        if key in seen:
            raise ValueError("duplicate source line")
        seen.add(key)
        total += _amount(row["minor_units"], kind == "adjustments")
        if kind == "adjustments":
            _text(row["reason"])
    return total


def recompute(inputs):
    """Calculate every monetary line from embedded, digest-bound inputs."""
    boundary = _text(inputs["measurement_boundary"])
    currency = _text(inputs["currency"])
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
        raise ValueError("currency code required")
    base, report = inputs["baseline_period"], inputs["reporting_period"]
    if _period(base)[1] > _period(report)[0]:
        raise ValueError("overlapping or reversed periods")
    if inputs["contract_version"] != CONTRACT or inputs["option"] != "C":
        raise ValueError("unsupported contract or measurement option")
    artifacts = inputs["artifacts"]
    if set(artifacts) != {"baseline", "actual", "adjustments"}:
        raise ValueError("unexpected or missing input artifact")
    baseline = _artifact(artifacts["baseline"], "customer_invoices", boundary, base, currency)
    actual = _artifact(artifacts["actual"], "tenant_metered_spend", boundary, report, currency)
    adjustments = _artifact(artifacts["adjustments"], "adjustments", boundary, report, currency)
    counterfactual = baseline + adjustments
    if counterfactual < 0:
        raise ValueError("negative adjusted baseline")
    avoided = max(0, counterfactual - actual)
    fee = avoided * SHARE
    # Fractions are exact minor units; payment rounding is not authorised here.
    return {key: str(Fraction(value)) for key, value in {
        "baseline_spend": baseline, "adjustments": adjustments,
        "counterfactual_spend": counterfactual, "actual_spend": actual,
        "net_avoided": avoided, "value_share": fee,
        "customer_retained": avoided - fee,
    }.items()}


def issue_report(inputs):
    """Return a portable report; it is not a signed invoice."""
    # Detach from caller-owned mutable structures.
    inputs = json.loads(json.dumps(inputs, allow_nan=False))
    body = {"schema": SCHEMA, "inputs": inputs, "lines": recompute(inputs)}
    return {"content": body, "sha256": digest(body)}


def verify_report(report):
    body = report["content"]
    if report["sha256"] != digest(body) or body["schema"] != SCHEMA:
        raise ValueError("report integrity or schema mismatch")
    if recompute(body["inputs"]) != body["lines"]:
        raise ValueError("settlement lines mismatch")
    return body["lines"]
