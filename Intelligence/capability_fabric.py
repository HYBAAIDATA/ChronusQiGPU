"""Euclid / Salamander Native Capability Fabric.

Extensible capability execution architecture:
- Native capability registration
- Typed manifest contracts (permissions, budgets, profiles, determinism)
- Execution isolation and profile gating (internal research vs shared restricted)
- Deterministic execution receipts binding inputs, outputs, and findings
- Default-deny security model: unequipped or unpermitted actions fail at authorization
"""

from __future__ import annotations

import copy
import os
import math
import marshal
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from threading import RLock
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


def snapshot_json(value: Any) -> Any:
    """Detach exact JSON values; reject lossy coercion at governed boundaries.

    This is a value snapshot, not process isolation or independent attestation.
    """
    def check(item, active):
        if type(item) in (str, int, bool, type(None)):
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise TypeError("finite JSON numbers required")
            return
        if type(item) not in (dict, list):
            raise TypeError("exact JSON values required")
        if id(item) in active:
            raise TypeError("cyclic JSON input")
        active.add(id(item))
        try:
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise TypeError("JSON object keys must be strings")
                children = item.values()
            else:
                children = item
            for child in children:
                check(child, active)
        finally:
            active.remove(id(item))
    check(value, set())
    return json.loads(json.dumps(value, allow_nan=False))


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
                or self.can_execute_code
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
    """Declared envelopes. Runtime duration is checked after return, not preempted.

    This in-process registry does not enforce process isolation or memory limits.
    Executors requiring those controls need an external enforcement boundary.
    """

    max_file_bytes: int = 262144
    max_total_bytes: int = 1048576
    max_findings: int = 128
    max_runtime_seconds: float = 30.0
    max_memory_mb: int = 512


    def __post_init__(self):
        for name in ("max_file_bytes", "max_total_bytes", "max_findings", "max_memory_mb"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise CapabilityRegistrationError(f"{name} must be a positive integer")
        if (type(self.max_runtime_seconds) not in (int, float)
                or not math.isfinite(self.max_runtime_seconds)
                or self.max_runtime_seconds <= 0):
            raise CapabilityRegistrationError("max_runtime_seconds must be finite and positive")
        if self.max_file_bytes > self.max_total_bytes:
            raise CapabilityRegistrationError("max_file_bytes exceeds max_total_bytes")


def _digest_data(val: Any) -> str:
    """Compute deterministic canonical SHA256 digest."""
    return hashlib.sha256(
        json.dumps(val, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


_SCHEMA_KEYS = frozenset({"type", "properties", "required", "additionalProperties",
    "items", "enum", "minimum", "maximum", "minLength", "maxLength", "minItems",
    "maxItems", "description", "title", "default"})
_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def _check_schema(schema, depth=0):
    """Validate the supported schema subset; never silently ignore constraints."""
    if depth > 32 or not isinstance(schema, dict):
        raise CapabilityRegistrationError("schema must be a bounded object")
    if set(schema) - _SCHEMA_KEYS:
        raise CapabilityRegistrationError("unsupported schema keyword")
    if "type" in schema:
        declared = schema["type"]
        kinds = declared if type(declared) is list else [declared]
        if (not kinds or any(type(k) is not str or k not in _TYPES for k in kinds)
                or len(kinds) != len(set(kinds))):
            raise CapabilityRegistrationError("unsupported schema type")
    props = schema.get("properties", {})
    if not isinstance(props, dict) or any(not isinstance(k, str) for k in props):
        raise CapabilityRegistrationError("schema properties must be named")
    required = schema.get("required", [])
    if (not isinstance(required, list) or any(not isinstance(k, str) for k in required)
            or len(required) != len(set(required))):
        raise CapabilityRegistrationError("required must contain distinct names")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise CapabilityRegistrationError("additionalProperties must be boolean")
    for child in props.values():
        _check_schema(child, depth + 1)
    if "items" in schema:
        _check_schema(schema["items"], depth + 1)
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise CapabilityRegistrationError("enum must be a non-empty array")
    for k in ("minLength", "maxLength", "minItems", "maxItems"):
        if k in schema and (type(schema[k]) is not int or schema[k] < 0):
            raise CapabilityRegistrationError(f"invalid schema {k}")
    for k in ("minimum", "maximum"):
        if k in schema and (type(schema[k]) not in (int, float) or not math.isfinite(schema[k])):
            raise CapabilityRegistrationError(f"invalid schema {k}")
    for lo, hi in (("minimum", "maximum"), ("minLength", "maxLength"), ("minItems", "maxItems")):
        if lo in schema and hi in schema and schema[lo] > schema[hi]:
            raise CapabilityRegistrationError("inverted schema bounds")


def _validate_schema(value, schema, path="value"):
    kind = schema.get("type")
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "integer": type(value) is int,
        "number": type(value) in (int, float) and math.isfinite(value),
        "boolean": type(value) is bool, "null": value is None}
    kinds = kind if type(kind) is list else [kind]
    if kind is not None and not any(matches[k] for k in kinds):
        raise TypeError(f"{path} must be {kind}")
    if "enum" in schema and not any(type(value) is type(x) and value == x for x in schema["enum"]):
        raise TypeError(f"{path} is not an allowed value")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise TypeError(f"{path} missing required argument: '{key}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise TypeError(f"{path} has unexpected properties")
        for key, child in props.items():
            if key in value:
                _validate_schema(value[key], child, f"{path}.{key}")
    if isinstance(value, list):
        if "items" in schema:
            for index, item in enumerate(value):
                _validate_schema(item, schema["items"], f"{path}[{index}]")
        for k, op in (("minItems", lambda n, b: n < b), ("maxItems", lambda n, b: n > b)):
            if k in schema and op(len(value), schema[k]):
                raise TypeError(f"{path} violates {k}")
    if isinstance(value, str):
        for k, op in (("minLength", lambda n, b: n < b), ("maxLength", lambda n, b: n > b)):
            if k in schema and op(len(value), schema[k]):
                raise TypeError(f"{path} violates {k}")
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise TypeError(f"{path} is non-finite")
        if "minimum" in schema and value < schema["minimum"]:
            raise TypeError(f"{path} is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise TypeError(f"{path} exceeds maximum")


def _execution_status(output):
    if is_dataclass(output) and not isinstance(output, type):
        output = asdict(output)
    if not isinstance(output, dict):
        return "SUCCESS"
    declared = str(output.get("status", "")).upper()
    if (output.get("success") is False or output.get("executed") is False
            or output.get("error") or declared in {
                "FAILED", "FAILURE", "ERROR", "REFUSED", "DENIED", "UNAVAILABLE", "REJECTED"}):
        raise CapabilityExecutionError("handler returned a failure or refusal outcome")
    if output.get("simulated") is True or declared in {"SIMULATION", "SIMULATED"}:
        return "SIMULATED"
    if declared in {"UNVERIFIED", "GUIDANCE", "PENDING"}:
        return declared
    return "SUCCESS"


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
    """Local hash-bound execution record, not a signature or independent proof.

    Legacy non-JSON arguments use a string projection in the digest. Such a
    projection is not an authenticated binding of callable or filesystem state.
    """

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
        self._registration_lock = RLock()

    def register(
        self, manifest: CapabilityManifest, adapter_fn: Callable[..., Any]
    ) -> None:
        """Register a native capability adapter bound to its manifest."""
        with self._registration_lock:
            if not callable(adapter_fn):
                raise CapabilityRegistrationError(
                    f"Adapter for {manifest.capability_id} must be callable"
                )
            if manifest.capability_id in self._manifests:
                raise CapabilityRegistrationError(
                    f"Capability '{manifest.capability_id}' is already registered"
                )
            if not isinstance(manifest.permissions, CapabilityPermissions):
                raise CapabilityRegistrationError("permissions contract is required")
            for name, value in asdict(manifest.permissions).items():
                if name != "allowed_profiles" and type(value) is not bool:
                    raise CapabilityRegistrationError("permission flags must be boolean")
            profiles = manifest.permissions.allowed_profiles
            if (not isinstance(profiles, tuple) or not profiles
                    or any(not isinstance(x, ExecutionProfile) for x in profiles)):
                raise CapabilityRegistrationError("allowed_profiles must name explicit profiles")
            if not isinstance(manifest.resource_budget, ResourceBudget):
                raise CapabilityRegistrationError("resource budget is required")
            if (not isinstance(manifest.supported_operations, tuple)
                    or not manifest.supported_operations
                    or any(not isinstance(x, str) or not x for x in manifest.supported_operations)
                    or len(set(manifest.supported_operations)) != len(manifest.supported_operations)):
                raise CapabilityRegistrationError("distinct supported operations are required")
            if not isinstance(manifest.side_effects, SideEffectClass):
                raise CapabilityRegistrationError("side-effect contract is required")
            _check_schema(manifest.input_schema)
            _check_schema(manifest.output_schema)
            self._manifests[manifest.capability_id] = copy.deepcopy(manifest)
            self._adapters[manifest.capability_id] = adapter_fn

    def unregister(self, capability_id: str) -> bool:
        """Unregister a capability."""
        with self._registration_lock:
            if capability_id in self._manifests:
                del self._manifests[capability_id]
                del self._adapters[capability_id]
                return True
            return False

    def get_manifest(self, capability_id: str) -> Optional[CapabilityManifest]:
        with self._registration_lock:
            return copy.deepcopy(self._manifests.get(capability_id))

    def list_capabilities(
        self, profile: Optional[ExecutionProfile] = None
    ) -> List[CapabilityManifest]:
        """List active capabilities filtered optionally by profile authorization."""
        with self._registration_lock:
            res = []
            for manifest in self._manifests.values():
                if not manifest.enabled:
                    continue
                if profile is not None and not manifest.permissions.is_permitted_for(profile):
                    continue
                res.append(copy.deepcopy(manifest))
            return res

    def dispatch(
        self,
        capability_id: str,
        *,
        profile: ExecutionProfile,
        _manifest_admission: Optional[Callable[[CapabilityManifest], None]] = None,
        _strict_json: bool = False,
        _audit_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
        **kwargs: Any,
    ) -> Tuple[Any, CapabilityExecutionReceipt]:
        """Execute a capability under an explicit profile and produce a deterministic receipt.

        Authorization checks fail-closed before invoking the adapter.
        """
        # Pair the exact contract with its handler while registration is locked.
        # Execute outside the lock: this is an admission snapshot, not OS
        # isolation or retroactive cancellation of already admitted execution.
        with self._registration_lock:
            manifest = copy.deepcopy(self._manifests.get(capability_id))
            adapter = self._adapters.get(capability_id)
        start_time = time.perf_counter()
        admitted_inputs = kwargs
        execution_id = hashlib.sha256(os.urandom(32)).hexdigest()
        handler_code = getattr(adapter, "__code__", None)
        binding = {"execution_id": execution_id,
                   "manifest_digest": _digest_data(asdict(manifest)) if manifest else None,
                   "handler_name": getattr(adapter, "__qualname__", None),
                   "handler_code_digest": hashlib.sha256(marshal.dumps(handler_code)).hexdigest()
                       if handler_code is not None else None,
                   "handler_binding_scope": "local_python_code_not_closure_or_external_state"}
        try:
            if _strict_json:
                admitted_inputs = snapshot_json(kwargs)
                kwargs = snapshot_json(admitted_inputs)
            if _audit_sink is not None and not callable(_audit_sink):
                raise TypeError("audit sink must be callable")
            if not isinstance(profile, ExecutionProfile):
                raise AuthorizationDenied("explicit ExecutionProfile is required")
            if manifest is None:
                raise KeyError(f"Capability '{capability_id}' is not registered in the fabric")
            if not manifest.enabled:
                raise CapabilityExecutionError(f"Capability '{capability_id}' is currently disabled")
            # 1. Authorization check
            if not manifest.permissions.is_permitted_for(profile):
                raise AuthorizationDenied(
                    f"Capability '{capability_id}' is not permitted under execution profile '{profile.value}'"
                )

            if adapter is None:
                raise CapabilityExecutionError("registered capability handler is unavailable")
            if _manifest_admission is not None:
                if not callable(_manifest_admission):
                    raise TypeError("manifest admission policy must be callable")
                # The policy sees a detached copy and cannot change the contract
                # used for schema validation, budgets, receipts or this handler.
                _manifest_admission(copy.deepcopy(manifest))

            # Validate before protected side effects; reserve the declared input envelope.
            _validate_schema(kwargs, manifest.input_schema, "inputs")
            if len(json.dumps(kwargs, default=str, allow_nan=False).encode()) > manifest.resource_budget.max_total_bytes:
                raise CapabilityExecutionError("input byte envelope exceeded")

            # Durable admission precedes any handler effect. Failure here refuses
            # execution; failure after execution cannot promise rollback.
            if _audit_sink is not None:
                _audit_sink({"kind": "capability-admitted", "execution_id": execution_id,
                    "capability_id": capability_id, "version": manifest.version,
                    "profile": profile.value, "input_digest": _digest_data(admitted_inputs),
                    "binding": binding})

            # 3. Execution with duration capture
            output = adapter(**kwargs)
            duration = time.perf_counter() - start_time
            if duration > manifest.resource_budget.max_runtime_seconds:
                raise CapabilityExecutionError(
                    f"Capability '{capability_id}' exceeded runtime budget: "
                    f"{duration:.2f}s > {manifest.resource_budget.max_runtime_seconds}s"
                )
            if _strict_json:
                output = snapshot_json(output)
            _validate_schema(output, manifest.output_schema, "outputs")
            status = _execution_status(output)
            if len(json.dumps(output, default=str, allow_nan=False).encode()) > manifest.resource_budget.max_total_bytes:
                raise CapabilityExecutionError("output byte envelope exceeded")
            findings = []
            if isinstance(output, dict) and "findings" in output:
                findings = output["findings"]
            if (not isinstance(findings, list) or any(not isinstance(x, dict) for x in findings)
                    or len(findings) > manifest.resource_budget.max_findings):
                raise CapabilityExecutionError("malformed findings or findings budget exceeded")
            side_effects = {"class": manifest.side_effects.value,
                "runtime_enforcement": "post-return", "memory_enforced": False,
                "process_isolated": False, "execution_binding": binding}

            receipt = CapabilityExecutionReceipt.create(
                capability_id=capability_id,
                version=manifest.version,
                profile=profile.value,
                inputs=admitted_inputs,
                outputs=output,
                status=status,
                duration_seconds=round(duration, 4),
                findings=findings,
                side_effects=side_effects,
            )
            if _audit_sink is not None:
                _audit_sink({"kind": "capability-completed", "execution_id": execution_id,
                    "capability_id": capability_id, "status": status,
                    "receipt_sha256": receipt.receipt_sha256,
                    "input_digest": receipt.input_digest, "output_digest": receipt.output_digest})
            self._audit_log.append(copy.deepcopy(receipt))
            return output, receipt

        except Exception as exc:
            duration = time.perf_counter() - start_time
            receipt = CapabilityExecutionReceipt.create(
                capability_id=capability_id,
                version=manifest.version if manifest else "unregistered",
                profile=profile.value if isinstance(profile, ExecutionProfile) else "invalid",
                inputs=admitted_inputs,
                outputs={"error": str(exc), "error_type": type(exc).__name__},
                status="FAILED",
                duration_seconds=round(duration, 4),
            )
            self._audit_log.append(copy.deepcopy(receipt))
            if callable(_audit_sink):
                try:
                    _audit_sink({"kind": "capability-failed", "execution_id": execution_id,
                        "capability_id": capability_id, "error_type": type(exc).__name__,
                        "receipt_sha256": receipt.receipt_sha256})
                except Exception as audit_exc:
                    exc.add_note("durable failure audit unavailable: " + type(audit_exc).__name__)
            raise

    def get_audit_log(self) -> List[CapabilityExecutionReceipt]:
        return copy.deepcopy(self._audit_log)


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
