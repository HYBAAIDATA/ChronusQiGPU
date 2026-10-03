"""#107 production-mining integration for the certified Chronus corpus.

This module binds the #104 conformance authority, #105 capability truth and
#106 typed intrinsics into the existing production mining coordinator.  It
owns evidence and capability admission only.  Stratum owns work identity and
pool outcomes; SHA256d/target comparison owns proof validity; ExecutionRouter
owns physical dispatch; RecoveryGovernor remains Salamander's single writer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from compiler.intrinsics import compile_intrinsic, execute_reference

SCHEMA = "chronus.production-mining-integration.v1"
EVIDENCE_SCHEMA = "chronus.production-mining-evidence.v1"
TRUTH_STATES = frozenset({
    "VERIFIED", "SOFTWARE_VERIFIED", "DEVICE_AVAILABLE", "HARDWARE_EXECUTED",
    "POOL_CONFIRMED", "UNSUPPORTED", "OPEN", "NOT_RUN", "NOT_REPORTED",
    "PHYSICAL_EVIDENCE_REQUIRED",
})
EXPECTED_BASE_SHA = "c0258303c4eed59f0a4fcae3e62c908f641a57a7"
EXPECTED_CORPUS_SHA256 = "0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class ProductionIntegrationError(RuntimeError):
    """The #107 production-mining contract is absent or contradictory."""


