"""Governed routing, authorization, auditing, and bounded skill execution."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from .skills import SKILL_MODULES, get_skill_module
from .skills.common import json_safe, validate_schema
from .hyba_context import resolve_context_budget

MAX_AUDIT_PAYLOAD_BYTES = 1_048_576


def _canonical(value: Any) -> str:
    def convert(item: Any) -> Any:
        if isinstance(item, bytes):
            return {"$bytes_hex": item.hex()}
        if isinstance(item, Mapping):
            return {str(key): convert(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(val) for val in item]
        return item

    return json.dumps(convert(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _audit_payload(value: Any) -> Any:
    encoded = _canonical(value).encode()
    if len(encoded) > MAX_AUDIT_PAYLOAD_BYTES:
        return {
            "truncated": True,
            "size_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    return json_safe(value)


def _stop_process(process: multiprocessing.Process) -> None:
    process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)


class AuditTrail:
    """Append-only SHA-256 chained audit records with optional durable storage."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._lock = RLock()
        self._records: list[dict[str, Any]] = []
        self._healthy = True
        if self.path is not None and self.path.exists():
            try:
                with self.path.open("a+", encoding="utf-8") as handle:
                    self._lock_file(handle, exclusive=True)
                    try:
                        self._records = self._read_file(handle)
                    finally:
                        self._lock_file(handle, exclusive=False)
            except Exception:
                self._healthy = False
                raise

    @property
    def durable(self) -> bool:
        return self.path is not None

    @property
    def healthy(self) -> bool:
        return self._healthy

    @staticmethod
    def _lock_file(handle: Any, *, exclusive: bool) -> None:
        try:
            import fcntl
        except ImportError:
            try:
                import msvcrt
            except ImportError as exc:
                raise RuntimeError("cross-process audit locking is unavailable") from exc
            handle.seek(0)
            mode = msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK
            msvcrt.locking(handle.fileno(), mode, 1)
        else:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN,
            )

    @staticmethod
    def _read_file(handle: Any) -> list[dict[str, Any]]:
        handle.seek(0)
        records: list[dict[str, Any]] = []
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            previous = records[-1]["record_hash"] if records else "0" * 64
            if record.get("previous_hash") != previous:
                raise ValueError("audit chain predecessor mismatch")
            body = {key: value for key, value in record.items() if key != "record_hash"}
            expected = hashlib.sha256(_canonical(body).encode()).hexdigest()
            if record.get("record_hash") != expected:
                raise ValueError("audit record hash mismatch")
            records.append(record)
        return records

    def _verify_next(self, record: Mapping[str, Any]) -> None:
        previous = self._records[-1]["record_hash"] if self._records else "0" * 64
        if record.get("previous_hash") != previous:
            raise ValueError("audit chain predecessor mismatch")
        body = {key: value for key, value in record.items() if key != "record_hash"}
        expected = hashlib.sha256(_canonical(body).encode()).hexdigest()
        if record.get("record_hash") != expected:
            raise ValueError("audit record hash mismatch")

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not self._healthy:
                raise RuntimeError("audit trail is unhealthy; reload and verify before use")
            if self.path is not None:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("a+", encoding="utf-8") as handle:
                        self._lock_file(handle, exclusive=True)
                        try:
                            self._records = self._read_file(handle)
                            record = self._append_record(event)
                            handle.seek(0, os.SEEK_END)
                            handle.write(_canonical(record) + "\n")
                            handle.flush()
                            os.fsync(handle.fileno())
                            self._records.append(record)
                        finally:
                            self._lock_file(handle, exclusive=False)
                except Exception:
                    self._healthy = False
                    raise
            else:
                record = self._append_record(event)
                self._records.append(record)
            return deepcopy(record)

    def _append_record(self, event: Mapping[str, Any]) -> dict[str, Any]:
        body = {
            **json_safe(event),
            "sequence": len(self._records) + 1,
            "previous_hash": self._records[-1]["record_hash"] if self._records else "0" * 64,
        }
        return {**body, "record_hash": hashlib.sha256(_canonical(body).encode()).hexdigest()}

    def records(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._records)

    def verify(self) -> bool:
        with self._lock:
            if not self._healthy:
                return False
            if self.path is not None:
                try:
                    with self.path.open("a+", encoding="utf-8") as handle:
                        self._lock_file(handle, exclusive=True)
                        try:
                            self._records = self._read_file(handle)
                        finally:
                            self._lock_file(handle, exclusive=False)
                    return True
                except Exception:
                    self._healthy = False
                    return False
            original = self._records
            self._records = []
            try:
                for record in original:
                    self._verify_next(record)
                    self._records.append(record)
            except (KeyError, TypeError, ValueError):
                return False
            finally:
                self._records = original
            return True


