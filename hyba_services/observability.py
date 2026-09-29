"""Tenant-bound metrics, traces, proof cost and evidence export."""

from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Callable, Iterable


class MetricKind(str, Enum):
    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"


class Source(str, Enum):
    PRIME_DB = "PRIME_DB"
    MLA1517 = "MLA1517"
    GUARDIAN = "GUARDIAN"
    WITNESS = "WITNESS"
    SERVICES = "SERVICES"


REQUIRED_METRICS = {
    "primedb.write.total",
    "primedb.read.total",
    "primedb.cassini.failures",
    "primedb.vertex.cursor",
    "primedb.rehydration.count",
    "mla1517.execute.total",
    "mla1517.backend.selected",
    "mla1517.bytes.moved",
    "mla1517.proof.bytes",
    "mla1517.energy.joules",
    "guardian.verdict.total",
    "guardian.verdict.latency_ms",
    "guardian.surface.status",
    "witness.anchor.total",
    "witness.chain.verify.total",
    "witness.tamper.detected",
    "services.flow.events.total",
    "services.ontology.bindings.total",
    "services.agent_fabric.actions.total",
    "services.quality.reports.total",
    "services.evidence.receipts.total",
}
REQUIRED_SPANS = {
    "primedb.put",
    "primedb.get",
    "fold.encode",
    "fold.execute",
    "fold.decode",
    "proof.certify",
    "proof.verify",
    "guardian.conjunction",
    "guardian.mode",
    "guardian.topology",
    "guardian.intelligence",
    "witness.anchor",
    "backend.select",
    "backend.execute",
    "receipt.build",
    "receipt.verify",
}


@dataclass(frozen=True)
class Metric:
    name: str
    kind: MetricKind
    unit: str
    labels: dict[str, str]
    value: int | str
    timestamp: int
    tenant: str | None
    instance: str
    profile: str
    source: Source


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_ns: int
    end_ns: int | None
    attributes: dict[str, Any]
    events: list[dict[str, Any]]
    status: str | None
    tenant: str
    instance: str
    profile: str


class InMemoryTransport:
    def __init__(self):
        self.metrics = []
        self.spans = []

    def publish_metric(self, m):
        self.metrics.append(m)

    def publish_span(self, s):
        self.spans.append(s)

    def search_metrics(self, names: set[str], tenant: str, start: int, end: int):
        return [
            m
            for m in self.metrics
            if m.tenant == tenant and m.name in names and start <= m.timestamp <= end
        ]

    def search_spans(self, names: set[str], tenant: str, start_ns: int, end_ns: int):
        return [
            s
            for s in self.spans
            if s.tenant == tenant and s.name in names and start_ns <= s.start_ns <= end_ns
        ]


