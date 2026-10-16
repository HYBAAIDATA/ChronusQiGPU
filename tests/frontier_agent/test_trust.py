from dataclasses import replace
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.trust import TrustLevel, trust_transition
from chronus.agent.assurance import AssuranceLevel


def test_no_forged_promotion(qualification, identity, task):
    s, r, a, g, k = qualification
    d = trust_transition(
        identity,
        task,
        TrustLevel.OBSERVE,
        r.metrics,
        a,
        now=2,
        expires_at=7000,
        thresholds=s.thresholds,
        verifier_keys=s.verifier_keys,
    )
    with pytest.raises(ContractError):
        s.trust.apply(
            replace(d, to_level=TrustLevel.OWN),
            task,
            2,
            identity=identity,
            metrics=r.metrics,
            attestation=a,
            thresholds=s.thresholds,
            verifier_keys=s.verifier_keys,
        )


def test_target_level_assurance(qualification, identity, task):
    s, r, a, g, k = qualification
    from chronus.agent.capabilities import RiskTier

    task = replace(task, risk_tier=RiskTier.T0_SANDBOX)
    metrics = replace(r.metrics, task_key=task.key)
    bad = replace(a, task_key=task.key, level=AssuranceLevel.SELF_ASSESSED, signature="")
    bad = replace(bad, signature=s.verifier_keys["unit-assurance"].sign(bad.body()))
    d = trust_transition(
        identity,
        task,
        TrustLevel.ASSIST,
        metrics,
        bad,
        now=2,
        expires_at=7000,
        thresholds=s.thresholds,
        verifier_keys=s.verifier_keys,
    )
    assert d.decision == "HOLD"


def test_model_change_clears_prior_authority(qualification, identity, task):
    s, r, a, g, k = qualification
    s.qualify("scheduled", r, a, g, now=2, expires_at=7000)
    assert s.trust.level(task, 3) == TrustLevel.ADVISE
    s.trust.bind(replace(identity, model_fingerprint="f" * 64))
    assert s.trust.level(task, 3) == TrustLevel.OBSERVE
