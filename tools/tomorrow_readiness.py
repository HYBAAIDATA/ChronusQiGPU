"""Evidence-scoped readiness index. Standard library only; never release approval.

Run: python -m tools.tomorrow_readiness --template > assessment.json
     python -m tools.tomorrow_readiness --input assessment.json --evidence-root .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

SCHEMA = "hyba.tomorrow-readiness.v1"
RECEIPT_SCHEMA = "hyba.readiness.check.v1"
MAX_FILE_BYTES = 8 * 1024 * 1024
_UNSET = object()


class MaturityLevel(IntEnum):
    ABSENT = 0
    EXPERIMENTING = 1
    DEVELOPING = 2
    DEPLOYING = 3
    OPTIMISED = 4


class Priority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


# Criterion weights are equal within each area: the supplied specification did
# not assign them. Every criterion requires evidence; silence scores zero.
AREAS = (
    (
        "ai",
        "AI infrastructure",
        0.25,
        (
            (
                "C1.1",
                "aiExperimentsSupported",
                "BOOL",
                "Execute an AI experiment on the target deployment.",
            ),
            (
                "C1.2",
                "aiProductionSupported",
                "BOOL",
                "Exercise TOE/intelligence end to end with workload-bound receipts.",
            ),
            (
                "C1.3",
                "dedicatedDataPlatform",
                "BOOL",
                "Bind and exercise the data platform and custody path.",
            ),
            (
                "C1.4",
                "secureConnections",
                "BOOL",
                "Verify authenticated connections and measured latency.",
            ),
            (
                "C1.5",
                "gpuComputeCapacity",
                "METRIC",
                "Measure actual device execution and headroom against demand; a ceiling is not throughput.",
            ),
            (
                "C1.6",
                "mlOpsPipelines",
                "SCALE_1_5",
                "Exercise training, deployment, rollback and revision-bound verification.",
            ),
            (
                "C1.7",
                "dataGovernanceForAI",
                "SCALE_1_5",
                "Verify lineage, quality, tenant isolation and access controls.",
            ),
        ),
    ),
    (
        "cyber",
        "Cyber security",
        0.20,
        (
            (
                "C2.1",
                "controlsDefinedForCritical",
                "BOOL",
                "Map controls to each critical service and threat model.",
            ),
            (
                "C2.2",
                "controlsTestedRegularly",
                "BOOL",
                "Execute scoped security tests and retain findings and logs.",
            ),
            (
                "C2.3",
                "segmentation",
                "SCALE_1_5",
                "Exercise network and workload isolation including denial cases.",
            ),
            (
                "C2.4",
                "identityAndAccess",
                "SCALE_1_5",
                "Test least privilege, authorization expiry and fail-closed denial.",
            ),
            (
                "C2.5",
                "incidentResponseTested",
                "BOOL",
                "Execute and time an incident response exercise.",
            ),
            (
                "C2.6",
                "thirdPartyRisk",
                "SCALE_1_5",
                "Assess suppliers, credentials, dependencies and response obligations.",
            ),
        ),
    ),
    (
        "resilience",
        "Resilience and business continuity",
        0.20,
        (
            (
                "C3.1",
                "continuityPlanExists",
                "BOOL",
                "Document service continuity and recovery ownership.",
            ),
            (
                "C3.2",
                "rtoRpoDefined",
                "BOOL",
                "Define and measure service-specific RTO and RPO.",
            ),
            (
                "C3.3",
                "supplierDisruptionCovered",
                "BOOL",
                "Exercise supplier outage and recovery without silent fallback.",
            ),
            (
                "C3.4",
                "failoverTested",
                "BOOL",
                "Inject failure and prove failover and Salamander recovery on the target.",
            ),
            (
                "C3.5",
                "redundancy",
                "SCALE_1_5",
                "Demonstrate independent replica/site failure survival.",
            ),
            (
                "C3.6",
                "observability",
                "SCALE_1_5",
                "Verify alerts and audit joins for successful and failed work.",
            ),
        ),
    ),
    (
        "sovereignty",
        "Sovereignty and compliance",
        0.20,
        (
            (
                "C4.1",
                "dataResidencyKnown",
                "BOOL",
                "Inventory actual primary and replica data locations.",
            ),
            (
                "C4.2",
                "regulatedDataClassified",
                "BOOL",
                "Classify sensitive data and enforce handling rules.",
            ),
            (
                "C4.3",
                "controlDemonstrable",
                "BOOL",
                "Retrieve authentic, tenant-bound custody and control evidence.",
            ),
            (
                "C4.4",
                "crossBorderTransferGoverned",
                "SCALE_1_5",
                "Test transfer rules against actual workload locations.",
            ),
            (
                "C4.5",
                "backupLocationProven",
                "BOOL",
                "Prove backup location, access and successful restore.",
            ),
            (
                "C4.6",
                "regulatoryAlignment",
                "SCALE_1_5",
                "Obtain scoped regulatory review; an index is not compliance certification.",
            ),
        ),
    ),
    (
        "energy",
        "Energy, sustainability and scaling",
        0.15,
        (
            (
                "C5.1",
                "powerHeadroom",
                "METRIC",
                "Measure available power against forecast demand with explicit units and targets.",
            ),
            (
                "C5.2",
                "capacityHeadroom",
                "METRIC",
                "Measure limiting compute, memory, storage and space headroom.",
            ),
            (
                "C5.3",
                "costProjection",
                "SCALE_1_5",
                "Model and validate growth costs against measured consumption.",
            ),
            (
                "C5.4",
                "sustainabilityTargets",
                "SCALE_1_5",
                "Set and measure energy/carbon targets with defined boundaries.",
            ),
            (
                "C5.5",
                "preemptiveCapacityPlanning",
                "BOOL",
                "Record capacity decisions before constraints are reached.",
            ),
            (
                "C5.6",
                "scalingRunway",
                "METRIC",
                "Measure runway in months against a documented growth forecast.",
            ),
        ),
    ),
)
QUESTIONS = {
    "ai": "Can infrastructure support AI as demand moves from experimentation to production?",
    "cyber": "Are controls tested across infrastructure supporting critical services?",
    "resilience": "Can services continue and recover when infrastructure or suppliers are disrupted?",
    "sovereignty": "Do you know where regulated data sits and can you demonstrate control?",
    "energy": "Can infrastructure grow without power, capacity, cost or sustainability becoming constraints?",
}

CRITERIA = {c[0]: c for _, _, _, criteria in AREAS for c in criteria}
GATES = (
    "regression_suite",
    "docker_e2e",
    "gpu_execution",
    "pool_acceptance",
    "failover",
    "custody",
    "toe_end_to_end",
    "salamander_recovery",
    "release_artifacts",
)
GATE_CHECKS = {
    "regression_suite": (
        "tests_executed",
        "zero_failures",
        "zero_errors",
        "required_suites_complete",
    ),
    "docker_e2e": (
        "image_built",
        "container_started",
        "mounts_verified",
        "services_exercised",
        "health_checked",
    ),
    "gpu_execution": (
        "device_identified",
        "device_work_executed",
        "result_independently_checked",
    ),
    "pool_acceptance": (
        "share_submitted",
        "pool_acceptance_observed",
        "acceptance_bound_to_work",
    ),
    "failover": ("failure_injected", "automatic_recovery", "work_resumed"),
    "custody": ("authenticated_custody", "lineage_verified", "reconciliation_passed"),
    "toe_end_to_end": (
        "plan_bound_to_work",
        "execution_observed",
        "learning_receipt_verified",
    ),
    "salamander_recovery": (
        "fault_injected",
        "recovery_executed",
        "state_integrity_verified",
    ),
    "release_artifacts": (
        "artifacts_built",
        "metadata_checked",
        "boundary_checked",
        "installed_smoke_passed",
    ),
}

CONTEXTS = (
    "connectivity",
    "residency_control",
    "capacity_planning",
    "ai_demand_pressure",
)
# Directed source -> target constraints, not duplicate incoming/outgoing arrows.
DEPENDENCIES = (
    ("cyber", "resilience", "SUPPORT", 0.6),
    ("cyber", "sovereignty", "SUPPORT", 0.4),
    ("context.connectivity", "resilience", "SUPPORT", 0.6),
    ("context.residency_control", "sovereignty", "SUPPORT", 0.7),
    ("context.capacity_planning", "energy", "SUPPORT", 0.6),
    ("context.ai_demand_pressure", "energy", "PRESSURE", 0.7),
)
CRITICAL = {"C1.4", "C2.1", "C2.4", "C2.5", "C3.2", "C3.4", "C4.3", "C4.5", "C5.1"}


def strict_loads(data: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def number(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def stamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return dt.astimezone(timezone.utc)


def maturity(score: float) -> str:
    return MaturityLevel(min(4, max(0, int(score // 20)))).name


def bounded_file(root: Path, relative: str) -> bytes:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("evidence path must be relative")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()):
        raise ValueError("evidence path escapes evidence root")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("evidence file exceeds size limit")
    return data


def evidence_status(
    ref: Any,
    subject: str,
    document: dict,
    root: Path,
    now: datetime,
    measurement: Any = _UNSET,
) -> tuple[bool, str]:
    """Validate a locally approved verifier receipt; NOT independent attestation.

    Hashing proves byte identity only. Verifier allowlisting is deployment policy,
    not cryptographic authentication. Existing signed custody verification must
    happen in the producing verifier; this assessor never replaces it.
    """
    if not isinstance(ref, str) or ref not in document["evidence"]:
        return False, "missing_evidence"
    try:
        item = document["evidence"][ref]
        data = bounded_file(root, item["path"])
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            return False, "digest_mismatch"
        receipt = strict_loads(data)
        if receipt.get("schema") != RECEIPT_SCHEMA:
            return False, "unsupported_receipt_schema"
        expected = {
            "subject": subject,
            **{k: document[k] for k in ("source_revision", "offering", "environment")},
        }
        if any(receipt.get(k) != v for k, v in expected.items()):
            return False, "scope_mismatch"
        if receipt.get("verifier_id") not in document["policy"]["approved_verifiers"]:
            return False, "verifier_not_approved"
        age = (now - stamp(receipt["observed_at"])).total_seconds()
        if age < 0 or age > document["policy"]["max_evidence_age_seconds"]:
            return False, "stale_or_future_evidence"
        checks = receipt.get("checks")
        if (
            receipt.get("status") != "PASS"
            or not isinstance(checks, dict)
            or not checks
        ):
            return False, "check_not_passed"
        if not all(isinstance(k, str) and k and v is True for k, v in checks.items()):
            return False, "check_not_passed"
        if subject.startswith("gate."):
            required = GATE_CHECKS.get(subject[5:], ())
            if not required or not all(checks.get(k) is True for k in required):
                return False, "required_checks_missing"
        if measurement is not _UNSET:
            if measurement.get("value") is None or json.dumps(
                receipt.get("measurement"), sort_keys=True, allow_nan=False
            ) != json.dumps(measurement, sort_keys=True, allow_nan=False):
                return False, "measurement_mismatch"
        return True, "local_receipt_validated"
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False, "invalid_evidence"


def normalise(criterion: tuple, answer: dict) -> float:
    value = answer.get("value")
    if value is None:
        return 0.0
    kind = criterion[2]
    if kind == "BOOL":
        if not isinstance(value, bool):
            raise ValueError(f"{criterion[0]} requires true or false")
        return float(value)
    raw = number(value, criterion[0])
    if kind == "SCALE_1_5":
        if raw < 1 or raw > 5 or not raw.is_integer():
            raise ValueError(f"{criterion[0]} requires an integer from 1 to 5")
        return raw / 5
    threshold = answer.get("threshold")
    if (
        not isinstance(threshold, dict)
        or not isinstance(threshold.get("unit"), str)
        or not threshold["unit"].strip()
    ):
        raise ValueError(f"{criterion[0]} requires metric unit, worst and target")
    worst = number(threshold.get("worst"), "worst")
    target = number(threshold.get("target"), "target")
    if target == worst:
        raise ValueError("metric target must differ from worst")
    return min(1.0, max(0.0, (raw - worst) / (target - worst)))


def validate(document: dict) -> None:
    if document.get("schema") != SCHEMA:
        raise ValueError("unsupported assessment schema")
    for key in ("source_revision", "offering", "environment"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise ValueError(f"{key} is required")
    for key in ("answers", "context", "evidence", "gates", "policy"):
        if not isinstance(document.get(key), dict):
            raise ValueError(f"{key} must be an object")
    for key, allowed in (
        ("answers", CRITERIA),
        ("context", CONTEXTS),
        ("gates", GATES),
    ):
        unknown = set(document[key]) - set(allowed)
        if unknown:
            raise ValueError(f"unknown {key}: {sorted(unknown)}")
        if not all(isinstance(v, dict) for v in document[key].values()):
            raise ValueError(f"{key} entries must be objects")
    policy = document["policy"]
    if number(policy.get("max_evidence_age_seconds"), "max_evidence_age_seconds") <= 0:
        raise ValueError("evidence age must be positive")
    approved = policy.get("approved_verifiers")
    if not isinstance(approved, list) or not all(
        isinstance(v, str) and v.strip() for v in approved
    ):
        raise ValueError("approved_verifiers must be a list of non-empty identifiers")
    profile = document.get("profile", {})
    if not isinstance(profile, dict) or set(profile) - {
        "sector",
        "organisation_size",
        "infrastructure_mix",
    }:
        raise ValueError(
            "profile supports sector, organisation_size and infrastructure_mix"
        )
    if not all(isinstance(v, str) for v in profile.values()):
        raise ValueError("profile values must be strings")
    risks = document.get("accepted_risks", [])
    if not isinstance(risks, list) or not all(isinstance(v, str) for v in risks):
        raise ValueError("accepted_risks must be a list of strings")


def assess(document: dict, evidence_root: Path, now: datetime | None = None) -> dict:
    validate(document)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("assessment time must include timezone")
    sections, gaps, base, verified_count = [], [], {}, 0
    for area_id, name, weight, criteria in AREAS:
        results = []
        for criterion in criteria:
            cid, description, _, remediation = criterion
            answer = document["answers"].get(cid, {})
            raw = normalise(criterion, answer)
            bound = {k: answer[k] for k in ("value", "threshold") if k in answer}
            verified, reason = evidence_status(
                answer.get("evidence"), cid, document, evidence_root, now, bound
            )
            score = raw * (1 if verified else 0.5)
            verified_count += int(verified)
            results.append(
                {
                    "id": cid,
                    "name": description,
                    "raw_score": raw * 100,
                    "score": score * 100,
                    "verified": verified,
                    "evidence_status": reason,
                }
            )
            if score < 0.6 or not verified:
                severity = (
                    Priority.CRITICAL
                    if cid in CRITICAL
                    else (
                        Priority.HIGH
                        if area_id in ("cyber", "resilience", "sovereignty", "ai")
                        else Priority.MEDIUM
                    )
                )
                phase = (
                    1
                    if severity == Priority.CRITICAL
                    or area_id in ("cyber", "resilience")
                    else (
                        2
                        if area_id == "sovereignty"
                        or cid in ("C1.3", "C5.2", "C5.5", "C5.6")
                        else 3
                    )
                )
                gaps.append(
                    {
                        "area_id": area_id,
                        "criterion_id": cid,
                        "severity": severity.name,
                        "priority": int(severity),
                        "phase": phase,
                        "remediation": remediation,
                        "reason": reason if not verified else "below_threshold",
                        "leverage": sum(
                            s for src, _, _, s in DEPENDENCIES if src == area_id
                        ),
                    }
                )
        base[area_id] = sum(c["score"] for c in results) / len(results)
        sections.append(
            {
                "id": area_id,
                "name": name,
                "question": QUESTIONS[area_id],
                "weight": weight,
                "base_score": base[area_id],
                "criteria": results,
            }
        )
    context, context_results = {}, []
    for name in CONTEXTS:
        answer = document["context"].get(name, {})
        value = answer.get("value")
        if value is not None and not 0 <= number(value, name) <= 100:
            raise ValueError("context values must be between zero and 100")
        verified, reason = evidence_status(
            answer.get("evidence"),
            f"context.{name}",
            document,
            evidence_root,
            now,
            {"value": value},
        )
        pressure = name == "ai_demand_pressure"
        effective = float(value) if verified else 100.0 if pressure else 0.0
        context[f"context.{name}"] = effective
        context_results.append(
            {
                "id": name,
                "verified": verified,
                "evidence_status": reason,
                "effective_value": effective,
            }
        )
    # Synchronous updates anchored to original evidence scores. A supporting
    # area can constrain, never award evidence credit. Missing demand = maximum
    # pressure, not free headroom. No repeated accumulation or in-place ordering.
    adjusted, passes = dict(base), 0
    for passes in range(1, 4):
        next_scores = dict(base)
        sources = {**adjusted, **context}
        for source, target, direction, strength in DEPENDENCIES:
            influence = sources[source] / 100
            factor = (
                1 - strength * (1 - influence)
                if direction == "SUPPORT"
                else 1 - strength * influence
            )
            next_scores[target] *= factor
        delta = max(abs(next_scores[k] - adjusted[k]) for k in base)
        adjusted = next_scores
        if delta < 1e-9:
            break
    for section in sections:
        exact = adjusted[section["id"]]
        section.update(score=round(exact, 1), maturity=maturity(exact))
    gates = []
    for gate in GATES:
        item = document["gates"].get(gate, {})
        ok, reason = evidence_status(
            item.get("evidence"), f"gate.{gate}", document, evidence_root, now
        )
        gates.append(
            {
                "id": gate,
                "status": "PASS" if ok else "NOT_ESTABLISHED",
                "evidence_status": reason,
            }
        )
        if not ok:
            gaps.append(
                {
                    "area_id": "qualification",
                    "criterion_id": f"gate.{gate}",
                    "severity": "CRITICAL",
                    "priority": 1,
                    "phase": 1,
                    "leverage": 1.0,
                    "reason": reason,
                    "remediation": f"Execute and retain scoped {gate} verification on the target.",
                }
            )
    for item in context_results:
        if not item["verified"]:
            gaps.append(
                {
                    "area_id": "context",
                    "criterion_id": f"context.{item['id']}",
                    "severity": "HIGH",
                    "priority": 2,
                    "phase": 2,
                    "leverage": 0.7,
                    "reason": item["evidence_status"],
                    "remediation": f"Measure and verify {item['id']} in the deployment scope.",
                }
            )
    gaps.sort(
        key=lambda g: (g["phase"], g["priority"], -g["leverage"], g["criterion_id"])
    )
    composite = sum(adjusted[a["id"]] * a["weight"] for a in sections)
    return {
        "schema": SCHEMA,
        "generated_at": now.isoformat(),
        **{k: document[k] for k in ("source_revision", "offering", "environment")},
        "organisation_profile": document.get("profile", {}),
        "model": "user-supplied Telehouse-inspired framework; not a Telehouse certification",
        "evidence_assurance": "local hash/scope/time/measurement/allowlist checks; not independent attestation",
        "policy": document["policy"],
        "areas": sections,
        "context": context_results,
        "composite_score": round(composite, 1),
        "overall_maturity": maturity(composite),
        "verified_criteria": verified_count,
        "criterion_count": len(CRITERIA),
        "evidence_coverage_percent": round(100 * verified_count / len(CRITERIA), 1),
        "dependency_passes": passes,
        "dependency_policy": "anchored multiplicative constraints; no evidence uplift",
        "qualification_gates": gates,
        "qualification_evidence_complete": all(g["status"] == "PASS" for g in gates),
        "production_qualification": "not_established_by_this_assessment",
        "accepted_risks": document.get("accepted_risks", []),
        "risk_acceptance_changes_scores": False,
        "gaps": gaps,
        "roadmap": [
            {"phase": n, "items": [g for g in gaps if g["phase"] == n]}
            for n in range(1, 5)
        ],
        "assessment_passed": not gaps,
    }


def template() -> dict:
    return {
        "schema": SCHEMA,
        "source_revision": "REPLACE_WITH_ACTUAL_REVISION",
        "offering": "REPLACE_WITH_OFFERING",
        "environment": "REPLACE_WITH_TARGET",
        "profile": {"sector": "", "organisation_size": "", "infrastructure_mix": ""},
        "policy": {"approved_verifiers": [], "max_evidence_age_seconds": 86400},
        "answers": {cid: {"value": None, "evidence": None} for cid in CRITERIA},
        "context": {name: {"value": None, "evidence": None} for name in CONTEXTS},
        "evidence": {},
        "gates": {gate: {"evidence": None} for gate in GATES},
        "accepted_risks": [],
    }


def runtime_observation(path: Path) -> dict:
    """Read-only adapter: a readiness probe is observation, never gate evidence."""
    data = bounded_file(path.parent, path.name)
    probe = strict_loads(data)
    if (
        not isinstance(probe, dict)
        or probe.get("schema_version") != "chronus.mla1517.ready/1"
    ):
        raise ValueError("unsupported runtime probe schema")
    components = probe.get("components", {})
    if not isinstance(components, dict):
        raise ValueError("probe components must be an object")
    allowed = (
        "boot_audit",
        "custody",
        "guardian",
        "identity",
        "m3_authorization",
        "remote_opencl",
        "runtime_config",
        "stratum",
        "worker_heartbeat_dir",
    )
    states = {}
    for name in allowed:
        item = components.get(name, {})
        state = item.get("state") if isinstance(item, dict) else None
        if state in (
            "ready",
            "not_ready",
            "not_configured",
            "connected",
            "disconnected",
        ):
            states[name] = state
    return {
        "schema": "hyba.runtime-probe-observation.v1",
        "probe_sha256": hashlib.sha256(data).hexdigest(),
        "reported_ready": probe.get("ready") is True,
        "scope": probe.get("scope")
        if probe.get("scope") in ("control_plane", "submission")
        else "unspecified",
        "component_states": states,
        "qualification_credit": False,
        "current_liveness_established": False,
        "note": "File snapshot only; probe HTTP success is not end-to-end qualification.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--evidence-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--runtime-probe",
        type=Path,
        help="Optional saved runtime probe; observation only",
    )
    args = parser.parse_args(argv)
    try:
        if args.template:
            payload, exit_code = template(), 0
        elif args.input:
            with args.input.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("input exceeds size limit")
            document = strict_loads(data)
            if not isinstance(document, dict):
                raise ValueError("input must be an object")
            payload = assess(document, args.evidence_root)
            if args.runtime_probe:
                payload["runtime_observation"] = runtime_observation(args.runtime_probe)
            exit_code = 0 if payload["assessment_passed"] else 1
        else:
            parser.error("--input or --template is required")
        text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return exit_code
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"assessment error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
