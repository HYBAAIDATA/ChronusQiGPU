"""Evidence-bound capability promotion tests."""

from dataclasses import replace
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from euclid.capability_qualification import (
    CapabilityClaim,
    CapabilityQualificationRegistry,
    ClaimConclusion,
    ConclusionKind,
    EvidenceKind,
    EvidenceOutcome,
    EvidenceRecord,
    EvidenceStatus,
    QualificationStatus,
)


REVISION = "a" * 40
DOMAIN = "proof-assistance"
TASK_SCOPE = "finite-group-ordering"
CHECKS = (
    "domain-acceptance",
    "proxy-reward-exploitation",
    "negative-transfer",
)


@pytest.fixture
def trust():
    private = Ed25519PrivateKey.generate()
    return private, CapabilityQualificationRegistry(
        trusted_verifiers={"independent-lab": private.public_key()}
    )


def evidence(private, evidence_id, check_id, *, kind=EvidenceKind.TEST,
             status=EvidenceStatus.EXECUTED, outcome=EvidenceOutcome.PASS,
             revision=REVISION, domain=DOMAIN, task_scope=TASK_SCOPE,
             independent=True, failures=(), limitations=()):
    record = EvidenceRecord(
        evidence_id=evidence_id,
        check_id=check_id,
        source_revision=revision,
        domain=domain,
        task_scope=task_scope,
        kind=kind,
        status=status,
        outcome=outcome,
        artifact_sha256=hashlib.sha256(evidence_id.encode()).hexdigest(),
        verifier_id="independent-lab",
        independent=independent,
        summary=f"Result for {check_id}",
        failures=tuple(failures),
        limitations=tuple(limitations),
    )
    return replace(record, signature=private.sign(record.body()).hex())


def claim(private, **changes):
    records = tuple(
        evidence(private, f"ev-{check}", check)
        for check in CHECKS
    )
    base = CapabilityClaim(
        claim_id="claim-01",
        statement="Assist with finite group ordering",
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
        conclusions=(
            ClaimConclusion(
                "bounded-result",
                "The capability solves the declared finite-group task.",
                ("ev-domain-acceptance",),
            ),
        ),
        evidence=records,
        acceptance_checks=CHECKS,
        authority_limits=("answer:finite-group-ordering",),
        rollback_plan="Disable the capability and restore the prior qualified revision.",
    )
    return replace(base, **changes)


def test_independent_scoped_evidence_promotes_and_authorizes_only_declared_scope(trust):
    private, registry = trust
    candidate = claim(private)

    result = registry.promote(candidate)

    assert result.status is QualificationStatus.PROMOTED
    assert registry.status(
        claim_id=candidate.claim_id,
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
    ) is QualificationStatus.PROMOTED
    assert registry.authorize(
        claim_id=candidate.claim_id,
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
        authority="answer:finite-group-ordering",
    )
    with pytest.raises(PermissionError):
        registry.authorize(
            claim_id=candidate.claim_id,
            source_revision=REVISION,
            domain="code-generation",
            task_scope=TASK_SCOPE,
            authority="answer:finite-group-ordering",
        )
    with pytest.raises(PermissionError):
        registry.authorize(
            claim_id=candidate.claim_id,
            source_revision=REVISION,
            domain=DOMAIN,
            task_scope=TASK_SCOPE,
            authority="write:repository",
        )


