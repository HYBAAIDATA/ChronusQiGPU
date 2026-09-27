"""Industry applications.

Each application reads rows the data layer already holds and returns the
calculation. Empty input returns an empty result, not a sample narrative.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from toe.operator_compilers import compile_operator
from kellogg.tensor_ml import fit as tensor_fit
from kellogg.tensor_ml import predict as tensor_predict


def _numeric(rows: list[dict], field: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values.append(float(value))
    return values


def risk_scores(rows: list[dict], score_field: str = "score") -> dict:
    values = _numeric(rows, score_field)
    if not values:
        return {"count": 0, "mean": None, "high": 0}
    high = sum(1 for value in values if value >= 0.7)
    return {"count": len(values), "mean": sum(values) / len(values), "high": high}


def fraud_rate(rows: list[dict], label_field: str = "fraud") -> dict:
    labels = [row.get(label_field) for row in rows if label_field in row]
    flagged = sum(1 for label in labels if label in (1, "1", True))
    return {"count": len(labels), "flagged": flagged, "rate": (flagged / len(labels)) if labels else None}


def regulatory_report(rows: list[dict], jurisdiction_field: str = "jurisdiction", amount_field: str = "amount") -> list[dict]:
    totals: dict[Any, float] = defaultdict(float)
    counts: dict[Any, int] = defaultdict(int)
    for row in rows:
        key = row.get(jurisdiction_field)
        totals[key] += float(row.get(amount_field) or 0.0)
        counts[key] += 1
    return [
        {"jurisdiction": key, "amount": totals[key], "rows": counts[key]}
        for key in sorted(totals, key=lambda item: str(item))
    ]


def customer_360(tables: dict[str, list[dict]], key: str = "customer_id") -> list[dict]:
    merged: dict[Any, dict] = {}
    for entity, rows in tables.items():
        for row in rows:
            if key not in row:
                continue
            bucket = merged.setdefault(row[key], {key: row[key], "entities": []})
            if entity not in bucket["entities"]:
                bucket["entities"].append(entity)
            for field, value in row.items():
                if field == key:
                    continue
                bucket[f"{entity}.{field}"] = value
    return [merged[item] for item in sorted(merged, key=lambda value: str(value))]


def defect_rate(rows: list[dict], defect_field: str = "defect") -> dict:
    return fraud_rate(rows, defect_field) | {"metric": "defect_rate"}


def inventory_position(rows: list[dict], sku_field: str = "sku", qty_field: str = "qty") -> list[dict]:
    totals: dict[Any, float] = defaultdict(float)
    for row in rows:
        totals[row.get(sku_field)] += float(row.get(qty_field) or 0.0)
    return [{"sku": sku, "qty": qty} for sku, qty in sorted(totals.items(), key=lambda item: str(item[0]))]


def energy(rows: list[dict], meter_field: str = "meter", kwh_field: str = "kwh") -> dict:
    values = _numeric(rows, kwh_field)
    by_meter: dict[Any, float] = defaultdict(float)
    for row in rows:
        value = row.get(kwh_field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            by_meter[row.get(meter_field)] += float(value)
    return {
        "total_kwh": sum(values),
        "meters": [{"meter": meter, "kwh": kwh} for meter, kwh in sorted(by_meter.items(), key=lambda item: str(item[0]))],
    }


def maintenance_trend(rows: list[dict], value_field: str = "reading") -> dict:
    """Least-squares slope of a telemetry channel, in row order."""
    values = _numeric(rows, value_field)
    n = len(values)
    if n < 2:
        return {"points": n, "slope": None, "direction": "insufficient"}
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numer = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
    denom = sum((index - x_mean) ** 2 for index in range(n))
    slope = numer / denom if denom else 0.0
    if slope > 1e-9:
        direction = "rising"
    elif slope < -1e-9:
        direction = "falling"
    else:
        direction = "flat"
    return {"points": n, "slope": slope, "direction": direction}


def fraud_detection_lift(rows: list[dict], feature: str = "amount", target: str = "fraud") -> dict:
    """Precision of exact_linear against a flag-every-row baseline."""
    labels = [int(row[target]) for row in rows]
    baseline = sum(labels) / len(labels)
    matrix = [[float(row[feature])] for row in rows]
    model = tensor_fit("exact_linear", matrix, labels)
    predicted = [int(value) for value in tensor_predict(model, matrix)]
    flagged = [(label, pred) for label, pred in zip(labels, predicted) if pred == 1]
    precision = (sum(label for label, _ in flagged) / len(flagged)) if flagged else 0.0
    improvement = ((precision - baseline) / baseline) if baseline else None
    return {
        "baseline_precision": baseline,
        "model_precision": precision,
        "improvement": improvement,
    }


def sensor_batch(rows: list[dict], value_field: str = "reading") -> dict:
    compiled = compile_operator({"events": rows})
    trend = maintenance_trend(rows, value_field)
    return {
        "operator_digest": compiled.input_digest,
        "operator": compiled.operator,
        "direction": trend["direction"],
        "slope": trend["slope"],
        "channel": "opcua",
    }


PACKS = {
    "financial_services": ("risk", "fraud", "regulatory", "customer_360"),
    "healthcare": ("risk", "customer_360"),
    "manufacturing": ("maintenance", "quality", "inventory", "energy", "sensor"),
}