class Observability:
    def __init__(self, transport: InMemoryTransport, registered_metrics=(), registered_spans=()):
        self.transport = transport
        self.metrics = REQUIRED_METRICS | set(registered_metrics)
        self.spans = REQUIRED_SPANS | set(registered_spans)

    def emit(self, metric: Metric):
        if metric.name not in self.metrics:
            raise ValueError("unregistered metric")
        if metric.source is not Source.WITNESS and not metric.tenant:
            raise ValueError("tenant required")
        self.transport.publish_metric(metric)

    def start_span(self, name, tenant, instance, profile, parent=None, attributes=None):
        if name not in self.spans:
            raise ValueError("unregistered span")
        return Span(
            parent.trace_id if parent else uuid.uuid4().hex,
            uuid.uuid4().hex,
            parent.span_id if parent else None,
            name,
            time.time_ns(),
            None,
            attributes or {},
            [],
            None,
            tenant,
            instance,
            profile,
        )

    def end_span(self, span: Span, status: str):
        if status not in {"OK", "ERROR"}:
            raise ValueError(status)
        span.end_ns = time.time_ns()
        span.status = status
        self.transport.publish_span(span)

    def query_metrics(self, names: Iterable[str], tenant: str, start: int, end: int):
        names = set(names)
        if not tenant or not names <= self.metrics:
            raise PermissionError("invalid tenant/query")
        return self.transport.search_metrics(names, tenant, start, end)

    def query_spans(self, names: Iterable[str], tenant: str, start_ns: int, end_ns: int):
        names = set(names)
        if not tenant or not names <= self.spans:
            raise PermissionError("invalid tenant/query")
        return self.transport.search_spans(names, tenant, start_ns, end_ns)

    def export_evidence(self, tenant, start, end, key: bytes):
        if len(key) < 32:
            raise ValueError("export key too short")
        metrics = [
            asdict(m)
            for m in self.transport.metrics
            if m.tenant == tenant and start <= m.timestamp <= end
        ]
        spans = [
            asdict(s)
            for s in self.transport.spans
            if s.tenant == tenant and start * 1_000_000_000 <= s.start_ns <= end * 1_000_000_000
        ]
        body = {"tenant": tenant, "window": [start, end], "metrics": metrics, "spans": spans}
        body["signature"] = hmac.new(
            key,
            json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode(),
            hashlib.sha256,
        ).hexdigest()
        return body


@dataclass(frozen=True)
class ProofCostReport:
    object_id: str
    operator: str
    invariants_checked: tuple[str, ...]
    proof_bytes: int
    verify_time_ms: str
    backend: str
    residual_bound: str
    replay_command: tuple[str, ...]


def measure_proof(
    object_id, operator, invariants, backend, certify: Callable[[], Any]
) -> ProofCostReport:
    start = time.perf_counter_ns()
    proof = certify()
    elapsed = time.perf_counter_ns() - start
    raw = (
        json.dumps(asdict(proof), sort_keys=True, default=str).encode()
        if hasattr(proof, "__dataclass_fields__")
        else repr(proof).encode()
    )
    return ProofCostReport(
        object_id,
        operator,
        tuple(invariants),
        len(raw),
        str(elapsed / 1_000_000),
        backend,
        str(proof.residual_bound),
        tuple(proof.replay_command),
    )


@dataclass(frozen=True)
class ResourceTruth:
    math_scale: int
    logical_state_size: int
    physical_bytes_committed: int
    bytes_moved: int
    proof_bytes: int
    checkpoint_count: int
    capacity_mode: str
    performance_claim: str = "measured_only"


def resource_truth(execution) -> ResourceTruth:
    if execution.capacity_mode not in {"bounded_measured", "candidate_exponential_measured_only"}:
        raise ValueError("invalid capacity mode")
    return ResourceTruth(
        execution.scale,
        execution.logical_size,
        execution.physical_bytes,
        execution.bytes_moved,
        execution.proof_bytes,
        execution.checkpoints,
        execution.capacity_mode,
    )


PANELS = {
    "Guardian verdicts by surface": ("guardian.surface.status",),
    "Witness anchoring health": ("witness.anchor.total",),
    "PRIME-DB integrity": ("primedb.cassini.failures",),
    "Execution backend distribution": ("mla1517.backend.selected",),
    "Bytes moved by operation": ("mla1517.bytes.moved",),
    "Proof cost per result": ("mla1517.proof.bytes",),
    "Resource truth": ("mla1517.bytes.moved", "mla1517.energy.joules"),
    "Rehydration events": ("primedb.rehydration.count",),
    "Agent action rate": ("services.agent_fabric.actions.total",),
    "Evidence receipts": ("services.evidence.receipts.total",),
}


def dashboard(profile: str, tenant: str) -> dict:
    if profile not in {"developer", "edge", "enterprise", "sovereign", "hyperscaler"} or not tenant:
        raise ValueError("profile and tenant required")
    return {
        name: {"metrics": metrics, "tenant": tenant, "profile": profile}
        for name, metrics in PANELS.items()
    }
