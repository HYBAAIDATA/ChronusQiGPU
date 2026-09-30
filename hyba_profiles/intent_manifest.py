"""C1 — User -> Assembly Compiler: the IntentManifest transport.

Loads the spec's `apiVersion: hyba.ai/v1, kind: PlatformAssembly` YAML
manifest and produces an `AssemblyIntent` for `compile_assembly`. Every
rejection carries the spec's failure-mode reasons — unknown capability,
incompatible modules, silent fallback, missing residency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Mapping

import yaml

from .model import AssemblyIntent
from .profiles import PROFILES
from .registry import MODULE_REGISTRY

API_VERSION = "hyba.ai/v1"
KIND = "PlatformAssembly"


class IntentRejected(ValueError):
    def __init__(self, reasons: tuple[str, ...]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


def _require(mapping: Mapping[str, Any], key: str, where: str, reasons: list[str]) -> Any:
    value = mapping.get(key)
    if value in (None, "", (), []):
        reasons.append(f"missing required {where}.{key}")
    return value


def _string_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    if value in (None, ""):
        return ()
    return (str(value),)


def intent_manifest_dict(document: Mapping[str, Any]) -> AssemblyIntent:
    """Validate one parsed manifest document and return the AssemblyIntent."""
    reasons: list[str] = []
    if document.get("apiVersion") != API_VERSION:
        reasons.append(f"apiVersion must be {API_VERSION}")
    if document.get("kind") != KIND:
        reasons.append(f"kind must be {KIND}")
    metadata = document.get("metadata") or {}
    intent = document.get("intent") or {}
    name = _require(metadata, "name", "metadata", reasons)
    seed = _require(metadata, "deploymentSeed", "metadata", reasons)

    industry = _require(intent, "industry", "intent", reasons)
    use_cases = _string_list(intent.get("useCases"))
    if not use_cases:
        reasons.append("missing required intent.useCases")
    scale = intent.get("scale") or {}
    profile = _require(scale, "profile", "intent.scale", reasons)
    if profile is not None and profile not in PROFILES:
        reasons.append(f"unsupported scale.profile {profile!r} (profiles: {sorted(PROFILES)})")

    risk = intent.get("risk") or {}
    risk_level = _require(risk, "level", "intent.risk", reasons)  # I4

    data = intent.get("data") or {}
    residency = _string_list(data.get("residency"))
    if not residency:
        reasons.append("missing required intent.data.residency")  # I2/F4
    exactness = _require(data, "exactness", "intent.data", reasons)  # I3

    execution = intent.get("execution") or {}
    if execution.get("silentFallback", False):
        reasons.append("silentFallback requested: prohibited")  # I1/F3

    capabilities = intent.get("capabilities") or {}
    capability_modules = {str(k): _string_list(v) for k, v in capabilities.items()}
    unknown = sorted(set(use_cases) - MODULE_REGISTRY.keys() - capability_modules.keys())
    if unknown:
        reasons.append(f"unknown capabilities: {','.join(unknown)}")  # I5/F1
    resolved = set()
    bad_refs = []
    for uc in use_cases:
        targets = capability_modules.get(uc, (uc,) if uc in MODULE_REGISTRY else ())
        missing = sorted(set(targets) - MODULE_REGISTRY.keys())
        bad_refs.extend(missing)
        resolved.update(set(targets) & MODULE_REGISTRY.keys())
    if bad_refs:
        reasons.append(f"capabilities map to unknown modules: {','.join(sorted(set(bad_refs)))}")
    incompatible = sorted(set(resolved) & set(_string_list(intent.get("incompatibleModules"))))
    if incompatible:
        reasons.append(f"incompatible modules: {','.join(incompatible)}")  # F2

    modules = _string_list(intent.get("modules")) or tuple(sorted(resolved))

    if not modules:
        reasons.append("no modules resolved from useCases/capabilities")
    if reasons:
        raise IntentRejected(tuple(reasons))

    availability = intent.get("availability") or {}
    economics = intent.get("economics") or {}
    security = intent.get("security") or {}
    spec = PROFILES[str(profile)]
    resilience = str(availability.get("recoveryTime") or availability.get("target") or "standard")
    from .model import ModuleEvidence

    evidence = tuple(
        ModuleEvidence(
            module=str(e.get("module", "")),
            version=str(e.get("version", "")),
            source_verified=bool(e.get("source_verified", False)),
            tests_passed=bool(e.get("tests_passed", False)),
            deployment_verified=bool(e.get("deployment_verified", False)),
            external_assessment=bool(e.get("external_assessment", False)),
            evidence_refs=_string_list(e.get("evidence_refs")),
        )
        for e in (intent.get("moduleEvidence") or [])
    )
    return AssemblyIntent(
        name=str(name),
        deployment_profile=str(profile),
        deployment_seed=str(seed),
        industry=str(industry),
        use_cases=use_cases,
        risk_level=str(risk_level),
        sovereignty=str(residency[0]),
        exactness=str(exactness),
        resilience=resilience,
        economics=_string_list(economics.get("optimiseFor")),
        modules=modules,
        module_evidence=evidence,
        dominant_tiers=spec.dominant_tiers,
        customer_managed_keys=bool(security.get("customerManagedKeys", False)),
        private_networking=bool(security.get("privateNetworking", False)),
        human_approval_for_high_risk_actions=bool(
            security.get("humanApprovalForHighRiskActions", False)
        ),
        silent_fallback=False,
    )


def load_intent_manifest(source: str | Path | Mapping[str, Any]) -> AssemblyIntent:
    """Load an IntentManifest from a YAML file, YAML string, or parsed mapping."""
    if isinstance(source, Mapping):
        document = source
    else:
        text = (
            Path(source).read_text(encoding="utf-8") if Path(str(source)).exists() else str(source)
        )
        document = yaml.safe_load(text)
    if not isinstance(document, Mapping):
        raise IntentRejected(("manifest is not a YAML mapping",))
    return intent_manifest_dict(document)


__all__ = [name for name in globals() if not name.startswith("_")]
