"""Claim–Evidence–Decision qualification; integrity is not factual correctness."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

STATUSES = {
    "PROPOSED",
    "VERIFIED",
    "CONDITIONALLY VERIFIED",
    "UNVERIFIED",
    "INVALIDATED",
    "STALE",
    "SUPERSEDED",
}
READY = {"VERIFIED", "CONDITIONALLY VERIFIED"}
RESULTS = {"PASS", "FAIL", "SKIP", "NOT_RUN", "ERROR"}
MAX_BYTES = 4 * 1024 * 1024
REQUIRED = {
    "claim_id",
    "title",
    "owner",
    "status",
    "claim",
    "scope",
    "candidate",
    "evidence",
    "limitations",
    "decision",
    "freshness",
}
NESTED = {
    "scope": {"environment", "backend", "hardware", "fleet", "tested_scenarios"},
    "candidate": {"commit_sha", "artifact_digest", "build_id"},
    "evidence": {
        "evidence_package",
        "package_digest",
        "execution_date",
        "reviewer",
        "retained_until",
    },
    "limitations": {"exclusions", "assumptions", "unverified_areas"},
    "decision": {"decision_owner", "decision", "decision_date", "risk_acceptance"},
    "freshness": {"last_verified", "expiry"},
}


def canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("oversized evidence")
    return json.loads(
        path.read_text(),
        object_pairs_hook=unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )


def validate_registry(document: dict) -> list[str]:
    errors = []
    if not isinstance(document, dict) or document.get("schema_version") != "cedr/1":
        return ["unsupported CEDR schema"]
    claims = document.get("claims")
    profiles = document.get("profiles")
    if not isinstance(claims, list) or not claims or not isinstance(profiles, dict) or not profiles:
        return ["claims and profiles must be nonempty"]
    ids = set()
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("invalid claim record")
            continue
        identifier = claim.get("claim_id")
        if not isinstance(identifier, str) or not re.fullmatch(r"CEDR-[0-9]{3}", identifier):
            errors.append("invalid claim identity")
        elif identifier in ids:
            errors.append(f"{identifier}: duplicate claim")
        if isinstance(identifier, str):
            ids.add(identifier)
        if (
            not REQUIRED <= claim.keys()
            or not isinstance(claim.get("status"), str)
            or claim["status"] not in STATUSES
        ):
            errors.append(f"{identifier}: missing fields or invalid status")
        for key, fields in NESTED.items():
            value = claim.get(key)
            if not isinstance(value, dict) or not fields <= value.keys():
                errors.append(f"{identifier}: incomplete {key} structure")
    for name, profile in profiles.items():
        required = profile.get("required_claims") if isinstance(profile, dict) else None
        if (
            not isinstance(required, list)
            or not required
            or any(not isinstance(x, str) for x in required)
            or len(set(required)) != len(required)
            or not set(required) <= ids
        ):
            errors.append(f"{name}: invalid required-claim policy")
        if not isinstance(profile, dict) or not isinstance(profile.get("reviewers"), dict):
            errors.append(f"{name}: missing reviewer trust policy")
    return errors


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def verify_package(package: dict, profile: dict, reviewer: str) -> None:
    attestation = package.get("attestation", {})
    trusted = profile["reviewers"].get(reviewer)
    if not isinstance(trusted, dict):
        raise ValueError("reviewer is not authorized by trust policy")
    if (
        attestation.get("reviewer") != reviewer
        or attestation.get("algorithm") != "Ed25519"
        or attestation.get("key_id") != trusted.get("key_id")
        or attestation.get("trust_policy") != profile.get("trust_policy")
    ):
        raise ValueError("attestation identity or policy mismatch")
    unsigned = {k: v for k, v in package.items() if k != "attestation"}
    try:
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted["public_key"]))
        public.verify(bytes.fromhex(attestation["signature"]), canonical(unsigned))
    except (InvalidSignature, KeyError, ValueError, TypeError) as exc:
        raise ValueError("invalid evidence signature") from exc


def qualify(
    claim: dict, profile: dict, root: Path, commit: str, artifact_digest: str, now: datetime
) -> dict:
    identifier = claim["claim_id"]
    stated = claim["status"]
    row = {
        "claim_id": identifier,
        "declared_status": stated,
        "effective_status": stated,
        "eligible": False,
        "reason": "claim is not qualified",
    }
    if stated not in READY:
        return row
    try:
        if not claim["owner"] or not claim["claim"] or not claim["title"]:
            raise ValueError("missing claim ownership or statement")
        candidate, evidence, decision, freshness = (
            claim[k] for k in ("candidate", "evidence", "decision", "freshness")
        )
        if candidate["commit_sha"] != commit or candidate["artifact_digest"] != artifact_digest:
            raise ValueError("candidate commit or artifact mismatch")
        if not candidate["build_id"]:
            raise ValueError("missing build identity")
        requested_scope = profile.get("scope")
        if not requested_scope or any(v is None for v in requested_scope.values()):
            raise ValueError("intended operating scope is not approved")
        if claim["scope"] != requested_scope:
            raise ValueError("claim does not cover the exact intended scope")
        if not all(isinstance(claim["limitations"][k], list) for k in NESTED["limitations"]):
            raise ValueError("limitations must be explicit lists")
        relative = Path(evidence["evidence_package"])
        path = (root / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not path.is_relative_to(root.resolve())
        ):
            raise ValueError("evidence path escapes custody root")
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != evidence["package_digest"]:
            raise ValueError("evidence package missing or tampered")
        package = read_json(path)
        verify_package(package, profile, evidence["reviewer"])
        if (
            package.get("schema_version") != "cedr.evidence/1"
            or package.get("claim_id") != identifier
            or package.get("source_commit") != commit
            or package.get("artifact_digest") != artifact_digest
            or package.get("scope") != claim["scope"]
        ):
            raise ValueError("signed evidence identity mismatch")
        statement = {k: claim[k] for k in ("claim", "title", "owner")}
        if package.get("statement") != statement:
            raise ValueError("reviewed claim statement differs from register")
        if (
            package.get("review") != decision
            or package.get("execution_date") != evidence["execution_date"]
        ):
            raise ValueError("review or execution date differs from signed evidence")
        if (
            package.get("freshness") != freshness
            or package.get("limitations") != claim["limitations"]
        ):
            raise ValueError("freshness or limitations differ from signed evidence")
        if (
            package.get("build_id") != candidate["build_id"]
            or package.get("retained_until") != evidence["retained_until"]
        ):
            raise ValueError("build identity or custody differs from signed evidence")
        executed = timestamp(evidence["execution_date"])
        reviewed = timestamp(freshness["last_verified"])
        expiry = timestamp(freshness["expiry"])
        retained = timestamp(evidence["retained_until"])
        if not executed <= reviewed <= now or expiry <= reviewed or retained < expiry:
            raise ValueError("invalid execution, review or custody window")
        maximum_age = profile.get("max_evidence_age_seconds")
        if type(maximum_age) is not int or maximum_age <= 0:
            raise ValueError("freshness threshold is not approved")
        if expiry > executed + timedelta(seconds=maximum_age):
            raise ValueError("evidence exceeds approved freshness threshold")
        if now >= expiry or now >= retained:
            row.update(effective_status="STALE", reason="evidence expired or custody expired")
            return row
        checks = package.get("checks")
        if (
            not isinstance(checks, list)
            or not checks
            or any(
                not isinstance(c, dict)
                or not isinstance(c.get("name"), str)
                or not c["name"]
                or c.get("result") not in RESULTS
                or not c.get("execution_reference")
                for c in checks
            )
        ):
            raise ValueError("missing executed check evidence")
        required_checks = profile.get("required_checks", {}).get(identifier)
        if (
            not isinstance(required_checks, list)
            or not required_checks
            or any(not isinstance(x, str) or not x for x in required_checks)
            or len(set(required_checks)) != len(required_checks)
            or not set(required_checks) <= {c["name"] for c in checks}
        ):
            raise ValueError("required acceptance scenarios are not covered")
        if len({c["name"] for c in checks}) != len(checks):
            raise ValueError("duplicate check evidence")
        if any(c["result"] in {"FAIL", "ERROR"} for c in checks):
            row.update(effective_status="INVALIDATED", reason="executed validation failed")
            return row
        if any(c["result"] != "PASS" for c in checks):
            raise ValueError("SKIP or NOT_RUN cannot qualify required validation")
        if decision["decision_owner"] != evidence["reviewer"]:
            raise ValueError("decision owner does not match authenticated reviewer")
        if timestamp(decision["decision_date"]) != reviewed:
            raise ValueError("decision date differs from qualification review")
        if stated == "CONDITIONALLY VERIFIED":
            risk = decision["risk_acceptance"]
            if (
                decision["decision"] != "accepted_with_limitations"
                or not isinstance(risk, dict)
                or risk.get("approved_by") != evidence["reviewer"]
                or not risk.get("rationale")
                or timestamp(risk.get("expiry")) <= now
                or timestamp(risk["expiry"]) > expiry
            ):
                raise ValueError("conditional scope needs signed, current risk approval")
        elif decision["decision"] != "accepted":
            raise ValueError("qualified claim lacks an accepting decision")
        row.update(eligible=True, reason="signed, retained, current evidence covers intended scope")
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        row.update(
            effective_status="UNVERIFIED", reason="missing or invalid qualification contract"
        )
    return row


def evaluate(
    document: dict,
    *,
    root: Path,
    profile_name: str,
    commit: str,
    artifact: Path,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    errors = validate_registry(document)
    rows = []
    digest = None
    try:
        if errors or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("invalid registry or candidate")
        profile = document["profiles"][profile_name]
        path = artifact.resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("candidate artifact is missing or outside custody root")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        by_id = {c["claim_id"]: c for c in document["claims"]}
        rows = [
            qualify(by_id[i], profile, root, commit, digest, now)
            for i in profile["required_claims"]
        ]
    except (OSError, ValueError, KeyError, TypeError):
        errors.append("candidate, profile or registry is not qualified")
    return {
        "schema_version": "cedr.decision/1",
        "profile": profile_name,
        "source_commit": commit,
        "artifact_digest": digest,
        "evaluated_at": now.isoformat(),
        "claims": rows,
        "errors": errors,
        "eligible": bool(rows) and not errors and all(r["eligible"] for r in rows),
        "qualification_note": "Signatures prove integrity/provenance under policy, not factual correctness.",
    }