@dataclass(frozen=True)
class SandboxConfig:
    timeout_seconds: float = 30.0
    cpu_seconds: int = 15
    memory_bytes: int = 2_147_483_648
    max_input_bytes: int = 1_048_576
    max_output_bytes: int = 1_048_576

    def validate(self) -> None:
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("sandbox timeout_seconds must be finite and positive")
        if self.timeout_seconds > 30 or self.cpu_seconds > 15:
            raise ValueError("sandbox limits exceed the control-plane ceiling")
        if (
            isinstance(self.cpu_seconds, bool)
            or not isinstance(self.cpu_seconds, int)
            or self.cpu_seconds <= 0
            or self.memory_bytes <= 0
            or self.memory_bytes > 2_147_483_648
        ):
            raise ValueError("sandbox CPU and memory limits must be positive")
        if (
            self.max_input_bytes <= 0
            or self.max_output_bytes <= 0
            or self.max_input_bytes > 1_048_576
            or self.max_output_bytes > 1_048_576
        ):
            raise ValueError("sandbox payload limits must be positive")


def _sandbox_worker(
    connection: Any,
    skill_id: str,
    arguments: dict[str, Any],
    sandbox: SandboxConfig,
) -> None:
    try:
        module = get_skill_module(skill_id)
        try:
            import resource
        except ImportError as exc:
            raise RuntimeError("OS resource limits are unavailable; execution denied") from exc
        resource.setrlimit(resource.RLIMIT_CPU, (sandbox.cpu_seconds, sandbox.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (sandbox.memory_bytes, sandbox.memory_bytes))
        result = module.run(**arguments)
        payload = _canonical(json_safe(result)).encode()
        if len(payload) > sandbox.max_output_bytes:
            raise RuntimeError("skill output exceeds sandbox payload limit")
        connection.send({"ok": True, "result": json.loads(payload)})
    except BaseException as exc:
        try:
            connection.send(
                {
                    "ok": False,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            )
        except (BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


def _authorization_result(value: Any) -> tuple[bool, str, dict[str, Any]]:
    if isinstance(value, tuple):
        allowed = value[0] is True if value else False
        reason = str(value[1]) if len(value) > 1 else ("allowed" if allowed else "denied")
        audit = value[2] if len(value) > 2 and isinstance(value[2], dict) else {}
        return allowed, reason, audit
    if isinstance(value, Mapping):
        allowed = value.get("allowed") is True
        reason = str(value.get("reason", "allowed" if allowed else "denied"))
        audit = value.get("audit_record", {})
        return allowed, reason, dict(audit) if isinstance(audit, Mapping) else {}
    allowed = value is True
    return allowed, "allowed" if allowed else "denied", {}


class ControlPlane:
    """Fail-closed capability routing and execution control plane."""

    def __init__(
        self,
        *,
        authorizer: Callable[[str, str, dict[str, Any]], Any] | None = None,
        audit_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self.authorizer = authorizer
        self.audit = AuditTrail(audit_path)
        self._outcomes: dict[str, list[dict[str, Any]]] = {}
        self._lock = RLock()

    def validate_inputs(self, skill_id: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            module = get_skill_module(skill_id)
        except KeyError:
            return {"valid": False, "errors": [f"unknown skill: {skill_id}"]}
        errors = validate_schema(arguments, module.INPUT_SCHEMA)
        return {"valid": not errors, "errors": errors, "skill_id": skill_id}

    def enforce_context_budget(
        self, tier: str = "T0", budget_bytes: int | None = None
    ) -> dict[str, Any]:
        """Validate a context request against its tier ceiling and Lucas scale."""
        return resolve_context_budget(tier, budget_bytes)

    def route_task(
        self,
        task: Mapping[str, Any],
        constraints: Mapping[str, Any] | None = None,
    ) -> tuple[str | None, int | None, float | None]:
        """Pick the cheapest explicitly declared candidate within caller budgets."""
        if not isinstance(task, Mapping) or (
            constraints is not None and not isinstance(constraints, Mapping)
        ):
            return None, None, None
        budgets = constraints or {}
        requested = task.get("candidates", task.get("fallback_chain"))
        candidates = (
            list(requested) if isinstance(requested, (list, tuple)) else [task.get("skill_id")]
        )
        try:
            max_cost = float(budgets.get("max_cost", float("inf")))
            max_risk = float(budgets.get("max_risk", 1.0))
            max_seconds = float(budgets.get("max_seconds", float("inf")))
            if (
                any(math.isnan(value) for value in (max_cost, max_risk, max_seconds))
                or max_risk < 0
                or max_seconds < 0
            ):
                return None, None, None
        except (TypeError, ValueError):
            return None, None, None
        admitted = []
        for skill_id in candidates:
            if not isinstance(skill_id, str) or skill_id not in SKILL_MODULES:
                continue
            module = get_skill_module(skill_id)
            cost, risk = module.COST_ESTIMATE, module.RISK_LEVEL
            if cost > max_cost:
                continue
            if risk > max_risk:
                continue
            if module.TIME_ESTIMATE > max_seconds:
                continue
            admitted.append((cost, skill_id, risk))
        if not admitted:
            return None, None, None
        cost, skill_id, risk = min(admitted, key=lambda row: (row[0], row[1]))
        return skill_id, cost, risk

    def check_permission(
        self,
        identity: str,
        skill_id: str,
        arguments: Mapping[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        """Check the deployment-bound AL HARAS authorizer and write the decision."""
        allowed, reason, evidence = False, "AL HARAS authorizer unavailable", {}
        if not self.audit.healthy:
            reason = "audit trail is unhealthy; denied by policy"
        try:
            audited_inputs = _audit_payload(arguments)
        except (TypeError, ValueError):
            audited_inputs = {"unserializable": True}
            reason = "invalid input; denied by policy"
        else:
            if isinstance(audited_inputs, Mapping) and audited_inputs.get("truncated") is True:
                reason = "input exceeds audit payload limit; denied by policy"
        if (
            self.audit.healthy
            and reason == "AL HARAS authorizer unavailable"
            and isinstance(identity, str)
            and identity
            and isinstance(skill_id, str)
            and skill_id in SKILL_MODULES
            and isinstance(arguments, Mapping)
            and self.authorizer is not None
        ):
            try:
                allowed, reason, evidence = _authorization_result(
                    self.authorizer(identity, skill_id, dict(arguments))
                )
            except Exception:
                allowed, reason = False, "AL HARAS authorization failed closed"
        if allowed and not self.audit.durable:
            allowed, reason = False, "durable audit storage unavailable; denied by policy"
        event = {
            "event": "permission_decision",
            "identity": identity,
            "skill_id": skill_id,
            "inputs": audited_inputs,
            "allowed": allowed,
            "reason": reason,
            "authorization": evidence,
            "timestamp": time.time(),
        }
        try:
            record = self.audit.append(event)
        except Exception:
            return False, "audit persistence failed; denied by policy", {}
        if not allowed:
            return False, reason, record
        return True, reason, record

    def execute_skill(
        self,
        skill_id: str,
        arguments: Mapping[str, Any],
        sandbox_config: SandboxConfig | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one registered skill in a resource-limited child process."""
        validation = self.validate_inputs(skill_id, arguments)
        if not validation["valid"]:
            return {
                "ok": False,
                "error": {"code": "invalid_input", "details": validation["errors"]},
            }
        try:
            sandbox = (
                sandbox_config
                if isinstance(sandbox_config, SandboxConfig)
                else SandboxConfig(**dict(sandbox_config or {}))
            )
            sandbox.validate()
            normalized = dict(arguments)
            if skill_id == "mining.guidance":
                normalized["header"] = bytes(normalized["header"])
                normalized["target"] = bytes(normalized["target"])
            encoded = _canonical(normalized).encode()
            if len(encoded) > sandbox.max_input_bytes:
                raise ValueError("skill input exceeds sandbox payload limit")
        except (TypeError, ValueError) as exc:
            return {"ok": False, "error": {"code": "invalid_sandbox_config", "message": str(exc)}}

        if skill_id == "security.verify_authority":
            # The only non-isolated operation is the trusted authorization adapter;
            # untrusted skill arguments are still schema-bounded and never executed.
            try:
                module = get_skill_module(skill_id)
                result = module.run(**normalized, authorizer=self.authorizer)
                return {"ok": True, "result": json_safe(result)}
            except Exception as exc:
                return {"ok": False, "error": {"code": "skill_failed", "message": str(exc)}}

        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_sandbox_worker,
            args=(child, skill_id, normalized, sandbox),
            daemon=True,
        )
        started = False
        try:
            process.start()
            started = True
            child.close()
            if not parent.poll(sandbox.timeout_seconds):
                _stop_process(process)
                return {"ok": False, "error": {"code": "timeout", "message": "skill timed out"}}
            response = parent.recv()
            process.join(timeout=1)
            if process.is_alive():
                _stop_process(process)
            if not response.get("ok"):
                return {
                    "ok": False,
                    "error": {"code": "skill_failed", **response.get("error", {})},
                }
            result = response["result"]
            output_errors = validate_schema(result, get_skill_module(skill_id).OUTPUT_SCHEMA)
            if output_errors:
                return {
                    "ok": False,
                    "error": {"code": "invalid_skill_output", "details": output_errors},
                }
            return {"ok": True, "result": result}
        except (OSError, EOFError, RuntimeError) as exc:
            if started and process.is_alive():
                _stop_process(process)
            return {"ok": False, "error": {"code": "sandbox_failed", "message": str(exc)}}
        finally:
            parent.close()
            child.close()

    def record_outcome(
        self,
        skill_id: str,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        latency: float,
        success: bool,
        *,
        identity: str = "",
    ) -> dict[str, Any]:
        """Record evaluation telemetry and a confidence-calibration observation."""
        if skill_id not in SKILL_MODULES:
            raise ValueError(f"unknown skill: {skill_id}")
        if (
            not isinstance(inputs, Mapping)
            or not isinstance(outputs, Mapping)
            or isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or not math.isfinite(latency)
            or latency < 0
        ):
            raise ValueError("latency must be finite and non-negative")
        try:
            encoded = _canonical({"inputs": inputs, "outputs": outputs}).encode()
        except (TypeError, ValueError) as exc:
            raise ValueError("outcome must be finite JSON data") from exc
        if len(encoded) > MAX_AUDIT_PAYLOAD_BYTES:
            raise ValueError("outcome exceeds the audit payload limit")
        confidence = outputs.get("confidence")
        if (
            isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and not math.isfinite(float(confidence))
        ):
            raise ValueError("confidence must be finite")
        brier = (
            (float(confidence) - float(bool(success))) ** 2
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
            else None
        )
        record = {
            "skill_id": skill_id,
            "identity": identity,
            "inputs": json_safe(inputs),
            "outputs": json_safe(outputs),
            "latency_seconds": latency,
            "success": bool(success),
            "estimated_cost": get_skill_module(skill_id).COST_ESTIMATE,
            "brier_score": brier,
            "timestamp": time.time(),
        }
        with self._lock:
            history = self._outcomes.setdefault(skill_id, [])
            history.append(record)
            success_rate = sum(item["success"] for item in history) / len(history)
            summary = {
                "observations": len(history),
                "success_rate": success_rate,
                "mean_latency_seconds": sum(item["latency_seconds"] for item in history)
                / len(history),
                "mean_brier_score": (
                    sum(item["brier_score"] for item in history if item["brier_score"] is not None)
                    / sum(item["brier_score"] is not None for item in history)
                    if any(item["brier_score"] is not None for item in history)
                    else None
                ),
                "regression_detected": len(history) >= 5 and success_rate < 0.9,
            }
        self.audit.append({"event": "skill_outcome", **record, "summary": summary})
        return summary

    def invoke_skill(
        self,
        identity: str,
        skill_id: str,
        arguments: Mapping[str, Any],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply schema, budgets, permission, sandbox, audit, and evaluation gates."""
        opts = options or {}
        if not isinstance(skill_id, str) or skill_id not in SKILL_MODULES:
            return {"ok": False, "error": {"code": "unknown_skill"}}
        if not isinstance(opts, Mapping):
            return {"ok": False, "error": {"code": "invalid_options"}}
        routed, cost, risk = self.route_task({"skill_id": skill_id}, opts.get("constraints", {}))
        if routed is None:
            return {
                "ok": False,
                "error": {
                    "code": "budget_exceeded",
                    "message": "No competent skill meets the budgets",
                },
            }
        validation = self.validate_inputs(skill_id, arguments)
        if not validation["valid"]:
            try:
                audit = self.audit.append(
                    {
                        "event": "input_validation_denied",
                        "identity": identity,
                        "skill_id": skill_id,
                        "inputs": _audit_payload(arguments),
                        "errors": validation["errors"],
                        "timestamp": time.time(),
                    }
                )
            except Exception:
                audit = {}
            return {
                "ok": False,
                "error": {"code": "invalid_input", "details": validation["errors"]},
                "audit_record": audit,
            }
        allowed, reason, permission_record = self.check_permission(identity, skill_id, arguments)
        if not allowed:
            return {
                "ok": False,
                "error": {"code": "permission_denied", "message": reason},
                "audit_record": permission_record,
            }
        sandbox_options = opts.get("sandbox", {})
        started = time.monotonic()
        result = self.execute_skill(skill_id, arguments, sandbox_options)
        latency = time.monotonic() - started
        output = result.get("result", {})
        success = result.get("ok") is True
        try:
            record = self.audit.append(
                {
                    "event": "skill_invocation",
                    "identity": identity,
                    "skill_id": skill_id,
                    "inputs": json_safe(arguments),
                    "outputs": json_safe(output) if success else result.get("error"),
                    "latency_seconds": latency,
                    "success": success,
                    "timestamp": time.time(),
                }
            )
        except Exception:
            return {"ok": False, "error": {"code": "audit_persistence_failed"}}
        try:
            evaluation = self.record_outcome(
                skill_id, arguments, output, latency, success, identity=identity
            )
        except (OSError, ValueError):
            evaluation = {"recorded": False}
        response = {
            **result,
            "skill_id": skill_id,
            "cost_estimate": cost,
            "risk_level": risk,
            "latency_seconds": latency,
            "audit_record": record,
            "evaluation": evaluation,
        }
        if not success:
            response["error"].setdefault("code", "skill_failed")
        return response


__all__ = ["AuditTrail", "ControlPlane", "SandboxConfig"]
