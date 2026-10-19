"""Explicit canonical EUCLID -> existing Intelligence registry binding.

No automatic rights, guardian, provider, signer, learner, registry or executor is
created here. Mutation/external-effect capabilities need their owner's enforced
execution boundary and are refused by this in-process read-only integration.
"""
from __future__ import annotations

import re

from typing import Mapping

from Intelligence.capability_fabric import (
    AuthorizationDenied, CapabilityRegistry, ExecutionProfile, SideEffectClass, snapshot_json,
)


class IntelligenceSpecialist:
    """Dispatch the configured registry; never accept caller-supplied profiles."""

    def __init__(self, registry, *, profile, capabilities, audit_sink=None):
        if not isinstance(registry, CapabilityRegistry):
            raise TypeError("existing CapabilityRegistry is required")
        if not isinstance(profile, ExecutionProfile):
            raise TypeError("explicit ExecutionProfile is required")
        names = tuple(capabilities)
        if not names or len(set(names)) != len(names) or any(not isinstance(x, str) or not x for x in names):
            raise ValueError("distinct capability identifiers are required")
        self.audit_sink = audit_sink
        self.registry = registry
        self.profile = profile
        self.capabilities = frozenset(names)
        for name in names:
            self._admit(name)

    def _admit(self, name, manifest=None):
        if manifest is None:
            manifest = self.registry.get_manifest(name)
        if manifest is None or not manifest.enabled:
            raise AuthorizationDenied("capability missing or disabled")
        permissions = manifest.permissions
        external = any(getattr(permissions, field) for field in (
            "can_write_repository", "can_execute_code", "can_spawn_process", "can_use_network",
            "can_install_dependency", "can_modify_configuration", "can_access_credentials",
            "can_invoke_recovery", "can_mutate_capability_registry"))
        if (manifest.side_effects is not SideEffectClass.READ_ONLY or external
                or not permissions.is_permitted_for(self.profile)):
            raise AuthorizationDenied("capability requires a separately enforced execution boundary")

    def catalog(self):
        """Describe this host binding, never infer qualification from registration."""
        rows = []
        for name in sorted(self.capabilities):
            manifest = self.registry.get_manifest(name)
            try:
                self._admit(name, manifest)
                available, reason = True, "BOUND_REQUIRES_RUNTIME_AUTHORIZATION"
            except AuthorizationDenied as exc:
                available, reason = False, str(exc)
            rows.append({"capability_id": name, "available": available,
                         "version": manifest.version if manifest else None,
                         "profile": self.profile.value, "reason": reason,
                         "input_schema": manifest.input_schema if manifest else None,
                         "output_schema": manifest.output_schema if manifest else None,
                         "independently_qualified": False})
        return rows

    def handle(self, request: Mapping):
        if set(request) - {"operation", "arguments"}:
            raise ValueError("unexpected Intelligence request fields")
        name = request.get("operation")
        if name not in self.capabilities:
            raise AuthorizationDenied("capability not bound to this specialist")
        arguments = request.get("arguments", {})
        if not isinstance(arguments, dict) or any(not isinstance(x, str) for x in arguments):
            raise TypeError("arguments must be a JSON object")
        # No callbacks, provider handles or filesystem object stringification at
        # the governed boundary. Authorization sees the same JSON request.
        arguments = snapshot_json(arguments)
        self._admit(name)  # Preserve explicit refusal for missing/disabled bindings.
        # Recheck admission against the atomic contract/handler pair used by
        # dispatch, not an earlier live lookup that can race with registration.
        output, receipt = self.registry.dispatch(
            name, profile=self.profile, _strict_json=True, _audit_sink=self.audit_sink,
            _manifest_admission=lambda manifest: self._admit(name, manifest),
            **arguments,
        )
        return {"executed": receipt.status == "SUCCESS", "status": receipt.status,
                "capability_id": name, "output": output, "receipt": receipt.as_dict(),
                "independently_qualified": False}


def bind_intelligence(runtime, registry, *, profile, capabilities, organ_id="intelligence"):
    """Register through the canonical runtime without granting dispatch rights.

    The caller must configure the existing AL HARAS guardian, its policy and
    entitlement and explicitly grant creator-scoped rights before dispatching
    with runtime.dispatch_specialist. Binding alone is never authorization.
    """
    from .runtime import EuclidRuntime

    if not isinstance(runtime, EuclidRuntime):
        raise TypeError("canonical EuclidRuntime is required")
    if runtime._closed:
        raise RuntimeError("runtime is closed")
    if type(organ_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", organ_id) is None:
        raise ValueError("organ_id must be a bounded path-free identifier")
    from al_haras import HashChainAudit
    audit = HashChainAudit(runtime.state_dir / "intelligence" / (organ_id + ".jsonl"))
    specialist = IntelligenceSpecialist(registry, profile=profile, capabilities=capabilities,
                                       audit_sink=audit.append)
    runtime.register_specialist(organ_id, specialist, operations=specialist.capabilities)
    runtime.evidence.append("intelligence-registry-bound", {
        "organ": organ_id, "profile": profile.value,
        "capabilities": sorted(specialist.capabilities), "rights_granted": False,
    })
    return specialist
