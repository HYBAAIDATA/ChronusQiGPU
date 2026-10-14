"""Explicit canonical EUCLID -> existing Intelligence registry binding.

No automatic rights, guardian, provider, signer, learner, registry or executor is
created here. Mutation/external-effect capabilities need their owner's enforced
execution boundary and are refused by this in-process read-only integration.
"""
from __future__ import annotations

import json
from typing import Mapping

from Intelligence.capability_fabric import (
    AuthorizationDenied, CapabilityRegistry, ExecutionProfile, SideEffectClass,
)


class IntelligenceSpecialist:
    """Dispatch the configured registry; never accept caller-supplied profiles."""

    def __init__(self, registry, *, profile, capabilities):
        if not isinstance(registry, CapabilityRegistry):
            raise TypeError("existing CapabilityRegistry is required")
        if not isinstance(profile, ExecutionProfile):
            raise TypeError("explicit ExecutionProfile is required")
        names = tuple(capabilities)
        if not names or len(set(names)) != len(names) or any(not isinstance(x, str) or not x for x in names):
            raise ValueError("distinct capability identifiers are required")
        self.registry = registry
        self.profile = profile
        self.capabilities = frozenset(names)
        for name in names:
            self._admit(name)

    def _admit(self, name):
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
        json.dumps(arguments, allow_nan=False)
        self._admit(name)  # Recheck live registration, enablement and permissions.
        output, receipt = self.registry.dispatch(name, profile=self.profile, **arguments)
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
    if not isinstance(organ_id, str) or not organ_id or "." in organ_id:
        raise ValueError("organ_id must be a non-empty undotted identifier")
    specialist = IntelligenceSpecialist(registry, profile=profile, capabilities=capabilities)
    runtime.register_specialist(organ_id, specialist, operations=specialist.capabilities)
    runtime.evidence.append("intelligence-registry-bound", {
        "organ": organ_id, "profile": profile.value,
        "capabilities": sorted(specialist.capabilities), "rights_granted": False,
    })
    return specialist
