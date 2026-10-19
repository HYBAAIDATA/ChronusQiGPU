"""Bounded pilot adapter; no new engine, identity authority or billing ledger.

The HTTP caller MUST complete AL HARAS preflight before dispatch. A security
subscription is not a commercial TURING entitlement. Enable only for controlled
technical evaluation; enterprise custody and commercial admission remain open.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from threading import Lock
from typing import Any, Callable

SCHEMA = "turing.workspace.v1"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}\Z")
GATES = frozenset({"i", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "cx", "cnot", "cz", "swap"})


class WorkspaceError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def validate_program(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"n_qubits", "operations"}:
        raise WorkspaceError(400, "invalid_program_schema")
    width, ops = value["n_qubits"], value["operations"]
    # Pilot admission envelope, NOT mathematical or commercial capacity claims.
    if type(width) is not int or not 1 <= width <= 12:
        raise WorkspaceError(400, "pilot_width_requires_integer_1_to_12")
    if not isinstance(ops, list) or len(ops) > 256:
        raise WorkspaceError(400, "pilot_operation_limit_256")
    normalized = []
    for op in ops:
        if not isinstance(op, dict) or set(op) != {"gate", "qubits"}:
            raise WorkspaceError(400, "invalid_operation_schema")
        gate, qubits = op["gate"], op["qubits"]
        if not isinstance(gate, str) or gate not in GATES:
            raise WorkspaceError(422, "unsupported_native_gate")
        arity = 2 if gate in {"cx", "cnot", "cz", "swap"} else 1
        if (not isinstance(qubits, list) or len(qubits) != arity
            or any(type(q) is not int or not 0 <= q < width for q in qubits)
            or len(set(qubits)) != arity):
            raise WorkspaceError(400, "invalid_gate_targets")
        normalized.append({"gate": gate, "qubits": list(qubits)})
    return {"n_qubits": width, "operations": normalized}


def native_pipeline():
    from turing_universal_quantum_computer.config import PipelineConfig
    from turing_universal_quantum_computer.public_api import TuringPipeline
    return TuringPipeline(PipelineConfig(max_qubits=12, max_amplitudes=4096))


def native_program(value):
    from turing_universal_quantum_computer.backends.base import Program
    return Program.from_dict(value)


@dataclass(frozen=True)
class Entry:
    owner: tuple[str, str]
    job: Any
    submitted_at: str
    program: dict[str, Any]


class Workspace:
    """One process, bounded registry. No restart recovery or commercial authority."""
    def __init__(self, pipeline_factory: Callable = native_pipeline,
                 program_factory: Callable = native_program, *, max_jobs: int = 256,
                 per_owner: int = 32):
        self._factory, self._program = pipeline_factory, program_factory
        self._pipeline = None
        self._jobs: dict[str, Entry] = {}
        self._keys: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._lock = Lock()
        self.max_jobs, self.per_owner = max_jobs, per_owner

    def dispatch(self, tenant: str, actor: str, body: dict) -> tuple[int, dict]:
        if not all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in (tenant, actor)):
            raise WorkspaceError(403, "verified_identity_required")
        action = body.get("action")
        fields = {
            "submit": {"program", "idempotency_key"},
            "status": {"job_id"}, "cancel": {"job_id"}, "capabilities": set(),
            "list": {"offset", "limit", "status", "query"},
        }
        if not isinstance(action, str) or action not in fields:
            raise WorkspaceError(400, "unsupported_workspace_action")
        if set(body) - (fields[action] | {"action", "observation"}):
            raise WorkspaceError(400, "unexpected_workspace_fields")
        owner = (tenant, actor)
        with self._lock:
            if action == "capabilities":
                return 200, self._envelope({
                    "max_qubits": 12, "max_operations": 256,
                    "max_amplitudes": 4096, "gates": sorted(GATES),
                    "max_retained_jobs": self.max_jobs,
                    "max_retained_jobs_per_identity": self.per_owner,
                    "commercial_entitlements": "not_integrated",
                    "billing": "not_integrated",
                })
            if action == "list":
                return 200, self._list(owner, body)
            if action == "submit":
                return self._submit(owner, body)
            job_id = body.get("job_id")
            entry = self._jobs.get(job_id) if isinstance(job_id, str) else None
            if entry is None or entry.owner != owner:
                raise WorkspaceError(404, "job_not_found_in_current_identity_or_process")
            if action == "cancel":
                cancelled = entry.job.cancel()
                return 200, self._snapshot(entry) | {"cancellation_accepted": cancelled}
            return 200, self._snapshot(entry)

    def _list(self, owner: tuple[str, str], body: dict) -> dict:
        """Only retained jobs for the verified identity; never a billing record.

        Mutable bounded offset pagination: refresh from offset zero after a new
        submission. No global counts, other actors, report payloads or keys leak.
        """
        offset, limit = body.get("offset", 0), body.get("limit", 10)
        status, query = body.get("status"), body.get("query", "")
        if (type(offset) is not int or not 0 <= offset <= self.max_jobs
            or type(limit) is not int or not 1 <= limit <= 20):
            raise WorkspaceError(400, "invalid_history_pagination")
        if status is not None and status not in ("queued", "running", "succeeded", "failed", "cancelled"):
            raise WorkspaceError(400, "invalid_history_status")
        if not isinstance(query, str) or len(query) > 128:
            raise WorkspaceError(400, "invalid_history_query")
        owned = [e for e in self._jobs.values() if e.owner == owner]
        rows = [{"job_id": e.job.job_id, "status": e.job.status().value,
                 "submitted_at": e.submitted_at, "n_qubits": e.program["n_qubits"],
                 "operation_count": len(e.program["operations"])} for e in owned]
        rows = [r for r in rows if (status is None or r["status"] == status)
                and query.casefold() in r["job_id"].casefold()]
        rows.sort(key=lambda r: (r["submitted_at"], r["job_id"]), reverse=True)
        page = rows[offset:offset + limit]
        return self._envelope({"jobs": page, "offset": offset, "limit": limit,
            "total_matching": len(rows), "total_retained": len(owned),
            "next_offset": offset + limit if offset + limit < len(rows) else None,
            "observed_at": datetime.now(timezone.utc).isoformat()})

    def _submit(self, owner: tuple[str, str], body: dict) -> tuple[int, dict]:
        program = validate_program(body.get("program"))
        key = body.get("idempotency_key")
        if not isinstance(key, str) or not IDENTIFIER.fullmatch(key):
            raise WorkspaceError(400, "valid_idempotency_key_required")
        fingerprint = sha256(json.dumps(program, sort_keys=True).encode()).hexdigest()
        scoped = (*owner, key)
        if scoped in self._keys:
            previous, job_id = self._keys[scoped]
            if previous != fingerprint:
                raise WorkspaceError(409, "idempotency_key_conflict")
            return 200, self._snapshot(self._jobs[job_id]) | {"idempotent_replay": True}
        if (len(self._jobs) >= self.max_jobs
            or sum(e.owner == owner for e in self._jobs.values()) >= self.per_owner):
            raise WorkspaceError(429, "pilot_retained_job_limit_reached")
        if self._pipeline is None:
            self._pipeline = self._factory()
        # The native facade compiles, admits, then submits; no browser engine.
        engine_key = sha256(json.dumps(scoped).encode()).hexdigest()
        job = self._pipeline.submit(self._program(program), idempotency_key=engine_key)
        entry = Entry(owner, job, datetime.now(timezone.utc).isoformat(), program)
        self._jobs[job.job_id] = entry
        self._keys[scoped] = fingerprint, job.job_id
        return 202, self._snapshot(entry)

    @staticmethod
    def _envelope(payload: dict) -> dict:
        return {"schema_version": SCHEMA, "persistence": "in_memory_process_local",
                "service_mode": "technical_evaluation_only", **payload}

    def _snapshot(self, entry: Entry) -> dict:
        status = entry.job.status().value
        payload = {"job_id": entry.job.job_id, "status": status,
                   "submitted_at": entry.submitted_at, "program": entry.program}
        if status == "succeeded":
            payload["report"] = entry.job.result(timeout=0).report()
        elif status == "failed":
            # Never return arbitrary engine exception messages or host paths.
            payload["error"] = "native_execution_failed"
        return self._envelope(payload)

    def close(self):
        with self._lock:
            pipeline = self._pipeline
        if pipeline is not None:
            pipeline.close()


_WORKSPACE = Workspace()


def handle_workspace(headers, body, receipt) -> tuple[int, dict]:
    """Called only AFTER preflight; re-check receipt rather than trusting headers alone."""
    if os.environ.get("TURING_WORKSPACE_PILOT_ENABLED") != "1":
        return 503, {"error": "turing_workspace_pilot_disabled"}
    tenant, actor = headers.get("X-HYBA-Tenant", ""), headers.get("X-HYBA-Actor", "")
    if (not isinstance(receipt, dict) or receipt.get("allowed") is not True
        or receipt.get("tenant_id") != tenant or receipt.get("operation") != "quantum.workspace"):
        return 403, {"error": "workspace_guardian_admission_required"}
    try:
        return _WORKSPACE.dispatch(tenant, actor, body)
    except WorkspaceError as exc:
        return exc.status, {"error": exc.code}
    except ImportError:
        return 503, {"error": "turing_public_api_dependency_unavailable"}
    except Exception as exc:
        # Import lazily; an absent facade is a dependency error, never a fake result.
        try:
            from turing_universal_quantum_computer.exceptions import (
                CapabilityError, CompilationError, ParameterValidationError,
                IdempotencyConflictError,
            )
        except ImportError:
            return 503, {"error": "turing_public_api_dependency_unavailable"}
        if isinstance(exc, IdempotencyConflictError):
            return 409, {"error": "native_idempotency_conflict"}
        if isinstance(exc, (CapabilityError, CompilationError, ParameterValidationError)):
            return 422, {"error": "native_admission_refused"}
        return 503, {"error": "native_service_unavailable", "execution_outcome": "unknown"}
