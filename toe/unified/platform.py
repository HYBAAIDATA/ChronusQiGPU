"""Unified analytics platform.

One object owns connectors, the data layer, tensor models, questions,
operations, the cost model, and the scholarship ledger.
"""

from __future__ import annotations

from dataclasses import dataclass

from toe.operator_compilers import compile_operator

from . import industries
from .adaptive import AdaptiveInterface
from .bi import Inquiry, dashboard
from .catalog import CATALOG, DISPLACED_CLASSES, search
from .connectors import BoundConnector, bind
from .data_layer import Policy, UnifiedDataLayer
from .economics import CostBaseline, PlatformCost, assess, document_fortune500_scenario, financial_services_case
from .impact import ScholarshipLedger
from .intelligence import ModelRegistry
from .monitor import HealthMonitor
from .operations import HealAction, Operations
from .optimizer import plan as plan_query
from .patents import PatentRegister
from .productivity import ProductivityMeter
from .risks import RiskRegister
from .security import SecurityModel
from .consciousness import ConsciousnessState


class GateUnavailable(RuntimeError):
    """A gate was read before its measured source existed."""


@dataclass(frozen=True)
class Gate:
    phase: str
    name: str
    passed: bool
    measured: object
    target: object


class UnifiedAnalyticsPlatform:
    def __init__(self, *, allocation_rate: float = 0.0, max_workers: int = 8) -> None:
        self.data = UnifiedDataLayer()
        self.models = ModelRegistry()
        self.adaptive = AdaptiveInterface()
        self.operations = Operations(max_workers=max_workers)
        self.ledger = ScholarshipLedger(allocation_rate=allocation_rate)
        self.consciousness = ConsciousnessState()
        self.security = SecurityModel()
        self.productivity = ProductivityMeter()
        self.patents = PatentRegister()
        self.risks = RiskRegister()
        self.monitor = HealthMonitor(self._monitor_tick)
        self.inquiry = Inquiry(self.data, self.models, document_fortune500_scenario)
        self._connections: dict[str, BoundConnector] = {}
        self._retired: set[str] = set()
        self._receipts: list = []
        self._drift: tuple | None = None
        self.drift_retrains = 0
        self._processing_reduction: float | None = None
        self._health_seq = 0
        self.started = False
        self._last_roi = None

    def start(self) -> dict:
        self.started = True
        return {
            "started": True,
            "connectors_available": len(CATALOG),
            "displaced_classes": list(DISPLACED_CLASSES),
        }

    def catalog(self, **filters) -> tuple:
        return search(**filters)

    def connect(self, connector_id: str, credentials: dict) -> BoundConnector:
        self.security.authorize("connect")
        bound = bind(connector_id, credentials)
        self._connections[bound.spec.id] = bound
        self.operations.note_probe(True)
        return bound

    def connections(self) -> dict:
        return dict(self._connections)

    def operations_note(self, ok: bool) -> None:
        self.operations.note_probe(ok)

    def entities(self) -> list[str]:
        return sorted({record.entity for record in self.data._records.values()})

    def quality(self, entity: str):
        return self.data.quality(entity)

    def null_policy(self, entity: str) -> float:
        return self.data.policy_for(entity).max_null_rate

    def batches(self, entity: str) -> list[str]:
        return sorted({record.batch_id for record in self.data._records.values() if record.entity == entity})

    def quarantine(self, batch_id: str) -> int:
        return self.data.quarantine(batch_id)

    def release(self, batch_id: str) -> int:
        return self.data.release(batch_id)

    def batch_null_rate(self, batch_id: str) -> float:
        return self.data.batch_null_rate(batch_id)

    def integrate(self, connector_id: str, entity: str, *, mode: str = "batch") -> dict:
        bound = self._connections.get(connector_id)
        if bound is None:
            raise KeyError(f"{connector_id} is not connected")
        extracted = bound.extract(entity, mode)
        compiled = compile_operator({"events": list(extracted.rows)})
        receipt = self.data.ingest(
            connector_id,
            entity,
            list(extracted.rows),
            operator_digest=compiled.input_digest,
            operator_kind=compiled.kind,
        )
        self._receipts.append(receipt)
        self.operations.queue_depth = max(0, self.operations.queue_depth - len(extracted.rows))
        return {
            "receipt": receipt,
            "operator": compiled.operator,
            "truth_class": compiled.truth_class,
        }

    def ingest_rows(self, source: str, entity: str, rows: list[dict]) -> dict:
        self.security.authorize("ingest")
        compiled = compile_operator({"events": rows})
        receipt = self.data.ingest(
            source,
            entity,
            rows,
            operator_digest=compiled.input_digest,
            operator_kind=compiled.kind,
        )
        self._receipts.append(receipt)
        return {"receipt": receipt, "operator": compiled.operator, "truth_class": compiled.truth_class}

    def export_records(self) -> list[dict]:
        self.security.authorize("export")
        return self.data.snapshot()

    def import_records(self, rows: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            grouped.setdefault((row["source"], row["entity"]), []).append(row["payload"])
        return [self.ingest_rows(source, entity, payloads) for (source, entity), payloads in sorted(grouped.items())]

    def govern(self, entity: str, classification: str, retention_days: int, owner: str, max_null_rate: float = 0.2) -> Policy:
        return self.data.set_policy(
            Policy(entity, classification, retention_days, owner, max_null_rate)
        )

    def train(self, name: str, rows: list[dict], features: list[str], target: str):
        self.security.authorize("train")
        return self.models.train(name, rows, features, target)

    def retrain(self, name: str, rows: list[dict], eval_rows: list[dict] | None = None):
        return self.models.retrain(name, rows, eval_rows)

    def predict(self, name: str, rows: list[dict]) -> list[int]:
        return self.models.predict(name, rows)

    def transfer(self, name: str, rows: list[dict], features: list[str]) -> dict:
        return self.models.predict_aligned(name, rows, features)

    def ask(self, question: str) -> dict:
        self.security.authorize("ask")
        if question.strip().lower() in ("health", "status"):
            report = self.health()
            return {"question": question, "kind": "health", "rows": [report], "text": "platform health"}
        return self.inquiry.ask(question).as_dict()

    def feedback(self, user: str, widget: str, depth: int = 1, rating: float | None = None):
        profile = self.adaptive.observe(user, widget, depth)
        if rating is not None:
            self.operations.note_rating(rating)
        return profile

    def dashboard_for(self, user: str, name: str, widgets: list[dict]) -> dict:
        profile = self.adaptive.profile(user)
        spec = dashboard(name, widgets, profile.widget_rank)
        spec["density"] = profile.preferred_density
        return spec

    def health(self) -> dict:
        self._health_seq += 1
        quality = self.data.quality()
        return {
            "sequence": self._health_seq,
            "started": self.started,
            "connectors_bound": len(self._connections),
            "connectors_available": len(CATALOG),
            "classes_bound": sorted({bound.spec.category for bound in self._connections.values()}),
            "classes_required": list(DISPLACED_CLASSES),
            "rows": quality.rows,
            "null_rate": quality.null_rate,
            "availability": self.operations.availability(),
            "satisfaction": self.operations.satisfaction(),
            "models": list(self.models.names()),
            "unplanned_downtime": self.operations.unplanned_downtime,
        }

    def require_gate(self, name: str) -> Gate:
        gate = next(item for item in self.phases() if item.name == name)
        if gate.measured is None:
            raise GateUnavailable(f"{name} has no measured source")
        return gate

    def heal(self) -> list[HealAction]:
        self.security.authorize("heal")
        return self.operations.heal(self)

    def reload(self, connector_id: str, credentials: dict) -> BoundConnector:
        self.security.authorize("reload")
        if connector_id not in self._connections:
            raise KeyError(f"{connector_id} is not connected")
        bound = bind(connector_id, credentials)
        self._connections[connector_id] = bound
        return bound

    def _monitor_tick(self) -> None:
        self.operations.heal(self)
        self._retrain_if_drifted()

    def watch(self, name: str, rows: list[dict]) -> None:
        self._drift = (name, list(rows))

    def _retrain_if_drifted(self) -> None:
        if self._drift is None:
            return
        name, rows = self._drift
        record = self.models.get(name)
        predicted = self.models.predict(name, rows)
        actual = [int(row[record.target]) for row in rows]
        accuracy = sum(int(left) == right for left, right in zip(predicted, actual)) / len(actual)
        if accuracy < 0.5:
            self.models.retrain(name, rows)
            self.drift_retrains += 1
            self._drift = None

    def benchmark_processing(self, entities: int = 100, per_entity: int = 20) -> dict:
        for index in range(entities):
            self.ingest_rows("benchmark", f"entity{index}", [{"n": value} for value in range(per_entity)])
        self.data.index_visits = 0
        self.data.scan_visits = 0
        self.data.rows("entity0")
        self.data.scan_rows("entity0")
        ratio = self.data.scan_visits / max(self.data.index_visits, 1)
        reduction = 1.0 - (self.data.index_visits / self.data.scan_visits)
        self._processing_reduction = reduction
        return {
            "index_visits": self.data.index_visits,
            "scan_visits": self.data.scan_visits,
            "ratio": ratio,
            "reduction": reduction,
        }

    def optimize(self, rows: list[dict], filters: list[tuple]) -> dict:
        return plan_query(rows, filters)

    def file_patent(self, title: str) -> int:
        return self.patents.file(title)

    def case_financial_services(self):
        result = financial_services_case()
        self._last_roi = result
        return result

    def scale(self):
        return self.operations.scale()

    def displacement(self) -> dict:
        covered = {}
        for bound in self._connections.values():
            covered.setdefault(bound.spec.category, []).append(bound.spec.id)
        return {
            "required": list(DISPLACED_CLASSES),
            "covered": sorted(covered),
            "missing": [name for name in DISPLACED_CLASSES if name not in covered],
            "bound": covered,
        }

    def retire(self, connector_id: str) -> None:
        self._retired.add(connector_id)

    def economics(self, baseline: CostBaseline, platform_cost: PlatformCost, **kwargs):
        result = assess(baseline, platform_cost, **kwargs)
        self._last_roi = result
        return result

    def scenario(self) -> dict:
        return document_fortune500_scenario()

    def recognize_value(self, amount: float, source: str):
        return self.ledger.recognize(amount, source)

    def industry(self, name: str) -> dict:
        if name not in industries.PACKS:
            raise KeyError(f"unknown industry pack {name}")
        connectors = search(industry=name)
        return {
            "industry": name,
            "applications": industries.PACKS[name],
            "connectors": len(connectors),
        }

    def run_application(self, application: str, **payload):
        functions = {
            "risk": industries.risk_scores,
            "fraud": industries.fraud_rate,
            "regulatory": industries.regulatory_report,
            "customer_360": industries.customer_360,
            "quality": industries.defect_rate,
            "inventory": industries.inventory_position,
            "energy": industries.energy,
            "maintenance": industries.maintenance_trend,
            "sensor": industries.sensor_batch,
            "fraud_lift": industries.fraud_detection_lift,
        }
        if application not in functions:
            raise KeyError(f"unknown application {application}")
        if application == "customer_360":
            return functions[application](payload["tables"], payload.get("key", "customer_id"))
        if application == "sensor":
            return functions[application](payload["rows"], payload.get("value_field", "reading"))
        if application == "fraud_lift":
            return functions[application](payload["rows"], payload.get("feature", "amount"), payload.get("target", "fraud"))
        return functions[application](payload["rows"], *payload.get("args", ()))

    def phases(self) -> list[Gate]:
        health = self.health()
        classes = len(health["classes_bound"])
        satisfaction = health["satisfaction"]
        savings = None if self._last_roi is None else self._last_roi.annual_savings
        roi = None if self._last_roi is None else self._last_roi.roi_3y
        gates = [
            Gate("foundation", "started", self.started, self.started, True),
            Gate("foundation", "connectors_integrated", len(self._connections) >= 50, len(self._connections), 50),
            Gate("foundation", "heal_armed", self.operations.armed, self.operations.armed, True),
            Gate("foundation", "downtime", self.operations.unplanned_downtime == 0, self.operations.unplanned_downtime, 0),
            Gate("expansion", "classes_in_use", classes >= 8, classes, 8),
            Gate("expansion", "enterprise_systems", len(self._connections) >= 500, len(self._connections), 500),
            Gate("expansion", "model_deployed", bool(self.models.names()), list(self.models.names()), "one live model"),
            Gate("expansion", "self_serve", bool(self.adaptive._actions), len(self.adaptive._actions), "one user profile"),
            Gate("optimization", "legacy_retired", len(self._retired) >= 1, sorted(self._retired), "one retired source"),
            Gate("optimization", "availability", health["availability"] >= 0.999, health["availability"], 0.999),
            Gate("optimization", "satisfaction", satisfaction is not None and satisfaction >= 0.95, satisfaction, 0.95),
            Gate("optimization", "processing_reduction", self._processing_reduction is not None and self._processing_reduction >= 0.90, self._processing_reduction, 0.90),
            Gate("optimization", "roi_positive", savings is not None and savings > 0, savings, "> 0"),
            Gate("optimization", "roi_400", roi is not None and roi >= 4.0, roi, 4.0),
            Gate("innovation", "model_retained", any(len(items) >= 1 for items in self.models._history.values()), len(self.models._history), "registry history"),
            Gate("innovation", "scholarship_configured", self.ledger.allocation_rate > 0, self.ledger.allocation_rate, "> 0"),
            Gate("innovation", "patents", self.patents.count() >= 10, self.patents.count(), 10),
        ]
        return gates
