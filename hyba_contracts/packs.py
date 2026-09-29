"""Composable industry and assurance pack contracts."""

from __future__ import annotations

import time
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Mapping


class PackType(str, Enum):
    INDUSTRY = "INDUSTRY"
    ASSURANCE = "ASSURANCE"


def semver(value: str) -> tuple[int, int, int]:
    try:
        return tuple(int(x) for x in value.split(".", 2))
    except Exception as exc:
        raise ValueError(f"invalid semantic version: {value}") from exc


@dataclass(frozen=True)
class PackRequirements:
    core_min_version: str
    modules_min: Mapping[str, str] = field(default_factory=dict)
    gates_min: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PackProvides:
    ontology_extension: tuple[dict[str, Any], ...] = ()
    policy_extension: tuple[dict[str, Any], ...] = ()
    controls: tuple[dict[str, Any], ...] = ()
    obligations: tuple[dict[str, Any], ...] = ()
    workflows: tuple[dict[str, Any], ...] = ()
    integrations: tuple[dict[str, Any], ...] = ()
    evidence_templates: tuple[dict[str, Any], ...] = ()
    threat_model_extension: tuple[dict[str, Any], ...] = ()
    benchmark_suite: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class PackManifest:
    pack_id: str
    pack_version: str
    pack_type: PackType
    industries: tuple[str, ...]
    workloads: tuple[str, ...]
    risk_levels: tuple[str, ...]
    sovereignties: tuple[str, ...]
    requires: PackRequirements
    provides: PackProvides
    conflicts_with: tuple[str, ...]
    upgrades_from: tuple[str, ...]
    signature: str
    issuer: str
    issued_at: int
    valid_until: int

    def validate(
        self,
        core_version: str,
        installed_packs: Mapping[str, str],
        module_versions: Mapping[str, str],
        gate_states: Mapping[str, str],
        verify_signature: Callable[["PackManifest"], bool],
        now: int | None = None,
    ) -> None:
        current = int(time.time() if now is None else now)
        if semver(core_version) < semver(self.requires.core_min_version):
            raise ValueError("core version too old")
        if set(self.conflicts_with) & set(installed_packs):
            raise ValueError("pack conflict")
        for module, minimum in self.requires.modules_min.items():
            if module not in module_versions or semver(module_versions[module]) < semver(minimum):
                raise ValueError(f"module requirement: {module}")
        ranks = {
            "RESEARCH": 0,
            "CONTRACTED": 1,
            "REFERENCE": 2,
            "VERIFIED": 3,
            "PILOT": 4,
            "PRODUCTION": 5,
        }
        for gate, minimum in self.requires.gates_min.items():
            if gate not in gate_states or ranks[gate_states[gate]] < ranks[minimum]:
                raise ValueError(f"gate requirement: {gate}")
        if not self.signature or not verify_signature(self):
            raise ValueError("pack signature invalid")
        if self.issued_at > current or self.valid_until <= current:
            raise ValueError("pack outside validity window")


@dataclass(frozen=True)
class ComposedPack:
    ontology: tuple
    policy: tuple
    controls: tuple
    obligations: tuple
    workflows: tuple
    integrations: tuple
    evidence: tuple
    threat_model: tuple
    benchmarks: tuple


def compose(pack: PackManifest, core: Mapping[str, Iterable]) -> ComposedPack:
    p = pack.provides

    def merged(name, extension):
        return tuple(core.get(name, ())) + tuple(extension)

    return ComposedPack(
        merged("ontology", p.ontology_extension),
        merged("policy", p.policy_extension),
        merged("controls", p.controls),
        merged("obligations", p.obligations),
        merged("workflows", p.workflows),
        merged("integrations", p.integrations),
        merged("evidence", p.evidence_templates),
        merged("threat_model", p.threat_model_extension),
        merged("benchmarks", p.benchmark_suite),
    )


@dataclass(frozen=True)
class ControlMapping:
    obligation_id: str
    control_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class AssurancePack:
    pack_id: str
    pack_version: str
    mappings: tuple[ControlMapping, ...]


def emit_gap_report(
    pack: AssurancePack,
    controls: set[str],
    tests: set[str],
    evidence: set[str],
    sign: Callable[[dict], str],
    now: int | None = None,
) -> dict:
    gaps = []
    for m in pack.mappings:
        for label, required, available in (
            ("control_missing", m.control_ids, controls),
            ("test_missing", m.test_ids, tests),
            ("evidence_missing", m.evidence_ids, evidence),
        ):
            missing = sorted(set(required) - available)
            if missing:
                gaps.append({"obligation_id": m.obligation_id, "kind": label, "missing": missing})
    report = {
        "pack": pack.pack_id,
        "version": pack.pack_version,
        "gaps": gaps,
        "generated": int(time.time() if now is None else now),
    }
    report["signature"] = sign(report)
    return report


