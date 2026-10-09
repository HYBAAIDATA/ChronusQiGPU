"""Installed-library boundary tests, using UNIT actuators; not production voyages."""
from __future__ import annotations
import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time
from dataclasses import replace


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--modules', required=True)
    args = parser.parse_args()
    checks = {}
    modules = json.loads(args.modules)
    for name in modules:
        module = importlib.import_module(name)
        require(Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()),
                'module not from clean installed environment: '+name)
    checks['all_shipped_modules_imported'] = bool(modules)
    import salamander
    from salamander import ActionRegistry, AutonomicControlPlane, EvidenceLedger, build_authorized_control_plane
    from salamander.control_plane import FailClosed, RecoveryPlan, RecoveryStep
    from salamander.models import ActionKind, ActionRequest
    from salamander.outcome_evidence import EvidenceClass, RuntimeObservation, unqualified_readiness
    from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
    require(salamander.__version__ == args.expected_version == importlib.metadata.version('hyba-salamander-self-healing'),
            'distribution/import version mismatch')
    provenance = json.loads((Path(salamander.__file__).parent/'_build_provenance.json').read_text())
    require(provenance['source_commit'] == args.expected_commit, 'wrong source provenance')
    checks['version_and_source_commit'] = True
    signer = SubscriptionAuthority({'unit':b'unit-only-installed-smoke-key-material'}, issuer='unit-smoke')
    now = int(time.time())
    token = signer.issue(SubscriptionClaims(
        subscription_id='unit-smoke', tenant_id='unit-tenant', issuer='unit-smoke', key_id='unit',
        capabilities=('hyba.security',), actors=('unit-actor',), not_before=now-1, expires_at=now+300,
    ))
    guardian = ALHaras(signer, GuardianPolicy(version='unit-policy', allowed_operations=frozenset(
        {'salamander.replan','salamander.rollback'})), HashChainAudit())
    calls = []
    state = {'value':'baseline'}
    registry = ActionRegistry()
    def owner(request):
        calls.append(request.action_id)
        state['value'] = 'baseline' if request.kind is ActionKind.ROLLBACK else 'changed'
        return {'reported_success': True}
    def independent_probe(request, response):
        # Probe reads the test subject, not the actuator's success dictionary.
        expected = 'baseline' if request.kind is ActionKind.ROLLBACK else request.bounds['expected']
        valid = state['value'] == expected
        return {'verified':valid,'evidence_ref':'unit-probe:'+request.action_id,
                'observations':{'value':state['value']}}
    registry.register('unit-owner',{ActionKind.REPLAN,ActionKind.ROLLBACK},owner,
                      verifier_id='unit-independent-probe',verifier=independent_probe)
    plane = build_authorized_control_plane(registry=registry,guardian=guardian,
                                          token_provider=lambda _:token,max_recoveries_per_target=1)
    request = ActionRequest('accepted',ActionKind.REPLAN,'unit-owner','unit-tenant','unit-subject',
                            'installed-unit-smoke',{'max_attempts':1,'expected':'changed'},
                            idempotency_key='accepted',actor_id='unit-actor')
    denied = replace(request,action_id='denied',tenant_id='foreign',idempotency_key='denied')
    try:
        plane.execute(denied)
    except FailClosed:
        checks['cross_tenant_denied_before_actuation'] = calls == []
    else:
        checks['cross_tenant_denied_before_actuation'] = False
    result = plane.execute(request)
    checks['signed_authorized_action'] = result.verified and calls == ['accepted']
    plane.execute(request)
    checks['idempotency'] = calls == ['accepted']
    rollback = replace(request,action_id='rollback',kind=ActionKind.ROLLBACK,idempotency_key='rollback')
    rejected = replace(request,action_id='rejected',idempotency_key='rejected',
                       bounds={'max_attempts':1,'expected':'deliberately-not-changed'})
    plan = RecoveryPlan('unit-recovery','unit-tenant','unit-subject',
                        (RecoveryStep('step',rejected,rollback=rollback),),2,time.time_ns()+5_000_000_000)
    results = plane.recover(plan)
    checks['fake_success_rejected_and_authorized_rollback_verified'] = (
        len(results)==2 and not results[0].verified and results[1].verified and state['value']=='baseline')
    reopened = EvidenceLedger.from_payload(plane.ledger.to_payload())
    restored = AutonomicControlPlane(registry=ActionRegistry(),ledger=reopened,max_recoveries_per_target=1)
    try:
        restored.recover(plan)
    except FailClosed as exc:
        checks['ledger_reconstruction_retains_recovery_budget'] = 'budget exhausted' in str(exc)
    else:
        checks['ledger_reconstruction_retains_recovery_budget'] = False
    try:
        AutonomicControlPlane(registry=ActionRegistry(),require_authorization=False)
    except FailClosed:
        checks['authorization_opt_out_refused'] = True
    else:
        checks['authorization_opt_out_refused'] = False
    try:
        registry.execute(request)
    except FailClosed:
        checks['direct_registry_bypass_refused'] = True
    else:
        checks['direct_registry_bypass_refused'] = False
    obs = RuntimeObservation('unit-observation','unit-subject','unit-tenant','pythia','unit-metric',1,
                             {'contract_ref':'unit','operator':'eq','value':1},time.time_ns(),
                             EvidenceClass.SIMULATED,'unit-fixture',args.expected_commit,'unit-trace')
    checks['synthetic_observation_not_production'] = not obs.production_eligible(now_ns=time.time_ns(),max_age_ns=10**9)
    from salamander.discovery_optimisation import DiscoveryOptimisationCandidate, DiscoveryRefused
    try:
        DiscoveryOptimisationCandidate('emergence','unit',True,{'latency':1.0},{'latency':0.5},4,'unit','unit')
    except DiscoveryRefused:
        checks['missing_toe_authority_refused'] = True
    else:
        checks['missing_toe_authority_refused'] = False
    require(all(checks.values()), 'installed boundary check failed')
    print(json.dumps({'passed':all(checks.values()),'checks':checks,'modules':modules,
                      'source_commit':args.expected_commit,'production':unqualified_readiness(),
                      'evidence_class':'INSTALLED_LIBRARY_UNIT_TEST',
                      'production_composition':'NOT_EXECUTED'}))


if __name__ == '__main__':
    main()
