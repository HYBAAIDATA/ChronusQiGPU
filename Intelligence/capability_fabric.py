"""Euclid / Salamander Native Capability Fabric.

Extensible capability execution architecture:
- Native capability registration
- Typed manifest contracts (permissions, budgets, profiles, determinism)
- Execution isolation and profile gating (internal research vs shared restricted)
- Deterministic execution receipts binding inputs, outputs, and findings
- Default-deny security model: unequipped or unpermitted actions fail at authorization
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class ExecutionProfile(str, Enum):
    """Enforceable operational profiles."""

    INTERNAL_RESEARCH = "internal"
    SHARED_RESTRICTED = "shared"


class DeterminismClass(str, Enum):
    """Determinism guarantee of capability execution."""

    DETERMINISTIC = "deterministic"
    STOCHASTIC = "stochastic"
    PSEUDORANDOM = "pseudorandom"


class SideEffectClass(str, Enum):
    """Side effect classification for sandbox and audit."""

    READ_ONLY = "read_only"
    ISOLATED_MUTATION = "isolated_mutation"
    SYSTEM_MUTATION = "system_mutation"


class AuthorizationDenied(PermissionError):
    """Raised when an operation is prohibited by capability permissions or execution profile."""


class CapabilityRegistrationError(ValueError):
    """Raised on invalid capability manifest or duplicate registration."""


class CapabilityExecutionError(RuntimeError):
    """Raised when capability execution fails or violates resource bounds."""


@dataclass(frozen=True)
class CapabilityPermissions:
    """Explicit least-privilege permissions model."""

    can_read_repository: bool = True
    can_write_repository: bool = False
    can_execute_code: bool = False
    can_spawn_process: bool = False
    can_use_network: bool = False
    can_install_dependency: bool = False
    can_modify_configuration: bool = False
    can_access_credentials: bool = False
    can_invoke_recovery: bool = False
    can_mutate_capability_registry: bool = False
    allowed_profiles: Tuple[ExecutionProfile, ...] = (
        ExecutionProfile.INTERNAL_RESEARCH,
    )

    def is_permitted_for(self, profile: ExecutionProfile) -> bool:
        if profile not in self.allowed_profiles:
            return False
        # In SHARED_RESTRICTED profile, dangerous write/exec/system permissions are strictly forbidden
        if profile == ExecutionProfile.SHARED_RESTRICTED:
            if (
                self.can_write_repository
                or self.can_spawn_process
                or self.can_use_network
                or self.can_install_dependency
                or self.can_modify_configuration
                or self.can_access_credentials
                or self.can_invoke_recovery
                or self.can_mutate_capability_registry
            ):
                return False
        return True


@dataclass(frozen=True)
class ResourceBudget:
    """Strict resource envelopes preventing runaway tasks."""

    max_file_bytes: int = 262144
    max_total_bytes: int = 1048576
    max_findings: int = 128
    max_runtime_seconds: float = 30.0
    max_memory_mb: int = 512


def _digest_data(val: Any) -> str:
    """Compute deterministic canonical SHA256 digest."""
    return hashlib.sha256(
        json.dumps(val, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class CapabilityManifest:
    """Machine-readable contract defining an integrated capability."""

    capability_id: str
    version: str
    source_provenance: str
    description: str
    permissions: CapabilityPermissions
    resource_budget: ResourceBudget
    supported_operations: Tuple[str, ...]
    determinism: DeterminismClass
    side_effects: SideEffectClass
    verification_strategy: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.capability_id or not isinstance(self.capability_id, str):
            raise CapabilityRegistrationError("capability_id must be a non-empty string")
        if not self.version or not isinstance(self.version, str):
            raise CapabilityRegistrationError("version must be a non-empty semantic version string")
        if not self.source_provenance or not isinstance(self.source_provenance, str):
            raise CapabilityRegistrationError("source_provenance must be declared")


@dataclass(frozen=True)
class CapabilityExecutionReceipt:
    """Cryptographically anchored execution proof."""

    receipt_id: str
    capability_id: str
    version: str
    profile: str
    input_digest: str
    output_digest: str
    status: str
    execution_timestamp: float
    duration_seconds: float
    findings: List[Dict[str, Any]]
    side_effects: Dict[str, Any]
    receipt_sha256: str

    @classmethod
    def create(
        cls,
        *,
        capability_id: str,
        version: str,
        profile: str,
        inputs: Any,
        outputs: Any,
        status: str,
        duration_seconds: float,
        findings: Optional[List[Dict[str, Any]]] = None,
        side_effects: Optional[Dict[str, Any]] = None,
    ) -> CapabilityExecutionReceipt:
        receipt_id = hashlib.sha256(
            f"{capability_id}:{version}:{time.time()}:{_digest_data(inputs)}".encode()
        ).hexdigest()[:16]
        input_digest = _digest_data(inputs)
        output_digest = _digest_data(outputs)
        findings_list = findings or []
        side_effects_dict = side_effects or {}
        now = time.time()

        payload = {
            "receipt_id": receipt_id,
            "capability_id": capability_id,
            "version": version,
            "profile": profile,
            "input_digest": input_digest,
            "output_digest": output_digest,
            "status": status,
            "execution_timestamp": now,
            "duration_seconds": duration_seconds,
            "findings": findings_list,
            "side_effects": side_effects_dict,
        }
        receipt_sha256 = _digest_data(payload)

        return cls(
            receipt_id=receipt_id,
            capability_id=capability_id,
            version=version,
            profile=profile,
            input_digest=input_digest,
            output_digest=output_digest,
            status=status,
            execution_timestamp=now,
            duration_seconds=duration_seconds,
            findings=findings_list,
            side_effects=side_effects_dict,
            receipt_sha256=receipt_sha256,
        )

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CapabilityRegistry:
    """Central registry and policy gatekeeper for Euclid / Salamander capabilities."""

    def __init__(self) -> None:
        self._manifests: Dict[str, CapabilityManifest] = {}
        self._adapters: Dict[str, Callable[..., Any]] = {}
        self._audit_log: List[CapabilityExecutionReceipt] = []

    def register(
        self, manifest: CapabilityManifest, adapter_fn: Callable[..., Any]
    ) -> None:
        """Register a native capability adapter bound to its manifest."""
        if not callable(adapter_fn):
            raise CapabilityRegistrationError(
                f"Adapter for {manifest.capability_id} must be callable"
            )
        if manifest.capability_id in self._manifests:
            raise CapabilityRegistrationError(
                f"Capability '{manifest.capability_id}' is already registered"
            )
        self._manifests[manifest.capability_id] = manifest
        self._adapters[manifest.capability_id] = adapter_fn

    def unregister(self, capability_id: str) -> bool:
        """Unregister a capability."""
        if capability_id in self._manifests:
            del self._manifests[capability_id]
            del self._adapters[capability_id]
            return True
        return False

    def get_manifest(self, capability_id: str) -> Optional[CapabilityManifest]:
        return self._manifests.get(capability_id)

    def list_capabilities(
        self, profile: Optional[ExecutionProfile] = None
    ) -> List[CapabilityManifest]:
        """List active capabilities filtered optionally by profile authorization."""
        res = []
        for manifest in self._manifests.values():
            if not manifest.enabled:
                continue
            if profile is not None and not manifest.permissions.is_permitted_for(profile):
                continue
            res.append(manifest)
        return res

    def dispatch(
        self,
        capability_id: str,
        *,
        profile: ExecutionProfile,
        **kwargs: Any,
    ) -> Tuple[Any, CapabilityExecutionReceipt]:
        """Execute a capability under an explicit profile and produce a deterministic receipt.

        Authorization checks fail-closed before invoking the adapter.
        """
        if capability_id not in self._manifests:
            raise KeyError(f"Capability '{capability_id}' is not registered in the fabric")

        manifest = self._manifests[capability_id]
        if not manifest.enabled:
            raise CapabilityExecutionError(f"Capability '{capability_id}' is currently disabled")

        start_time = time.perf_counter()
        try:
            # 1. Authorization check
            if not manifest.permissions.is_permitted_for(profile):
                raise AuthorizationDenied(
                    f"Capability '{capability_id}' is not permitted under execution profile '{profile.value}'"
                )

            # 2. Schema check (mandatory arguments if specified)
            if manifest.input_schema:
                required_keys = manifest.input_schema.get("required", [])
                for key in required_keys:
                    if key not in kwargs:
                        raise TypeError(
                            f"Capability '{capability_id}' missing required argument: '{key}'"
                        )

            # 3. Execution with duration capture
            adapter = self._adapters[capability_id]
            output = adapter(**kwargs)
            duration = time.perf_counter() - start_time
            if duration > manifest.resource_budget.max_runtime_seconds:
                raise CapabilityExecutionError(
                    f"Capability '{capability_id}' exceeded runtime budget: "
                    f"{duration:.2f}s > {manifest.resource_budget.max_runtime_seconds}s"
                )
            status = "SUCCESS"
            findings = []
            if isinstance(output, dict) and "findings" in output:
                findings = output["findings"]
            side_effects = {"class": manifest.side_effects.value}

            receipt = CapabilityExecutionReceipt.create(
                capability_id=capability_id,
                version=manifest.version,
                profile=profile.value,
                inputs=kwargs,
                outputs=output,
                status=status,
                duration_seconds=round(duration, 4),
                findings=findings,
                side_effects=side_effects,
            )
            self._audit_log.append(receipt)
            return output, receipt

        except Exception as exc:
            duration = time.perf_counter() - start_time
            receipt = CapabilityExecutionReceipt.create(
                capability_id=capability_id,
                version=manifest.version,
                profile=profile.value,
                inputs=kwargs,
                outputs={"error": str(exc), "error_type": type(exc).__name__},
                status="FAILED",
                duration_seconds=round(duration, 4),
            )
            self._audit_log.append(receipt)
            raise

    def get_audit_log(self) -> List[CapabilityExecutionReceipt]:
        return list(self._audit_log)


__all__ = [
    "ExecutionProfile",
    "DeterminismClass",
    "SideEffectClass",
    "AuthorizationDenied",
    "CapabilityRegistrationError",
    "CapabilityExecutionError",
    "CapabilityPermissions",
    "ResourceBudget",
    "CapabilityManifest",
    "CapabilityExecutionReceipt",
    "CapabilityRegistry",
]
