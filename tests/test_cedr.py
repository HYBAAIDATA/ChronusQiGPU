"""Executable positive/negative controls; fixture keys are never production trust."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from al_haras.cedr import canonical, evaluate, read_json, validate_registry

NOW = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)
COMMIT = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    key = Ed25519PrivateKey.generate()
    artifact = tmp_path / "candidate.whl"
    artifact.write_bytes(b"isolated fixture, not a real release")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    scope = {
        "environment": "isolated-test",
        "backend": "unit-fixture",
        "hardware": [],
        "fleet": [],
        "tested_scenarios": ["negative-controls"],
    }
    profile = {
        "required_claims": ["CEDR-001"],
        "required_checks": {"CEDR-001": ["fixture-execution"]},
        "max_evidence_age_seconds": 172800,
        "scope": scope,
        "trust_policy": "fixture-policy/1",
        "reviewers": {
            "reviewer": {
                "key_id": "fixture-review",
                "public_key": key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
            }
        },
    }
    claim = {
        "claim_id": "CEDR-001",
        "title": "Test-only qualification",
        "owner": "owner",
        "status": "VERIFIED",
        "claim": "Fixture executes within isolated scope.",
        "scope": scope,
        "candidate": {"commit_sha": COMMIT, "artifact_digest": digest, "build_id": "fixture-build"},
        "evidence": {
            "evidence_package": "evidence.json",
            "package_digest": None,
            "execution_date": (NOW - timedelta(hours=1)).isoformat(),
            "reviewer": "reviewer",
            "retained_until": (NOW + timedelta(days=2)).isoformat(),
        },
        "limitations": {"exclusions": [], "assumptions": [], "unverified_areas": []},
        "decision": {
            "decision_owner": "reviewer",
            "decision": "accepted",
            "decision_date": NOW.isoformat(),
            "risk_acceptance": None,
        },
        "freshness": {
            "last_verified": NOW.isoformat(),
            "expiry": (NOW + timedelta(days=1)).isoformat(),
        },
    }
    package = {
        "schema_version": "cedr.evidence/1",
        "statement": {k: claim[k] for k in ("claim", "title", "owner")},
        "build_id": claim["candidate"]["build_id"],
        "retained_until": claim["evidence"]["retained_until"],
        "claim_id": "CEDR-001",
        "source_commit": COMMIT,
        "artifact_digest": digest,
        "scope": scope,
        "execution_date": claim["evidence"]["execution_date"],
        "review": claim["decision"],
        "freshness": claim["freshness"],
        "limitations": claim["limitations"],
        "checks": [
            {"name": "fixture-execution", "result": "PASS", "execution_reference": "fixture-run/1"}
        ],
    }
    document = {"schema_version": "cedr/1", "profiles": {"test": profile}, "claims": [claim]}
    return document, package, artifact, key


def retain(tmp_path, document, package, key):
    unsigned = {k: v for k, v in package.items() if k != "attestation"}
    package["attestation"] = {
        "reviewer": "reviewer",
        "key_id": "fixture-review",
        "algorithm": "Ed25519",
        "trust_policy": "fixture-policy/1",
        "signature": key.sign(canonical(unsigned)).hex(),
    }
    content = json.dumps(package, sort_keys=True).encode()
    (tmp_path / "evidence.json").write_bytes(content)
    document["claims"][0]["evidence"]["package_digest"] = hashlib.sha256(content).hexdigest()


def result(tmp_path, document, artifact, now=NOW):
    return evaluate(
        document, root=tmp_path, profile_name="test", commit=COMMIT, artifact=artifact, now=now
    )


def test_real_signature_and_scoped_execution_are_eligible(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    retain(tmp_path, document, package, key)
    assert result(tmp_path, document, artifact)["eligible"] is True


@pytest.mark.parametrize("status", ["PROPOSED", "UNVERIFIED", "INVALIDATED", "STALE", "SUPERSEDED"])
def test_nonqualified_claims_cannot_promote(tmp_path, status):
    document, package, artifact, key = fixture(tmp_path)
    document["claims"][0]["status"] = status
    retain(tmp_path, document, package, key)
    assert not result(tmp_path, document, artifact)["eligible"]


@pytest.mark.parametrize("state", ["FAIL", "ERROR", "SKIP", "NOT_RUN"])
def test_nonpassing_execution_is_never_a_pass(tmp_path, state):
    document, package, artifact, key = fixture(tmp_path)
    package["checks"][0]["result"] = state
    retain(tmp_path, document, package, key)
    report = result(tmp_path, document, artifact)
    assert not report["eligible"]
    if state in ["FAIL", "ERROR"]:
        assert report["claims"][0]["effective_status"] == "INVALIDATED"


def test_expired_evidence_is_stale(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    retain(tmp_path, document, package, key)
    report = result(tmp_path, document, artifact, NOW + timedelta(days=1))
    assert not report["eligible"]
    assert report["claims"][0]["effective_status"] == "STALE"


@pytest.mark.parametrize(
    "mutation",
    [
        "artifact",
        "package",
        "signature",
        "reviewer",
        "scope",
        "commit",
        "review",
        "future",
        "empty-checks",
        "duplicate-checks",
    ],
)
def test_substitution_and_missing_evidence_fail_closed(tmp_path, mutation):
    document, package, artifact, key = fixture(tmp_path)
    claim = document["claims"][0]
    if mutation == "empty-checks":
        package["checks"] = []
    elif mutation == "duplicate-checks":
        package["checks"] *= 2
    elif mutation == "future":
        claim["evidence"]["execution_date"] = (NOW + timedelta(days=1)).isoformat()
        package["execution_date"] = claim["evidence"]["execution_date"]
    retain(tmp_path, document, package, key)
    if mutation == "artifact":
        artifact.write_bytes(b"substituted artifact")
    elif mutation == "package":
        (tmp_path / "evidence.json").write_text("{}")
    elif mutation == "signature":
        package["attestation"]["signature"] = "00" * 64
        raw = json.dumps(package).encode()
        (tmp_path / "evidence.json").write_bytes(raw)
        claim["evidence"]["package_digest"] = hashlib.sha256(raw).hexdigest()
    elif mutation == "reviewer":
        document["profiles"]["test"]["reviewers"] = {}
    elif mutation == "scope":
        document["profiles"]["test"]["scope"] = {**claim["scope"], "environment": "production"}
    elif mutation == "commit":
        claim["candidate"]["commit_sha"] = "b" * 40
    elif mutation == "review":
        claim["decision"] = {**claim["decision"], "decision_owner": "unapproved-reviewer"}
    assert not result(tmp_path, document, artifact)["eligible"]


def test_conditionally_verified_needs_signed_current_risk_approval(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    claim = document["claims"][0]
    claim["status"] = "CONDITIONALLY VERIFIED"
    claim["decision"]["decision"] = "accepted_with_limitations"
    claim["decision"]["risk_acceptance"] = {
        "approved_by": "reviewer",
        "rationale": "fixture scope only",
        "expiry": (NOW + timedelta(hours=2)).isoformat(),
    }
    package["review"] = claim["decision"]
    retain(tmp_path, document, package, key)
    assert result(tmp_path, document, artifact)["eligible"]
    assert not result(tmp_path, document, artifact, NOW + timedelta(hours=3))["eligible"]


def test_unapproved_conditional_claim_cannot_promote(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    document["claims"][0]["status"] = "CONDITIONALLY VERIFIED"
    retain(tmp_path, document, package, key)
    assert not result(tmp_path, document, artifact)["eligible"]


def test_registry_has_all_claims_but_no_invented_qualification(tmp_path):
    document = read_json(ROOT / "governance/cedr.json")
    assert validate_registry(document) == []
    assert len(document["claims"]) == 23
    assert all(c["status"] in ["PROPOSED", "UNVERIFIED"] for c in document["claims"])
    artifact = tmp_path / "candidate.whl"
    artifact.write_bytes(b"fixture")
    report = evaluate(
        document,
        root=tmp_path,
        profile_name="pilot-operations",
        commit=COMMIT,
        artifact=artifact,
        now=NOW,
    )
    assert not report["eligible"]
    assert len(report["claims"]) == 19


def test_duplicate_keys_and_unknown_profiles_fail_closed(tmp_path):
    path = tmp_path / "duplicated.json"
    path.write_text('{"eligible":true,"eligible":false}')
    with pytest.raises(ValueError):
        read_json(path)
    document, package, artifact, key = fixture(tmp_path)
    report = evaluate(
        document, root=tmp_path, profile_name="unknown", commit=COMMIT, artifact=artifact, now=NOW
    )
    assert not report["eligible"]


def test_removed_required_claim_cannot_turn_green(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    document["claims"] = []
    assert validate_registry(document)
    assert not result(tmp_path, document, artifact)["eligible"]


def test_unsigned_retention_extension_is_rejected(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    retain(tmp_path, document, package, key)
    document["claims"][0]["evidence"]["retained_until"] = (NOW + timedelta(days=90)).isoformat()
    assert not result(tmp_path, document, artifact)["eligible"]


def test_missing_freshness_policy_cannot_promote(tmp_path):
    document, package, artifact, key = fixture(tmp_path)
    document["profiles"]["test"]["max_evidence_age_seconds"] = None
    retain(tmp_path, document, package, key)
    assert not result(tmp_path, document, artifact)["eligible"]


@pytest.mark.parametrize("policy", [None, [], ["missing-scenario"]])
def test_signed_pass_does_not_replace_required_acceptance_scenarios(tmp_path, policy):
    document, package, artifact, key = fixture(tmp_path)
    document["profiles"]["test"]["required_checks"]["CEDR-001"] = policy
    retain(tmp_path, document, package, key)
    assert not result(tmp_path, document, artifact)["eligible"]


@pytest.mark.parametrize("malformation", ["claim-id", "status", "required-id"])
def test_malformed_policy_types_fail_closed(malformation):
    document = read_json(ROOT / "governance/cedr.json")
    if malformation == "claim-id":
        document["claims"][0]["claim_id"] = []
    elif malformation == "status":
        document["claims"][0]["status"] = {}
    else:
        document["profiles"]["pilot-operations"]["required_claims"] = [[]]
    assert validate_registry(document)


@pytest.mark.parametrize("field", ["claim", "title", "owner"])
def test_reviewed_claim_cannot_be_reworded_after_signing(tmp_path, field):
    document, package, artifact, key = fixture(tmp_path)
    retain(tmp_path, document, package, key)
    document["claims"][0][field] = "different operational claim"
    assert not result(tmp_path, document, artifact)["eligible"]