def test_reported_results_and_unsupported_conclusions_are_unavailable(trust):
    private, registry = trust
    records = list(claim(private).evidence)
    records[0] = evidence(
        private,
        "ev-domain-acceptance",
        "domain-acceptance",
        status=EvidenceStatus.REPORTED,
    )
    candidate = claim(
        private,
        evidence=tuple(records),
        conclusions=(
            ClaimConclusion("unsupported", "No executed support.", ("ev-domain-acceptance",)),
        ),
    )

    result = registry.promote(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert result.unavailable_conclusions == ("unsupported",)
    assert registry.events[-1]["action"] == "promotion-refused"


@pytest.mark.parametrize("check_id", ["proxy-reward-exploitation", "negative-transfer"])
def test_known_safety_failure_blocks_promotion_and_is_retained(trust, check_id):
    private, registry = trust
    records = list(claim(private).evidence)
    index = CHECKS.index(check_id)
    records[index] = evidence(
        private,
        f"ev-{check_id}",
        check_id,
        outcome=EvidenceOutcome.FAIL,
        failures=("observed safety failure",),
    )

    result = registry.promote(claim(private, evidence=tuple(records)))

    assert result.status is QualificationStatus.BLOCKED
    assert "observed safety failure" in result.failures
    assert check_id in result.reasons[0] or any(check_id in item for item in result.reasons)


def test_cross_revision_evidence_cannot_be_substituted(trust):
    private, registry = trust
    records = list(claim(private).evidence)
    records[0] = evidence(
        private,
        "ev-domain-acceptance",
        "domain-acceptance",
        revision="b" * 40,
    )

    result = registry.evaluate(claim(private, evidence=tuple(records)))

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("revision or scope mismatch" in item for item in result.reasons)


def test_safety_checks_cannot_be_omitted_from_acceptance(trust):
    private, registry = trust
    candidate = claim(private, acceptance_checks=("domain-acceptance",))

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("missing required safety checks" in item for item in result.reasons)


def test_reported_benchmark_is_preserved_but_does_not_count_as_acceptance(trust):
    private, registry = trust
    records = claim(private).evidence + (
        evidence(
            private,
            "ev-benchmark",
            "performance-benchmark",
            kind=EvidenceKind.BENCHMARK,
            status=EvidenceStatus.REPORTED,
            independent=False,
            limitations=("historical report; not rerun on this revision",),
        ),
    )
    candidate = claim(private, evidence=records)

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.PROMOTED
    assert result.limitations == ("historical report; not rerun on this revision",)
    assert "ev-benchmark" not in candidate.conclusions[0].evidence_ids


def test_theorem_claim_requires_formally_verified_theorem_evidence(trust):
    private, registry = trust
    theorem = evidence(
        private,
        "ev-theorem",
        "formal-proof",
        kind=EvidenceKind.THEOREM,
        status=EvidenceStatus.FORMALLY_VERIFIED,
    )
    candidate = claim(
        private,
        conclusions=(
            ClaimConclusion(
                "finite-result",
                "The finite-group result follows from a verified theorem.",
                ("ev-theorem",),
                kind=ConclusionKind.THEOREM,
            ),
        ),
        evidence=claim(private).evidence + (theorem,),
    )

    assert registry.evaluate(candidate).status is QualificationStatus.PROMOTED

    reported = replace(
        theorem,
        status=EvidenceStatus.REPORTED,
        signature="",
    )
    reported = replace(reported, signature=private.sign(reported.body()).hex())
    candidate = replace(candidate, evidence=claim(private).evidence + (reported,))
    result = registry.evaluate(candidate)
    assert result.status is QualificationStatus.UNAVAILABLE
    assert result.unavailable_conclusions == ("finite-result",)


def test_revocation_removes_authority_and_records_rollback_plan(trust):
    private, registry = trust
    candidate = claim(private)
    registry.promote(candidate)

    registry.revoke(
        claim_id=candidate.claim_id,
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
        reason="post-release divergence",
    )

    with pytest.raises(PermissionError):
        registry.authorize(
            claim_id=candidate.claim_id,
            source_revision=REVISION,
            domain=DOMAIN,
            task_scope=TASK_SCOPE,
            authority="answer:finite-group-ordering",
        )
    assert registry.events[-1]["action"] == "revoked"
    assert candidate.rollback_plan in registry.events[-1]["rollback_plan"]
    assert registry.status(
        claim_id=candidate.claim_id,
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
    ) is QualificationStatus.REVOKED
    assert registry.promote(candidate).status is QualificationStatus.REVOKED


def test_tampered_attestation_is_not_accepted(trust):
    private, registry = trust
    records = list(claim(private).evidence)
    records[0] = replace(records[0], summary="tampered")

    result = registry.evaluate(claim(private, evidence=tuple(records)))

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("invalid evidence signature" in item for item in result.reasons)
