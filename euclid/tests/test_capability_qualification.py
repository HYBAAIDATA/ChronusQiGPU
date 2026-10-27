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
    compute_claim_binding_digest,
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
             claim_binding_digest, independent=True, failures=(), limitations=()):
    record = EvidenceRecord(
        evidence_id=evidence_id,
        check_id=check_id,
        source_revision=revision,
        domain=domain,
        task_scope=task_scope,
        claim_binding_digest=claim_binding_digest,
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


def claim(
    private,
    *,
    conclusions=None,
    acceptance_checks=CHECKS,
    authority_limits=("answer:finite-group-ordering",),
    statement="Assist with finite group ordering",
    evidence_overrides=None,
    extra_evidence=(),
    include_checks=CHECKS,
):
    conclusions = conclusions or (
        ClaimConclusion(
            "bounded-result",
            "The capability solves the declared finite-group task.",
            ("ev-domain-acceptance",),
        ),
    )
    evidence_overrides = evidence_overrides or {}
    specs = [
        {
            "evidence_id": f"ev-{check}",
            "check_id": check,
            **evidence_overrides.get(check, {}),
        }
        for check in include_checks
    ]
    specs.extend(extra_evidence)
    evidence_ids = tuple(spec["evidence_id"] for spec in specs)
    rollback_plan = "Disable the capability and restore the prior qualified revision."
    binding_digest = compute_claim_binding_digest(
        claim_id="claim-01",
        statement=statement,
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
        conclusions=tuple(conclusions),
        evidence_ids=evidence_ids,
        acceptance_checks=tuple(acceptance_checks),
        authority_limits=tuple(authority_limits),
        rollback_plan=rollback_plan,
    )
    records = tuple(
        evidence(
            private,
            **spec,
            claim_binding_digest=binding_digest,
        )
        for spec in specs
    )
    return CapabilityClaim(
        claim_id="claim-01",
        statement=statement,
        source_revision=REVISION,
        domain=DOMAIN,
        task_scope=TASK_SCOPE,
        conclusions=tuple(conclusions),
        evidence=records,
        acceptance_checks=tuple(acceptance_checks),
        authority_limits=tuple(authority_limits),
        rollback_plan=rollback_plan,
    )


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
    candidate = claim(
        private,
        evidence_overrides={
            "domain-acceptance": {"status": EvidenceStatus.REPORTED},
        },
        conclusions=(
            ClaimConclusion(
                "unsupported",
                "No executed support.",
                ("ev-domain-acceptance",),
            ),
        ),
    )

    result = registry.promote(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert result.unavailable_conclusions == ("unsupported",)
    assert registry.events[-1]["action"] == "promotion-refused"


@pytest.mark.parametrize("check_id", ["proxy-reward-exploitation", "negative-transfer"])
def test_known_safety_failure_blocks_promotion_and_is_retained(trust, check_id):
    private, registry = trust
    candidate = claim(
        private,
        evidence_overrides={
            check_id: {
                "outcome": EvidenceOutcome.FAIL,
                "failures": ("observed safety failure",),
            }
        },
    )

    result = registry.promote(candidate)

    assert result.status is QualificationStatus.BLOCKED
    assert "observed safety failure" in result.failures
    assert check_id in result.reasons[0] or any(check_id in item for item in result.reasons)


def test_cross_revision_evidence_cannot_be_substituted(trust):
    private, registry = trust
    candidate = claim(
        private,
        evidence_overrides={
            "domain-acceptance": {"revision": "b" * 40},
        },
    )

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("revision or scope mismatch" in item for item in result.reasons)


def test_evidence_cannot_be_reused_for_reworded_claim_or_conclusion(trust):
    private, registry = trust
    candidate = claim(private)
    changed_conclusion = replace(
        candidate.conclusions[0],
        statement="The capability solves an unrelated task.",
    )
    changed_claim = replace(
        candidate,
        statement="A different capability claim.",
        conclusions=(changed_conclusion,),
    )

    result = registry.evaluate(changed_claim)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("claim binding mismatch" in item for item in result.reasons)
    assert result.unavailable_conclusions == ("bounded-result",)


def test_safety_checks_cannot_be_omitted_from_acceptance(trust):
    private, registry = trust
    candidate = claim(private, acceptance_checks=("domain-acceptance",))

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("missing required acceptance checks" in item for item in result.reasons)


def test_unrelated_check_label_cannot_replace_domain_acceptance(trust):
    private, registry = trust
    unrelated = "unrelated-check"
    candidate = claim(
        private,
        acceptance_checks=(unrelated, "proxy-reward-exploitation", "negative-transfer"),
        include_checks=(unrelated, "proxy-reward-exploitation", "negative-transfer"),
    )

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("domain-acceptance" in item for item in result.reasons)


def test_reported_benchmark_is_preserved_but_does_not_count_as_acceptance(trust):
    private, registry = trust
    candidate = claim(
        private,
        extra_evidence=(
            {
                "evidence_id": "ev-benchmark",
                "check_id": "performance-benchmark",
                "kind": EvidenceKind.BENCHMARK,
                "status": EvidenceStatus.REPORTED,
                "independent": False,
                "limitations": ("historical report; not rerun on this revision",),
            },
        ),
    )

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.PROMOTED
    assert result.limitations == ("historical report; not rerun on this revision",)
    assert "ev-benchmark" not in candidate.conclusions[0].evidence_ids


def test_theorem_claim_requires_formally_verified_theorem_evidence(trust):
    private, registry = trust
    theorem_conclusion = ClaimConclusion(
        "finite-result",
        "The finite-group result follows from a verified theorem.",
        ("ev-theorem",),
        kind=ConclusionKind.THEOREM,
    )
    candidate = claim(
        private,
        conclusions=(theorem_conclusion,),
        extra_evidence=(
            {
                "evidence_id": "ev-theorem",
                "check_id": "formal-proof",
                "kind": EvidenceKind.THEOREM,
                "status": EvidenceStatus.FORMALLY_VERIFIED,
            },
        ),
    )

    assert registry.evaluate(candidate).status is QualificationStatus.PROMOTED

    reported_claim = claim(
        private,
        conclusions=(theorem_conclusion,),
        extra_evidence=(
            {
                "evidence_id": "ev-theorem",
                "check_id": "formal-proof",
                "kind": EvidenceKind.THEOREM,
                "status": EvidenceStatus.REPORTED,
            },
        ),
    )
    result = registry.evaluate(reported_claim)
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
    candidate = claim(private)
    records = list(candidate.evidence)
    records[0] = replace(records[0], summary="tampered")
    candidate = replace(candidate, evidence=tuple(records))

    result = registry.evaluate(candidate)

    assert result.status is QualificationStatus.UNAVAILABLE
    assert any("invalid evidence signature" in item for item in result.reasons)
