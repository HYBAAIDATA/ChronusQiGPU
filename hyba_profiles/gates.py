from __future__ import annotations
from .model import AssemblyIntent, GateCheck, GateReport, GateStatus
from .profiles import PROFILES
from .registry import MODULE_REGISTRY


def evaluate(intent: AssemblyIntent) -> GateReport:
    if intent.deployment_profile not in PROFILES:
        raise ValueError("unknown deployment profile")
    spec = PROFILES[intent.deployment_profile]
    selected = set(intent.modules)
    evidence = {item.module: item for item in intent.module_evidence}
    checks: list[GateCheck] = []
    def add(name: str, passed: bool, required: bool, detail: str):
        checks.append(GateCheck(name, passed, required, detail))
    add("dominant_tiers", tuple(intent.dominant_tiers) == spec.dominant_tiers, True, f"expected {[t.value for t in spec.dominant_tiers]}")
    for module in sorted(spec.required_modules):
        add(f"module:{module}", module in selected, True, "required by profile")
        item = evidence.get(module)
        add(f"source:{module}", bool(item and item.source_verified), True, "source verification required")
        add(f"tests:{module}", bool(item and item.tests_passed), True, "executed tests required")
    for module in sorted(spec.prohibited_modules & selected):
        add(f"prohibited:{module}", False, True, "research-gated or prohibited in this profile")
    add("silent_fallback_disabled", not intent.silent_fallback, True, "backend changes must be explicit")
    if spec.requires_customer_keys: add("customer_managed_keys", intent.customer_managed_keys, True, "profile requirement")
    if spec.requires_local_identity: add("local_identity_provider", intent.local_identity_provider, True, "profile requirement")
    if spec.requires_air_gap: add("air_gapped", intent.air_gapped, True, "profile requirement")
    if spec.requires_private_networking: add("private_networking", intent.private_networking, True, "profile requirement")
    if spec.requires_human_approval: add("human_approval", intent.human_approval_for_high_risk_actions, True, "profile requirement")
    blockers = tuple(check.name for check in checks if check.required and not check.passed)
    assessments = tuple(spec.external_assessments)
    if blockers: status = GateStatus.REJECTED
    elif assessments: status = GateStatus.EXTERNAL_ASSESSMENT_REQUIRED
    else: status = GateStatus.ACCEPTED
    return GateReport(spec.name, status, tuple(checks), blockers, assessments)


def assert_promotion(source: GateReport, target: GateReport) -> None:
    if source.status not in {GateStatus.ACCEPTED, GateStatus.EXTERNAL_ASSESSMENT_REQUIRED}:
        raise ValueError("source profile has not passed its gate")
    if target.blockers:
        raise ValueError("target profile requires new evidence")
