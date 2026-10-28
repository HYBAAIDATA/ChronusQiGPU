"""Opt-in, advisory Salamander tools for the canonical HYBA MCP server."""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import time
from collections import defaultdict, deque
from dataclasses import asdict
from threading import RLock
from typing import Any, Mapping

from .skills.common import json_safe, validate_schema

MAX_AUTHORITY_LEASE_SECONDS = 300.0
OPTIMISE_COOLDOWN_SECONDS = 30.0
OPTIMISE_WINDOW_SECONDS = 300.0
OPTIMISE_WINDOW_CALLS = 3
OPTIMISE_CAPABILITY = "salamander.optimise"

_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "vram_utilization": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "error_rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "throughput": {"type": "number", "minimum": 0.0, "maximum": 1e15},
    },
    "required": ["vram_utilization", "error_rate", "throughput"],
    "additionalProperties": False,
}

_COMMON_PROPERTIES = {
    "enabled": {"type": "boolean"},
    "metrics": _METRICS_SCHEMA,
    "baseline_throughput": {"type": "number", "minimum": 0.000001, "maximum": 1e15},
}

SALAMANDER_TOOLS: dict[str, dict[str, Any]] = {
    "salamander_diagnose": {
        "description": (
            "Opt-in, read-only Salamander homeostasis check; reports only threshold breaches."
        ),
        "inputSchema": {
            "type": "object",
            "properties": _COMMON_PROPERTIES,
            "required": ["enabled", "metrics", "baseline_throughput"],
            "additionalProperties": False,
        },
    },
    "salamander_propose": {
        "description": "Opt-in Salamander repair proposal; never applies or executes the proposal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "fault_type": {"type": "string", "minLength": 1, "maxLength": 64},
                "details": {
                    "type": "object",
                    "properties": {"component": {"type": "string", "maxLength": 256}},
                    "additionalProperties": False,
                },
            },
            "required": ["enabled", "fault_type", "details"],
            "additionalProperties": False,
        },
    },
    "salamander_optimise": {
        "description": (
            "Opt-in, one-step golden-ratio recommendation. Requires an unexpired "
            "verify_authority lease and explicit budgets; never applies changes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **_COMMON_PROPERTIES,
                "lease_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "optimization": {
                    "type": "object",
                    "properties": {
                        "parameter": {"type": "string", "minLength": 1, "maxLength": 64},
                        "previous_value": {"type": "number"},
                        "current_value": {"type": "number"},
                        "minimum": {"type": "number"},
                        "maximum": {"type": "number"},
                        "previous_cuop": {"type": "number", "minimum": 0.0},
                        "current_cuop": {"type": "number", "minimum": 0.0},
                    },
                    "required": [
                        "parameter",
                        "previous_value",
                        "current_value",
                        "minimum",
                        "maximum",
                        "previous_cuop",
                        "current_cuop",
                    ],
                    "additionalProperties": False,
                },
                "budget": {
                    "type": "object",
                    "properties": {
                        "max_steps": {"type": "integer", "minimum": 1, "maximum": 1},
                        "max_seconds": {"type": "number", "minimum": 0.001, "maximum": 1.0},
                    },
                    "required": ["max_steps", "max_seconds"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "enabled",
                "metrics",
                "baseline_throughput",
                "lease_id",
                "optimization",
                "budget",
            ],
            "additionalProperties": False,
        },
    },
}