class ProductionMiningIntegration:
    """Evidence adapter over the existing mining authorities; never a second miner."""

    def __init__(self, manifest: Mapping[str, Any], *, source: str = "injected") -> None:
        self.manifest = dict(manifest)
        self.source = source
        self._validate()
        self.manifest_digest = digest(self.manifest)

    @classmethod
    def from_repository(cls, root: str | Path | None = None) -> "ProductionMiningIntegration":
        repo = Path(root) if root is not None else Path(__file__).resolve().parents[3]
        path = repo / "manifests" / "chronus107" / "production-mining.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProductionIntegrationError(f"cannot load #107 manifest: {exc}") from exc
        return cls(value, source=str(path))

    def _validate(self) -> None:
        m = self.manifest
        if m.get("schema") != SCHEMA:
            raise ProductionIntegrationError("unsupported #107 manifest schema")
        if m.get("base_sha") != EXPECTED_BASE_SHA:
            raise ProductionIntegrationError("#107 must stack on the exact #106 head")
        if m.get("chronus104_corpus_sha256") != EXPECTED_CORPUS_SHA256:
            raise ProductionIntegrationError("#104 corpus authority digest changed")
        states = m.get("truth_states")
        if not isinstance(states, Mapping) or any(v not in TRUTH_STATES for v in states.values()):
            raise ProductionIntegrationError("unknown or missing capability truth state")
        required = {
            "f64": "UNSUPPORTED",
            "opencl.BINET_EXACT": "UNSUPPORTED",
            "FOLDED_NATIVE": "OPEN",
            "physical_opencl": "PHYSICAL_EVIDENCE_REQUIRED",
            "acceptance": "NOT_RUN",
            "ci": "NOT_REPORTED",
        }
        if any(states.get(k) != v for k, v in required.items()):
            raise ProductionIntegrationError("locked #104-#107 truth boundary contradicted")
        authority = m.get("authority", {})
        exact = {
            "work_identity": "stratum_adapter",
            "sha256d_target": "proof_adapter_and_host_recheck",
            "pool_outcome": "literal_pool_response",
            "physical_execution": "execution_router",
            "recovery": "recovery_governor",
            "custody": "existing_aethel_and_causal_ledgers",
        }
        if any(authority.get(k) != v for k, v in exact.items()):
            raise ProductionIntegrationError("#107 may not replace mining truth owners")

    def plan_evidence(self, extent: int, maximum_work_group_size: int) -> Mapping[str, Any]:
        """Run #106 PISOT_SCHEDULE as a proposal and seal the result.

        The proposal never changes the leased range, target, nonce validity or
        selected backend. Conventional candidates remain in the candidate set;
        measurement outside this method retains promotion authority.
        """
        limit = 16
        ir = {
            "schema": "chronus.ir.v0.2", "name": "mining_window_candidates",
            "op": "intrinsic", "intrinsic": "PISOT_SCHEDULE",
            "operands": {
                "extent": int(extent), "maximum_candidates": limit,
                "maximum_work_group_size": int(maximum_work_group_size),
            },
            "result_type": "candidate_set", "lowering": "REFERENCE_HOST",
        }
        plan = compile_intrinsic(ir)
        candidates = execute_reference(plan)
        body = {
            "schema": EVIDENCE_SCHEMA,
            "kind": "PLAN",
            "manifest_sha256": self.manifest_digest,
            "conformance_corpus_sha256": EXPECTED_CORPUS_SHA256,
            "intrinsic": "PISOT_SCHEDULE",
            "intrinsic_backend": plan.backend,
            "intrinsic_numeric_class": "EXACT",
            "candidates": candidates,
            "authority": "ADVISORY_ONLY_MEASUREMENT_SELECTS",
        }
        return {**body, "evidence_sha256": digest(body)}

    def route_evidence(self, hasher: Any) -> Mapping[str, Any]:
        backend = str(getattr(hasher, "backend", "") or "cpu_reference")
        physical = backend.startswith("opencl") or backend == "remote_opencl"
        state = "DEVICE_AVAILABLE" if physical else "SOFTWARE_VERIFIED"
        body = {
            "schema": EVIDENCE_SCHEMA,
            "kind": "ROUTE_ADMISSION",
            "manifest_sha256": self.manifest_digest,
            "backend": backend,
            "device": getattr(hasher, "device", None),
            "vendor": getattr(hasher, "vendor", None),
            "state": state,
            "hardware_executed": False,
            "physical_evidence_gate": "PHYSICAL_EVIDENCE_REQUIRED" if physical else "NOT_APPLICABLE",
        }
        return {**body, "evidence_sha256": digest(body)}

    def execution_evidence(self, record: Any) -> Mapping[str, Any]:
        raw = asdict(record) if is_dataclass(record) else dict(record)
        evidence_class = getattr(getattr(record, "evidence_class", None), "value", raw.get("evidence_class"))
        outcome = getattr(getattr(record, "pool_outcome", None), "value", raw.get("pool_outcome"))
        launches = int(raw.get("kernel_launch_count", 0) or 0)
        completed = int(raw.get("completed_work_items", 0) or 0)
        if evidence_class == "HARDWARE_EXECUTED" and (launches <= 0 or completed <= 0):
            raise ProductionIntegrationError("hardware evidence requires launch and completed work")
        state = "POOL_CONFIRMED" if outcome == "ACCEPTED" else str(evidence_class or "NOT_RUN")
        body = {
            "schema": EVIDENCE_SCHEMA,
            "kind": "EXECUTION",
            "manifest_sha256": self.manifest_digest,
            "plan_id": raw.get("search_plan_id") or raw.get("plan_id"),
            "job_fingerprint": raw.get("job_fingerprint"),
            "requested_route": raw.get("requested_route"),
            "executed_route": raw.get("executed_route"),
            "completion_state": getattr(raw.get("completion_state"), "value", raw.get("completion_state")),
            "hash_count": raw.get("hash_count"),
            "kernel_launch_count": launches,
            "pool_outcome": outcome,
            "state": state,
            "physical_evidence": state in {"HARDWARE_EXECUTED", "POOL_CONFIRMED"} and launches > 0,
        }
        return {**body, "evidence_sha256": digest(body)}

    def recovery_evidence(self, governor: Any) -> Mapping[str, Any]:
        """Bind existing mining-specific Salamander state without adding policy."""
        snapshot = governor.snapshot()
        body = {
            "schema": EVIDENCE_SCHEMA,
            "kind": "MINING_RECOVERY",
            "manifest_sha256": self.manifest_digest,
            "entrypoint": "IntelligentPoolCoordinator.apply_salamander_mode",
            "authority": "recovery_governor",
            "scope": "PRODUCTION_MINING_ONLY",
            "snapshot": snapshot,
        }
        return {**body, "evidence_sha256": digest(body)}

    def snapshot(self, *, hasher: Any, recovery: Any) -> Mapping[str, Any]:
        return {
            "schema": SCHEMA,
            "manifest_sha256": self.manifest_digest,
            "base_sha": EXPECTED_BASE_SHA,
            "conformance_corpus_sha256": EXPECTED_CORPUS_SHA256,
            "route": self.route_evidence(hasher),
            "recovery": self.recovery_evidence(recovery),
            "truth_states": dict(self.manifest["truth_states"]),
        }


__all__ = [
    "EXPECTED_BASE_SHA", "EXPECTED_CORPUS_SHA256", "ProductionIntegrationError",
    "ProductionMiningIntegration", "canonical", "digest",
]
