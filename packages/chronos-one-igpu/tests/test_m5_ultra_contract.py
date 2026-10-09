import copy
import json
import random
import subprocess
import sys
import pytest
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.m5_ultra import elevate_pads
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.igpu import m5_ultra_contract as m

SHA='eb174c8cd9cb4695a4f1ed1360ca843d0191d203'

def session(pads=2,db=None):
    gpu=OneIGPU(working_width=32,prime_rom_limit=1000,db_path=db)
    return gpu,gpu.m5_resident(model=elevate_pads(pads)).ultra_contract(SHA)

def chain(pads,gates):return m.OperatorChain(pads,tuple(tuple(g)for g in gates),tuple(range(pads)))

@pytest.mark.parametrize('gate',list(m.GATES))
def test_exact_gate_symbolic_basis_and_inverse(gate):
    n=m.GATES[gate];c=chain(n,[(gate,*range(n))]);proof=m.audit_operator_laws(c)
    assert proof['basis_pairs_checked']==(1<<n)**2
    assert c.then(c.inverse()).adjoint()==c.then(c.inverse())

@pytest.mark.parametrize('pads',[1,2,3,10])
@pytest.mark.parametrize('algorithm',['exact_m5_ghz','exact_m5_cluster'])
def test_preparation_preserves_pad_span_and_exact_norm(pads,algorithm):
    gpu,r=session(pads)
    try:
        c=m.preparation(r.model,algorithm);receipt=r.execute(c)
        assert len(receipt['result'])==1<<pads and receipt['normalisation']=='1'
        assert receipt['cost_model_counts']['pad_occupancy']==pads
        assert r.replay(receipt,m.device_contract('IGPU'))
    finally:gpu.close()

@pytest.mark.parametrize('seed',range(12))
def test_fuzz_exact_chain_differential_adjoint_composition(seed):
    rng=random.Random(seed);n=2;gates=[]
    for _ in range(4):
        name=rng.choice(list(m.GATES));args=rng.sample(range(n),m.GATES[name]);gates.append((name,*args))
    c=chain(n,gates);a=chain(n,gates[:2]);b=chain(n,gates[2:])
    assert a.then(b).adjoint()==b.adjoint().then(a.adjoint())
    assert m.audit_operator_laws(c)['unitarity_exact']
    gpu,r=session(n)
    try:
        receipt=r.execute(c);assert r.execute(c)['replay_binding']==receipt['replay_binding']
        assert r.execute(c,backend='CPU_REFERENCE')['result']==receipt['result']
        out=r.execute(c.inverse(),receipt['result'])['result']
        assert out==[m.encode(m.ONE),*[m.encode(m.ZERO)for _ in range(3)]]
    finally:gpu.close()

@pytest.mark.parametrize('field',['algorithm','implementation_id','topology_id','result','device_contract_identity','rc_sha','pad_map','depth','operator_chain_digest','result_digest','cost_model_counts','certified','physical_claims','normalisation','requested_algorithm','planned_algorithm','executed_algorithm','initial_digest','reference_verification','execution_work'])
def test_resealed_mutants_rejected(field):
    gpu,r=session()
    try:
        original=r.execute(chain(2,[('H',0),('CX',0,1)]));bad=copy.deepcopy(original)
        bad[field]='mutant';body=dict(bad);body.pop('replay_binding');bad['replay_binding']=m.digest(body)
        with pytest.raises((ValueError,TypeError,KeyError,BackendAbsent)):r.replay(bad,m.device_contract('IGPU'))
    finally:gpu.close()

@pytest.mark.parametrize('mutation',['chain_map','chain_depth','chain_gate','norm','born','amplitude','extra_field'])
def test_nested_resealed_corruption_rejected(mutation):
    gpu,r=session()
    try:
        bad=r.execute(chain(2,[('H',0),('CX',0,1)]))
        if mutation=='chain_map':bad['chain']['pad_map']=[1,0]
        elif mutation=='chain_depth':bad['chain']['depth_max']=999
        elif mutation=='chain_gate':bad['chain']['gates'][0]=['X',0]
        elif mutation=='norm':bad['initial'][0]=m.encode(m.ZERO)
        elif mutation=='born':bad['born'][0]=m.encode(m.ONE)
        elif mutation=='amplitude':bad['result'][0]=m.encode(m.ONE)
        else:bad['extra']='silent extension'
        body=dict(bad);body.pop('replay_binding');bad['replay_binding']=m.digest(body)
        with pytest.raises((ValueError,ArithmeticError)):r.replay(bad,m.device_contract('IGPU'))
    finally:gpu.close()

