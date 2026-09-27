"""Business intelligence: natural-language questions, query plans, dashboards."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .data_layer import UnifiedDataLayer


_SHOW = re.compile(
    r"^show\s+(?P<metric>[a-z_][a-z0-9_]*)\s+by\s+(?P<dimension>[a-z_][a-z0-9_]*)\s+from\s+(?P<entity>[a-z_][a-z0-9_]*)(?:\s+where\s+(?P<where>.+))?$",
    re.I,
)
_COUNT = re.compile(
    r"^count\s+(?P<entity>[a-z_][a-z0-9_]*)(?:\s+where\s+(?P<where>.+))?$",
    re.I,
)
_DRIVES = re.compile(r"^what\s+drives\s+(?P<model>[a-z_][a-z0-9_]*)$", re.I)
_QUALITY = re.compile(r"^quality(?:\s+of\s+(?P<entity>[a-z_][a-z0-9_]*))?$", re.I)
_WHERE = re.compile(
    r"^(?P<field>[a-z_][a-z0-9_]*)\s*(?P<op>>=|<=|!=|=|>|<)\s*(?P<value>.+)$",
    re.I,
)


class QueryError(ValueError):
    pass


@dataclass(frozen=True)
class Query:
    kind: str
    entity: str | None = None
    metric: str | None = None
    dimension: str | None = None
    model: str | None = None
    where: tuple[tuple[str, str, Any], ...] = ()


def _value(raw: str) -> Any:
    text = raw.strip().strip("'\"")
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _where(clause: str | None) -> tuple[tuple[str, str, Any], ...]:
    if not clause:
        return ()
    match = _WHERE.match(clause.strip())
    if not match:
        raise QueryError(f"unsupported filter: {clause}")
    return ((match.group("field").lower(), match.group("op"), _value(match.group("value"))),)


def parse(question: str) -> Query:
    text = " ".join(question.strip().split())
    if not text:
        raise QueryError("empty question")
    lowered = text.lower()
    if lowered in ("health", "status"):
        return Query("health")
    if lowered in ("roi", "savings"):
        return Query("roi")
    match = _SHOW.match(text)
    if match:
        return Query(
            "aggregate",
            entity=match.group("entity").lower(),
            metric=match.group("metric").lower(),
            dimension=match.group("dimension").lower(),
            where=_where(match.group("where")),
        )
    match = _COUNT.match(text)
    if match:
        return Query("aggregate", entity=match.group("entity").lower(), metric="count", where=_where(match.group("where")))
    match = _DRIVES.match(text)
    if match:
        return Query("drivers", model=match.group("model").lower())
    match = _QUALITY.match(text)
    if match:
        entity = match.group("entity")
        return Query("quality", entity=entity.lower() if entity else None)
    raise QueryError(
        "unsupported question; try 'show revenue by region from accounts where region = emea'"
    )


def optimize(query: Query, importances: list[dict] | None = None) -> dict:
    """Order filters by measured feature importance when a model has them."""
    weights = {item["feature"]: item["importance"] for item in (importances or [])}
    ranked = tuple(sorted(query.where, key=lambda item: (-weights.get(item[0], 0.0), item[0])))
    return {
        "kind": query.kind,
        "filters": [{"field": field, "op": op, "value": value, "importance": weights.get(field, 0.0)} for field, op, value in ranked],
        "ordered_by": "feature_importance" if weights else "source_order",
    }


@dataclass
class Answer:
    question: str
    query: Query
    plan: dict
    rows: list
    text: str

    def as_dict(self) -> dict:
        return {
            "question": self.question,
            "kind": self.query.kind,
            "plan": self.plan,
            "rows": self.rows,
            "text": self.text,
        }


class Inquiry:
    def __init__(self, data: UnifiedDataLayer, models: Any, economics: Any) -> None:
        self.data = data
        self.models = models
        self.economics = economics

    def ask(self, question: str) -> Answer:
        query = parse(question)
        importances = []
        if query.model and query.model in self.models.names():
            importances = self.models.importances(query.model)
        plan = optimize(query, importances)
        if query.kind == "aggregate":
            rows = self.data.aggregate(query.entity, query.metric, query.dimension, query.where)
            text = f"{len(rows)} group(s) from {query.entity}"
        elif query.kind == "drivers":
            rows = self.models.importances(query.model)
            text = f"{len(rows)} features in {query.model}"
        elif query.kind == "quality":
            report = self.data.quality(query.entity)
            rows = [{"entity": report.entity, "rows": report.rows, "null_rate": report.null_rate, "quarantined": report.quarantined}]
            text = f"null rate {report.null_rate:.4f}"
        elif query.kind == "roi":
            scenario = self.economics()
            rows = [scenario["low"], scenario["high"]]
            text = "document fortune 500 scenario, low and high"
        else:
            rows = []
            text = "health is reported by operations"
        return Answer(question, query, plan, rows, text)


def dashboard(name: str, widgets: list[dict], profile_rank: tuple[str, ...] = ()) -> dict:
    order = {widget_name: index for index, widget_name in enumerate(profile_rank)}
    ranked = sorted(widgets, key=lambda widget: (order.get(widget["id"], len(order)), widget["id"]))
    return {"name": name, "widgets": ranked, "ordered_by": "user_profile" if profile_rank else "declared"}
