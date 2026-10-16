"""Evaluator fault-injection records only; never execution/device evidence."""
import copy
import pytest
from chronos_one_igpu.igpu.m5_release_gates import evaluate_contract_gates
from chronos_one_igpu.igpu.m5_ultra_contract import digest

SHA='a'*40

def fail_record():
    d={'rc_sha':SHA,'parity':[{'CPU_REFERENCE':'PASS','IGPU':'PASS_HOST_CPU_EXACT_RESIDENT','GPU':'UNAVAILABLE','canonical_byte_equal':True,'symbolic_basis_proof':{'unitarity_exact':True}}],'mutations':[{'target':'identity','survived':False,'detection_layer':'replay','rejection_reason':'identity mismatch'}],'mutation_survivors':0,'fallback':{'unsupported_GPU_domain_without_authorisation':'REJECT','named_CPU_REFERENCE_fallback':'PASS'}};d['report_digest']=digest(d);return d


def test_missing_external_evidence_never_closes():
    v=evaluate_contract_gates(SHA,fail_record(),[])
    assert v['gates']['C']and v['gates']['E']and v['gates']['G']
    assert not v['gates']['A']and not v['gates']['B']and not v['gates']['D']and not v['gates']['F']and not v['gates']['H']
    assert not v['elevation_complete']and not v['certified']and not v['public_publication_authorised']

@pytest.mark.parametrize('field',['rc_sha','mutation_survivors','parity','fallback'])
def test_mutated_unsealed_evidence_rejected(field):
    d=fail_record();d[field]='changed'
    with pytest.raises(ValueError):evaluate_contract_gates(SHA,d,[])


def test_resealed_survivor_is_release_blocker():
    d=fail_record();d['mutations'][0]['survived']=True;d['mutation_survivors']=1;d.pop('report_digest');d['report_digest']=digest(d)
    assert not evaluate_contract_gates(SHA,d,[])['gates']['E']


def test_zero_steps_ci_and_skips_cannot_be_pass():
    installed=[{'rc_sha':SHA,'results':[{'pass':9,'fail':0,'error':0,'unavailable':1}]}]
    ci={'rc_sha':SHA,'verified_acquisition':True,'conclusion':'success','executed_steps':0,'ci_run_url':'not-an-executed-run'}
    assert not evaluate_contract_gates(SHA,fail_record(),installed,ci=ci)['gates']['B']


def test_public_index_cannot_satisfy_internal_gate():
    index={'rc_sha':SHA,'pass':True,'registry':'INTERNAL_INDEX','internal_index_url':'https://pypi.org/simple','artifacts':[1],'commands':[{'exit_code':0}]}
    assert not evaluate_contract_gates(SHA,fail_record(),[],index_install=index)['gates']['A']


def test_replay_not_distinct_and_unsigned_custody_stay_open():
    replay={'rc_sha':SHA,'distinct_runner_context_observed':False,'replayed_receipts':[{'pass':True}],'hardware_redispatched':False}
    custody={'rc_sha':SHA,'signature_algorithm':'Ed25519','trusted_signature_verified':False,'public_key_sha256':'test-key','bundle_sha256':'test-bundle'}
    v=evaluate_contract_gates(SHA,fail_record(),[],cross_replay=replay,signed_custody=custody);assert not v['gates']['F']and not v['gates']['H']


def test_boolean_zero_counter_is_not_integer_evidence():
    d=fail_record();d['mutation_survivors']=False;d.pop('report_digest');d['report_digest']=digest(d)
    assert not evaluate_contract_gates(SHA,d,[])['gates']['E']