def financial_services_pack(
    signature: str, issuer: str, issued_at: int, valid_until: int
) -> PackManifest:
    controls = tuple(
        {"id": i, "description": d}
        for i, d in (
            ("FS.C1", "Customer data residency"),
            ("FS.C2", "Dual approval for case export"),
            ("FS.C3", "Immutable audit for report filing"),
            ("FS.C4", "Model approval before deployment"),
            ("FS.C5", "Human-in-loop for high-risk actions"),
        )
    )
    return PackManifest(
        "industry.financial_services",
        "1.0.0",
        PackType.INDUSTRY,
        ("financial_services", "insurance", "capital_markets"),
        ("fraud_detection", "aml", "investigator_agent", "regulatory_reporting"),
        ("regulated", "critical"),
        ("private", "on_prem", "air_gapped"),
        PackRequirements(
            "0.1.0",
            {
                name: "0.1.0"
                for name in (
                    "services.core.object",
                    "services.core.policy",
                    "services.core.proof",
                    "services.guard.identity",
                    "services.guard.keys",
                    "services.evidence",
                    "services.ontology",
                    "services.agent_fabric",
                    "services.model_registry",
                )
            },
            {"identity": "CONTRACTED", "schema": "CONTRACTED"},
        ),
        PackProvides(
            ontology_extension=(
                {"noun": "Customer", "permissions": ["READ", "WRITE", "EXPORT"]},
                {"noun": "Account", "permissions": ["READ", "WRITE"]},
                {"noun": "Transaction", "permissions": ["READ"]},
                {"noun": "Case", "permissions": ["READ", "WRITE", "EXPORT"]},
            ),
            policy_extension=(
                {"id": "transaction_read", "residency": "GB"},
                {"id": "case_export", "dual_approval": True},
                {"id": "report_filing", "immutable_evidence": True},
            ),
            controls=controls,
            obligations=(
                {"id": "UK_GDPR.Art5", "controls": ["FS.C1"]},
                {"id": "FCA.SYSC.8", "controls": ["FS.C2", "FS.C3"]},
                {"id": "DORA.Art9", "controls": ["FS.C3", "FS.C4"]},
                {"id": "ISO_42001.8", "controls": ["FS.C4", "FS.C5"]},
            ),
            workflows=tuple(
                {"id": x}
                for x in (
                    "fraud_alert_to_case",
                    "investigator_agent_review",
                    "regulatory_report_filing",
                )
            ),
            integrations=tuple(
                {"id": x}
                for x in ("core_banking_api", "case_management_system", "regulator_gateway")
            ),
            evidence_templates=tuple(
                {"id": x}
                for x in (
                    "fs.customer_data_access",
                    "fs.case_export_approval",
                    "fs.report_filing_receipt",
                )
            ),
            threat_model_extension=tuple(
                {"id": i, "text": t}
                for i, t in (
                    ("T.FS.1", "Insider case data leakage"),
                    ("T.FS.2", "Model drift in fraud detection"),
                    ("T.FS.3", "Approval bypass via agent tool"),
                )
            ),
            benchmark_suite=tuple(
                {"id": x}
                for x in (
                    "fs.fraud_detection_latency",
                    "fs.investigator_agent_precision",
                    "fs.report_filing_completeness",
                )
            ),
        ),
        (),
        (),
        signature,
        issuer,
        issued_at,
        valid_until,
    )


STARTER_ASSURANCE_PACKS = (
    AssurancePack(
        "assurance.uk_gdpr",
        "1.0.0",
        (
            ControlMapping("UK_GDPR.Art5", ("FS.C1",), ("T.RESIDENCY",), ("E.RESIDENCY",)),
            ControlMapping("UK_GDPR.Art30", ("FS.C3",), ("T.AUDIT",), ("E.AUDIT_CHAIN",)),
            ControlMapping(
                "UK_GDPR.Art32", ("FS.C2", "FS.C3"), ("T.APPROVAL",), ("E.APPROVAL_RECEIPT",)
            ),
        ),
    ),
    AssurancePack(
        "assurance.nist_ai_rmf",
        "1.0.0",
        (
            ControlMapping("NIST.MAP.1", ("FS.C4",), ("T.MODEL_APPROVAL",), ("E.MODEL_CARD",)),
            ControlMapping("NIST.MEAS.1", ("FS.C5",), ("T.HUMAN_LOOP",), ("E.APPROVAL_RECEIPT",)),
            ControlMapping("NIST.MANAGE.1", ("FS.C3",), ("T.INCIDENT",), ("E.INCIDENT_RECORD",)),
        ),
    ),
    AssurancePack(
        "assurance.iso_42001",
        "1.0.0",
        (
            ControlMapping("ISO42001.5", ("FS.C4",), ("T.MODEL_APPROVAL",), ("E.MODEL_CARD",)),
            ControlMapping("ISO42001.8", ("FS.C5",), ("T.HUMAN_LOOP",), ("E.APPROVAL_RECEIPT",)),
        ),
    ),
    AssurancePack(
        "assurance.dora_fca",
        "1.0.0",
        (
            ControlMapping("DORA.Art9", ("FS.C3",), ("T.INCIDENT",), ("E.INCIDENT_RECORD",)),
            ControlMapping(
                "FCA.SYSC.8",
                ("FS.C2", "FS.C3"),
                ("T.APPROVAL", "T.AUDIT"),
                ("E.APPROVAL_RECEIPT", "E.AUDIT_CHAIN"),
            ),
        ),
    ),
)
