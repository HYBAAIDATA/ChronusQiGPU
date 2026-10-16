"""Fail-closed bounded contract gate evaluator; never whole-product authority.

Inputs are authenticated/pinned evidence already verified by the acquisition
and custody tools. This evaluator does not prove a JSON record came from CI or
hardware; trusted evidence acquisition remains an external prerequisite.
"""
import hashlib
from .resident import canonical


def evaluate_contract_gates(rc_sha,campaign,installed,index_install=None,cross_replay=None,signed_custody=None,ci=None):
    gates={key:False for key in'ABCDEFGH'};reasons={};bindings=[]
    if not isinstance(rc_sha,str)or len(rc_sha)!=40:raise ValueError('full revision binding required')
    if campaign.get('rc_sha')!=rc_sha:raise ValueError('campaign revision mismatch')
    body=dict(campaign);seal=body.pop('report_digest',None)
    if seal!=hashlib.sha256(canonical(body)).hexdigest():raise ValueError('campaign content seal')
    rows=campaign.get('parity',[]);mutants=campaign.get('mutations',[])
    if not rows or not isinstance(rows,list)or not mutants or not isinstance(mutants,list):raise ValueError('nonempty declared evidence required')
    for m in mutants:
        if set(m)-{'target','survived','detection_layer','rejection_reason'}or type(m.get('survived'))is not bool:raise ValueError('mutation record type')
    gates['C']=all(r.get('CPU_REFERENCE')=='PASS'and r.get('IGPU')=='PASS_HOST_CPU_EXACT_RESIDENT'and r.get('canonical_byte_equal')is True and r.get('symbolic_basis_proof',{}).get('unitarity_exact')is True for r in rows)
    gates['D']=gates['C']and all(r.get('GPU')=='PASS_ACTUAL_EXACT_OPENCL'for r in rows)
    gates['E']=type(campaign.get('mutation_survivors'))is int and campaign.get('mutation_survivors')==0 and len({m['target']for m in mutants})==len(mutants)and all(m['survived']is False and m.get('detection_layer')and m.get('rejection_reason')for m in mutants)
    gates['G']=campaign.get('fallback',{}).get('unsupported_GPU_domain_without_authorisation')=='REJECT'and campaign.get('fallback',{}).get('named_CPU_REFERENCE_fallback')=='PASS'
    # Installed records must have executed tests, with no failures/errors. Device
    # unavailability skips may not turn into complete backend qualification.
    suites=[]
    for record in installed:
        if record.get('rc_sha')!=rc_sha:raise ValueError('installed evidence revision mismatch')
        suites.extend(record.get('results',[]))
    gates['B']=bool(suites)and all(type(s.get('pass'))is int and s['pass']>0 and s.get('fail')==0 and s.get('error')==0 and type(s.get('unavailable'))is int and s['unavailable']==0 for s in suites)
    if index_install is not None:
        if index_install.get('rc_sha')!=rc_sha:raise ValueError('internal index evidence revision mismatch')
        from urllib.parse import urlsplit
        u=urlsplit(index_install.get('internal_index_url',''))
        gates['A']=index_install.get('pass')is True and index_install.get('registry')=='INTERNAL_INDEX'and u.scheme=='https'and bool(u.hostname)and not any(p in u.hostname.lower()for p in('pypi.org','pypi.python.org','pythonhosted.org'))and bool(index_install.get('artifacts'))and bool(index_install.get('commands'))and all(c.get('exit_code')==0 for c in index_install['commands'])
    if cross_replay is not None:
        if cross_replay.get('rc_sha')!=rc_sha:raise ValueError('replay evidence revision mismatch')
        cases=cross_replay.get('replayed_receipts',[])
        gates['F']=cross_replay.get('distinct_runner_context_observed')is True and bool(cases)and all(c.get('pass')is True for c in cases)and cross_replay.get('hardware_redispatched')is False
    if signed_custody is not None:
        if signed_custody.get('rc_sha')!=rc_sha:raise ValueError('custody revision mismatch')
        gates['H']=signed_custody.get('signature_algorithm')=='Ed25519'and signed_custody.get('trusted_signature_verified')is True and bool(signed_custody.get('public_key_sha256'))and bool(signed_custody.get('bundle_sha256'))
    ci_ok=bool(ci and ci.get('rc_sha')==rc_sha and ci.get('verified_acquisition')is True and ci.get('conclusion')=='success'and ci.get('executed_steps',0)>0 and ci.get('ci_run_url'))
    if not ci_ok:gates['B']=False;reasons['B']='actual complete-checkout CI evidence unavailable'
    for key,value in gates.items():
        if not value:reasons.setdefault(key,'required evidence missing, unavailable, skipped or failing')
    return {'schema':'chronos.bounded_gate_verdict/1','rc_sha':rc_sha,'scope':'CONTRACT_LAYER_INCREMENTAL_EVIDENCE_ONLY','gates':gates,'open_gates':reasons,'elevation_complete':all(gates.values()),'certified':False,'whole_product_qualified':False,'registry_policy':'INTERNAL_INDEX','public_publication_authorised':False,'evidence_authenticity_prerequisite':'verified acquisition plus externally trusted/pinned custody; JSON flags alone are not authentication'}