@pytest.mark.parametrize('bad',[0,11,True])
def test_pad_bounds(bad):
    with pytest.raises(ValueError):chain(bad,[])


def test_depth_phase_and_zero_norm_bounds():
    assert m.DEPTH_MAX==55
    c=chain(1,[('T',0)]*55)
    state=(m.ZERO,m.ONE);out,_=m.fast_apply(c,state);restored,_=m.fast_apply(c.adjoint(),out);assert restored==state
    out,_=m.fast_apply(chain(1,[('T',0)]*8),state);assert out==state
    with pytest.raises(ValueError):chain(1,[('H',0)]*56)
    with pytest.raises(ValueError):c.then(chain(1,[('H',0)]))
    with pytest.raises(ValueError):m.initial_state(1,[m.encode(m.ZERO)]*2)
    with pytest.raises(ValueError):m.decode([[1.0,1],[0,1],[0,1],[0,1]])
    with pytest.raises(ValueError):m.decode([[2,2],[0,1],[0,1],[0,1]])


def test_exact_counts_and_actual_buffer_shape():
    c=chain(2,[('H',0),('CX',0,1)]);_,cost=m.fast_apply(c,(m.ONE,m.ZERO,m.ZERO,m.ZERO))
    assert cost['amplitude_add_calls']==4 and cost['amplitude_multiply_calls']==4
    assert cost['permutation_writes']==4 and cost['norm_amplitude_products']==12
    assert cost['field_rational_products']==256 and cost['state_buffer_shape']==[2,4,4]
    assert cost['op_count']==26


def test_gpu_unavailable_requires_named_fallback():
    gpu,r=session();c=chain(2,[('H',0)])
    try:
        with pytest.raises(BackendAbsent):r.execute(c,backend='GPU')
        fallback=r.execute(c,backend='GPU',authorised_fallback='CPU_REFERENCE')
        assert fallback['fallback_used'] and fallback['executed_backend']=='CPU_REFERENCE'
        assert fallback['result']==r.execute(c)['result']
        assert r.replay(fallback,m.device_contract('CPU_REFERENCE'))
        with pytest.raises(ValueError):r.replay(fallback,m.device_contract('IGPU'))
    finally:gpu.close()


def test_igpu_unavailability_has_identical_authorised_fallback(monkeypatch):
    gpu,r=session();original=m.device_contract
    def absent(b):
        if b=='IGPU':raise BackendAbsent('test absence')
        return original(b)
    try:
        monkeypatch.setattr(m,'device_contract',absent)
        with pytest.raises(BackendAbsent):r.execute(chain(2,[]))
        fallback=r.execute(chain(2,[]),authorised_fallback='CPU_REFERENCE')
        assert fallback['fallback_used']
        monkeypatch.setattr(m,'device_contract',original)
        assert r.replay(fallback,original('CPU_REFERENCE'))
    finally:gpu.close()


def test_symbolic_laws_and_proof_admission():
    assert m.symbolic_gate_laws()['exact_unitarity']
    with pytest.raises(ValueError):m.audit_operator_laws(chain(4,[]))


def test_restart_replay_installed_fresh_process(tmp_path):
    db=tmp_path/'custody.db';gpu,r=session(db=str(db))
    receipt=r.execute(chain(2,[('H',0),('T',0),('CX',0,1)]));oid=r.checkpoint(receipt);gpu.close()
    code='''import sys,json
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.m5_ultra import elevate_pads
from chronos_one_igpu.igpu.m5_ultra_contract import device_contract
with OneIGPU(working_width=32,prime_rom_limit=1000,db_path=sys.argv[1])as g:
 r=g.m5_resident(model=elevate_pads(2)).ultra_contract(sys.argv[2]);x=r.restore(sys.argv[3],device_contract('IGPU'));print(x['replay_binding'])
'''
    result=subprocess.run([sys.executable,'-I','-c',code,str(db),SHA,oid],capture_output=True,text=True)
    assert result.returncode==0,result.stderr;assert result.stdout.strip()==receipt['replay_binding']