class SalamanderTools:
    """Keep MCP-visible Salamander operations opt-in, bounded, and non-actuating."""

    def __init__(self, control_plane: Any, *, enabled: bool = False) -> None:
        self.control_plane = control_plane
        self.enabled = enabled is True
        self._lock = RLock()
        self._leases: dict[str, dict[str, Any]] = {}
        self._optimise_times: dict[str, deque[float]] = defaultdict(deque)
        self._monitor: Any = None
        self._repair_engine: Any = None
        self._circuit_breaker: Any = None

    def issue_authority_lease(
        self,
        identity: str,
        arguments: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Create a short-lived, process-local lease only after AL HARAS approval."""
        if not self.enabled or not identity or arguments.get("capability") != OPTIMISE_CAPABILITY:
            return None
        duration = arguments.get("lease_duration")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or (isinstance(duration, float) and not math.isfinite(duration))
            or duration <= 0
            or duration > MAX_AUTHORITY_LEASE_SECONDS
        ):
            return None
        authorized = result.get("ok") is True and result.get("result", {}).get("allowed") is True
        if not authorized or not self._audit_ready():
            return None
        authority_record = result["result"].get("audit_record", {})
        issuer_expiry = (
            authority_record.get("expires_at") if isinstance(authority_record, Mapping) else None
        )
        if isinstance(issuer_expiry, (int, float)) and not isinstance(issuer_expiry, bool):
            if isinstance(issuer_expiry, float) and not math.isfinite(issuer_expiry):
                return None
            now_wall = time.time()
            if issuer_expiry <= now_wall + duration:
                duration = float(issuer_expiry) - now_wall
        if duration <= 0:
            return None

        lease_id = secrets.token_urlsafe(32)
        expires_mono = time.monotonic() + duration
        with self._lock:
            self._leases[lease_id] = {
                "identity": identity,
                "capability": OPTIMISE_CAPABILITY,
                "expires_mono": expires_mono,
            }
        return {
            "lease_id": lease_id,
            "capability": OPTIMISE_CAPABILITY,
            "expires_at": time.time() + duration,
        }

    def execute(self, name: str, arguments: Mapping[str, Any], identity: str) -> dict[str, Any]:
        if name not in SALAMANDER_TOOLS:
            raise ValueError(f"Unknown Salamander MCP tool: {name}")
        self._validate_numeric_bounds(arguments)
        errors = validate_schema(arguments, SALAMANDER_TOOLS[name]["inputSchema"])
        if errors:
            raise ValueError("; ".join(errors))
        self._validate_string_limits(name, arguments)
        if arguments["enabled"] is not True or not self.enabled:
            return {"enabled": False, "status": "disabled", "theorem_proven": False}
        if name == "salamander_diagnose":
            return self._diagnose(arguments["metrics"], arguments["baseline_throughput"])
        if name == "salamander_propose":
            return self._propose(arguments["fault_type"], arguments["details"])
        return self._optimise(arguments, identity)

    @staticmethod
    def _validate_numeric_bounds(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                SalamanderTools._validate_numeric_bounds(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                SalamanderTools._validate_numeric_bounds(item)
        elif isinstance(value, int) and not isinstance(value, bool) and abs(value) > 1e15:
            raise ValueError("numeric arguments exceed the bounded Salamander input range")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric arguments must be finite")

    @staticmethod
    def _validate_string_limits(name: str, arguments: Mapping[str, Any]) -> None:
        if name == "salamander_propose" and len(arguments["fault_type"]) > 64:
            raise ValueError("fault_type exceeds the maximum length")
        if name == "salamander_propose" and len(arguments["details"].get("component", "")) > 256:
            raise ValueError("component exceeds the maximum length")
        if name == "salamander_optimise":
            if len(arguments["lease_id"]) > 128:
                raise ValueError("lease_id exceeds the maximum length")
            if len(arguments["optimization"]["parameter"]) > 64:
                raise ValueError("parameter exceeds the maximum length")

    def _diagnose(self, metrics: Mapping[str, Any], baseline_throughput: float) -> dict[str, Any]:
        self._validate_metrics(metrics, baseline_throughput)
        monitor = self._get_monitor()
        monitor.set_baseline({"throughput": baseline_throughput})
        report = monitor.check(dict(metrics)).as_dict()
        return {
            "enabled": True,
            "status": "breach" if not report["healthy"] else "quiet",
            "triggered": not report["healthy"],
            "report": report,
            "evidence_class": "caller_supplied_unverified_telemetry",
            "theorem_proven": False,
        }

    def _propose(self, fault_type: str, details: Mapping[str, Any]) -> dict[str, Any]:
        engine = self._get_repair_engine()
        proposal = engine.diagnose(fault_type, dict(details))
        proposal.applied = False
        return {
            "enabled": True,
            "proposal": asdict(proposal),
            "executed": False,
            "applied": False,
            "risk_score": 0.0 if proposal.is_safe else 1.0,
            "risk_measure": "categorical safety proxy; not a calibrated probability",
            "theorem_proven": False,
        }

    def _optimise(self, arguments: Mapping[str, Any], identity: str) -> dict[str, Any]:
        metrics = arguments["metrics"]
        baseline = arguments["baseline_throughput"]
        optimisation = arguments["optimization"]
        budget = arguments["budget"]
        self._validate_metrics(metrics, baseline)
        self._validate_optimisation(optimisation, budget)
        lease_id = arguments["lease_id"]
        input_digest = hashlib.sha256(
            json.dumps(
                {key: value for key, value in arguments.items() if key != "lease_id"},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        if not identity:
            return self._audited_result(
                "denied", "trusted_identity_unavailable", identity, input_digest
            )
        if not self._audit_ready():
            return {"enabled": True, "status": "denied", "reason": "durable_audit_unavailable"}
        try:
            self.control_plane.audit.append(
                {
                    "event": "salamander_optimise_requested",
                    "identity": identity,
                    "lease_sha256": hashlib.sha256(lease_id.encode("utf-8")).hexdigest(),
                    "inputs_sha256": input_digest,
                    "budget": dict(budget),
                    "timestamp": time.time(),
                }
            )
        except Exception:
            return {"enabled": True, "status": "denied", "reason": "audit_persistence_failed"}

        lease_error = self._consume_lease(lease_id, identity)
        if lease_error:
            return self._audited_result("denied", lease_error, identity, input_digest)

        report = self._homeostasis_report(metrics, baseline)
        if report["healthy"]:
            return self._audited_result(
                "quiet", "no_homeostasis_breach", identity, input_digest, report=report
            )
        if report["action"] == "circuit_break":
            self._get_circuit_breaker().record_failure()
            return self._audited_result(
                "blocked", "error_rate_circuit_break", identity, input_digest, report=report
            )

        now = time.monotonic()
        if not self._reserve_rate_slot(identity, now):
            return self._audited_result("denied", "rate_limit_exceeded", identity, input_digest)
        breaker = self._get_circuit_breaker()
        if not breaker.can_execute():
            return self._audited_result("blocked", "circuit_breaker_open", identity, input_digest)

        started = time.monotonic()
        try:
            recommendation = self._golden_step(optimisation)
            if time.monotonic() - started > budget["max_seconds"]:
                raise TimeoutError("optimizer exceeded its requested budget")
        except Exception:
            breaker.record_failure()
            return self._audited_result("failed", "optimizer_unavailable", identity, input_digest)
        breaker.record_success()
        return self._audited_result(
            "recommended",
            "advisory_only",
            identity,
            input_digest,
            report=report,
            recommendation=recommendation,
            budget=budget,
        )

    @staticmethod
    def _validate_metrics(metrics: Mapping[str, Any], baseline_throughput: float) -> None:
        if not isinstance(metrics, Mapping):
            raise ValueError("metrics must be an object")
        if (
            isinstance(baseline_throughput, bool)
            or not isinstance(baseline_throughput, (int, float))
            or not math.isfinite(baseline_throughput)
            or baseline_throughput <= 0
        ):
            raise ValueError("baseline_throughput must be finite and positive")

    @staticmethod
    def _validate_optimisation(optimisation: Mapping[str, Any], budget: Mapping[str, Any]) -> None:
        if not isinstance(optimisation, Mapping) or not isinstance(budget, Mapping):
            raise ValueError("optimization and budget must be objects")
        lower = optimisation["minimum"]
        upper = optimisation["maximum"]
        previous = optimisation["previous_value"]
        current = optimisation["current_value"]
        values = (lower, upper, previous, current)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            raise ValueError("optimization values must be finite numbers")
        if not all(math.isfinite(value) for value in values) or lower >= upper:
            raise ValueError("optimization bounds must be finite and increasing")
        if not lower <= previous <= upper or not lower <= current <= upper:
            raise ValueError("observed parameter values must be within the supplied bounds")
        if budget["max_steps"] != 1 or not 0 < budget["max_seconds"] <= 1.0:
            raise ValueError("optimizer budget is limited to one step and at most one second")

    def _golden_step(self, values: Mapping[str, Any]) -> dict[str, Any]:
        from Intelligence.autonomous_capabilities import CuopLearner

        holder = {"value": float(values["previous_value"])}
        learner = CuopLearner(
            str(values["parameter"]),
            lambda: holder["value"],
            lambda value: holder.__setitem__("value", value),
            float(values["minimum"]),
            float(values["maximum"]),
        )
        learner.record(float(values["previous_cuop"]))
        holder["value"] = float(values["current_value"])
        learner.record(float(values["current_cuop"]))
        suggestion = learner.suggest()
        return {
            "parameter": learner.name,
            "previous_value": float(values["previous_value"]),
            "current_value": float(values["current_value"]),
            "suggested_value": suggestion,
            "bounds": [learner.lo, learner.hi],
            "steps": 1,
        }

    def _homeostasis_report(
        self, metrics: Mapping[str, Any], baseline_throughput: float
    ) -> dict[str, Any]:
        monitor = self._get_monitor()
        monitor.set_baseline({"throughput": baseline_throughput})
        return monitor.check(dict(metrics)).as_dict()

    def _consume_lease(self, lease_id: str, identity: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None or lease["identity"] != identity:
                return "authority_lease_invalid"
            if lease["expires_mono"] <= now:
                self._leases.pop(lease_id, None)
                return "authority_lease_expired"
            if lease["capability"] != OPTIMISE_CAPABILITY:
                return "authority_lease_invalid"
            self._leases.pop(lease_id, None)
        return None

    def _reserve_rate_slot(self, identity: str, now: float) -> bool:
        with self._lock:
            attempts = self._optimise_times[identity]
            while attempts and now - attempts[0] >= OPTIMISE_WINDOW_SECONDS:
                attempts.popleft()
            if len(attempts) >= OPTIMISE_WINDOW_CALLS or (
                attempts and now - attempts[-1] < OPTIMISE_COOLDOWN_SECONDS
            ):
                return False
            attempts.append(now)
            return True

    def _audited_result(
        self,
        status: str,
        reason: str,
        identity: str,
        input_digest: str,
        *,
        report: Mapping[str, Any] | None = None,
        recommendation: Mapping[str, Any] | None = None,
        budget: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "event": "salamander_optimise",
            "identity": identity,
            "status": status,
            "reason": reason,
            "inputs_sha256": input_digest,
            "report": report,
            "recommendation": recommendation,
            "budget": budget,
            "applied": False,
            "timestamp": time.time(),
        }
        try:
            audit_record = self.control_plane.audit.append(payload)
        except Exception:
            return {"enabled": True, "status": "denied", "reason": "audit_persistence_failed"}
        return {
            "enabled": True,
            "status": status,
            "reason": reason,
            "report": json_safe(report) if report is not None else None,
            "recommendation": json_safe(recommendation) if recommendation is not None else None,
            "budget": json_safe(budget) if budget is not None else None,
            "applied": False,
            "audit_record": audit_record,
            "evidence_class": "caller_supplied_unverified_telemetry",
            "theorem_proven": False,
        }

    def _audit_ready(self) -> bool:
        audit = getattr(self.control_plane, "audit", None)
        return bool(audit is not None and audit.durable and audit.healthy)

    def _get_monitor(self) -> Any:
        if self._monitor is None:
            from Intelligence.salamander import HomeostasisMonitor

            self._monitor = HomeostasisMonitor()
        return self._monitor

    def _get_repair_engine(self) -> Any:
        if self._repair_engine is None:
            from Intelligence.salamander import SelfRepairEngine

            self._repair_engine = SelfRepairEngine()
        return self._repair_engine

    def _get_circuit_breaker(self) -> Any:
        if self._circuit_breaker is None:
            from Intelligence.salamander import CircuitBreaker

            self._circuit_breaker = CircuitBreaker()
        return self._circuit_breaker


__all__ = ["SALAMANDER_TOOLS", "SalamanderTools", "OPTIMISE_CAPABILITY"]