def test_same_contract_new_owner_replay_and_revision_swap():
    g1,r1=session();g2,r2=session()
    try:
        receipt=r1.execute(chain(2,[('H',1),('S',1)]));assert r2.replay(receipt,m.device_contract('IGPU'))
        wrong=m.M5UltraContract(g2,r2.model,'a'*40)
        with pytest.raises(ValueError):wrong.replay(receipt,m.device_contract('IGPU'))
    finally:g1.close();g2.close()


def test_differential_disagreement_fails_no_winner(monkeypatch):
    gpu,r=session()
    try:
        monkeypatch.setattr(m,'reference_apply',lambda c,s,with_counts=False:((m.ZERO,)*4,{})if with_counts else(m.ZERO,)*4)
        with pytest.raises(ArithmeticError):r.execute(chain(2,[]))
    finally:gpu.close()


def test_signed_custody_and_tamper(tmp_path):
    from chronos_one_igpu.igpu.m5_contract_custody import seal,verify
    import hashlib
    key=tmp_path/'test-only.pem'
    result=subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(key)],capture_output=True)
    assert result.returncode==0
    bundle={'rc_sha':SHA,'test_fixture_only':True,'contract_scope':'INCREMENTAL_EVIDENCE_ONLY'}
    receipt=seal(bundle,key,tmp_path/'store');folder=tmp_path/'store'/SHA/receipt['bundle_sha256']
    assert verify(folder,receipt['public_key_sha256'])==bundle
    assert seal(bundle,key,tmp_path/'store')==receipt
    with pytest.raises(ValueError):verify(folder,'0'*64)
    (folder/'bundle.json').write_text('{}')
    with pytest.raises((ValueError,KeyError)):verify(folder,receipt['public_key_sha256'])


def test_random_exact_normalised_inputs_and_gate_phase_closure():
    from fractions import Fraction
    c=chain(2,[('H',0),('T',0),('SDG',0),('SWAP',0,1)])
    for sign in(-1,1):
        initial=((Fraction(3,5),Fraction(0),Fraction(0),Fraction(0)),(Fraction(sign*4,5),Fraction(0),Fraction(0),Fraction(0)),m.ZERO,m.ZERO)
        fast,_=m.fast_apply(c,initial);assert fast==m.reference_apply(c,initial)
        back,_=m.fast_apply(c.inverse(),fast);assert back==initial


def test_signature_wrong_key_and_signature_tamper(tmp_path):
    from chronos_one_igpu.igpu.m5_contract_custody import seal,verify
    key=tmp_path/'test-only.pem'
    assert subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(key)],capture_output=True).returncode==0
    receipt=seal({'rc_sha':SHA,'test_fixture_only':True},key,tmp_path/'store');folder=tmp_path/'store'/SHA/receipt['bundle_sha256']
    signature=bytearray((folder/'signature.ed25519').read_bytes());signature[0]^=1;(folder/'signature.ed25519').write_bytes(signature)
    with pytest.raises(ValueError):verify(folder,receipt['public_key_sha256'])


def test_non_ed25519_signer_rejected(tmp_path):
    from chronos_one_igpu.igpu.m5_contract_custody import seal
    key=tmp_path/'test-only-rsa.pem'
    assert subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(key)],capture_output=True).returncode==0
    with pytest.raises(ValueError):seal({'rc_sha':SHA,'test_fixture_only':True},key,tmp_path/'store')


def test_installed_operator_chain_cli(tmp_path):
    p=tmp_path/'chain.json';p.write_text(json.dumps({'chain':chain(2,[('H',0),('T',0),('CX',0,1)]).to_dict()}))
    result=subprocess.run([sys.executable,'-I','-c','from chronos_one_igpu.release_cli import main;main()','m5-ultra-run',str(p),'--rc-sha',SHA],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    r=json.loads(result.stdout);assert r['depth']==3 and r['rc_sha']==SHA and r['certified']is False


def test_independent_born_disagreement_is_release_failure(monkeypatch):
    gpu,r=session()
    try:
        monkeypatch.setattr(m,'born_fast',lambda state:[m.encode(m.ONE)]*len(state))
        with pytest.raises(ArithmeticError):r.execute(chain(2,[('H',0)]))
    finally:gpu.close()
