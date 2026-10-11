import copy
from fractions import Fraction
import hashlib
import json
from multiprocessing import shared_memory
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
import sympy as sp
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.family_algebra import PHI,PhiElement
from chronos_one_igpu.m5_ultra import m5_ultra_fabric,elevate_pads
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.igpu.feature_profile import FeatureProfile
from chronos_one_igpu.igpu.feature_runtime import FeatureConfig,GenericFeatureRuntime,digest
from chronos_one_igpu.igpu.exact_neural import PreparedNetwork,PreparedLayer,value,sign,encode
from chronos_one_igpu.igpu.exact_stabilizer import StabilizerState,prepare,verify_receipt
from chronos_one_igpu.igpu.unified_fabric import UnifiedArena,LocalPadTransport
from chronos_one_igpu.igpu.virtual_abi import Workload,VirtualRuntime


@pytest.fixture
def profile():return FeatureProfile((2,2),((0,1),))


def neural_task():return {'kind':'neural','input':[[1,-2],[3,4]],'layers':[{'weights':[[2,0],[0,3]],'bias':[0,1],'activation':'relu'}]}


def test_full_original_model_register_composition():
    profile=FeatureProfile.from_model(m5_ultra_fabric())
    assert profile.pad_qubits==(128,128,128,128)
    assert profile.register_layout()[0]==512
    assert profile.register_layout('pad')[0]==4
    assert FeatureProfile.from_dict(profile.to_dict())==profile


@pytest.mark.parametrize('counts,edges', [((True,),()),((0,),()),((4097,),()),((2,2),((0,0),)),((2,2),((0,1),(1,0)))])
def test_invalid_generic_profiles_rejected(counts,edges):
    with pytest.raises(ValueError):FeatureProfile(counts,edges)


@pytest.mark.parametrize('algorithm',['exact_stabilizer_ghz','exact_stabilizer_cluster'])
def test_full_512_qubit_exact_register(algorithm):
    p=FeatureProfile.from_model(m5_ultra_fabric())
    r=prepare(p,algorithm)
    assert verify_receipt(r,p,algorithm)
    state=StabilizerState.from_dict(r['state'])
    assert state.n==512 and len(state.rows)==512
    assert r['sha256d_evaluations']==0 and not r['physical_quantum_execution']
    expected=Fraction(1,2)if algorithm.endswith('ghz')else Fraction(1,2**512)
    assert state.born({i:0 for i in range(512)})==expected


def test_exact_partial_born_queries_and_qec_syndrome_sign():
    p=FeatureProfile((4,),())
    state=StabilizerState.from_dict(prepare(p,'exact_stabilizer_ghz')['state'])
    assert state.born({})==1
    assert state.born({0:0})==Fraction(1,2)
    assert state.born({0:0,3:1})==0
    assert state.born({0:1,3:1})==Fraction(1,2)


def test_h_s_cx_cz_swap_exact_algebra():
    zero=StabilizerState.zero(2)
    assert zero.gate('H',0).gate('H',0)==zero
    assert zero.gate('H',0).gate('S',0).gate('S',0).gate('S',0).gate('S',0)==zero.gate('H',0)
    state=zero.gate('H',0).gate('CX',0,1);assert state.verify()
    assert state.gate('CX',0,1).gate('CX',0,1)==state
    assert state.gate('CZ',0,1).gate('CZ',0,1)==state
    assert state.gate('SWAP',0,1).gate('SWAP',0,1)==state


@pytest.mark.parametrize('rows', [((1,0,0),(1,0,0)),((1,0,0),(0,1,0)),((1,1,0),(0,2,0))])
def test_invalid_stabilizer_rank_commutation_hermiticity(rows):
    with pytest.raises(ValueError):StabilizerState(2,rows).verify()


def test_resealed_stabilizer_corruption_fails(profile):
    r=prepare(profile,'exact_stabilizer_ghz');r['state']['paulis'][0][2]=2
    body=dict(r);body.pop('receipt_digest');r['receipt_digest']=digest(body)
    with pytest.raises(ValueError):verify_receipt(r,profile,'exact_stabilizer_ghz')


@pytest.mark.parametrize('v,want', [(0,0),(1,1),(-1,-1),(PhiElement(1,-1),-1),(PhiElement(-1,1),1),(PhiElement(3,-2),-1),(PhiElement(-3,2),1)])
def test_exact_relu_ordering(v,want):assert sign(v)==want


@pytest.mark.parametrize('invalid',[1.0,True,{'encoding':'q_phi_v1','a':[2,2],'b':[0,1]}])
def test_neural_rejects_approximate_or_noncanonical_scalar(invalid):
    with pytest.raises(ValueError):value(invalid)


@pytest.mark.parametrize('field',[False,True])
def test_prepared_network_full_dense_parity(field):
    weights=[[PHI if field else 2,0],[0,3]]
    network=PreparedNetwork([{'weights':weights,'bias':[0,1],'activation':'relu'}])
    result,work=network.execute([[1,-2],[3,4]])
    assert network.verify([[1,-2],[3,4]],encode(result))
    assert work['scalar_products']==4 and work['dense_scalar_products']==8
    assert work['zero_coefficients_eliminated']==4
    assert work['layers'][0]['kernel_branch']==('exact_qphi_field'if field else'exact_rational_subfield')
    snapshot=network.spec;snapshot[0]['weights'].clear()
    assert network.spec[0]['weights']


def test_network_quota_before_first_layer():
    network=PreparedNetwork(neural_task()['layers'])
    with pytest.raises(ValueError):network.execute(neural_task()['input'],max_scalar_ops=1)


def test_m5_to_generic_features_cache_and_fresh_inputs():
    with OneIGPU()as gpu:
        with gpu.m5_resident().features()as runtime:
            assert runtime.profile.register_layout()[0]==512
            assert runtime.manifest()['active_transport_workers']==0
            first=runtime.execute(neural_task());second=runtime.execute(neural_task())
            assert not first['prepared_program_cache_hit']and second['prepared_program_cache_hit']
            task=neural_task();task['input']=[[5,6]]
            third=runtime.execute(task)
            assert third['prepared_program_cache_hit'] and third['output']!=first['output']
            task=neural_task();task['layers'][0]['weights'][0][0]=4
            assert not runtime.execute(task)['prepared_program_cache_hit']
            assert runtime.manifest()['vendor_dependency']is None


@pytest.mark.parametrize('operation',['matmul','add','hadamard'])
def test_generic_exact_tensor_route(profile,operation):
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            r=runtime.execute({'kind':'tensor','operation':operation,'left':[[1,2],[3,4]],'right':[[5,6],[7,8]]})
            assert runtime.verify(r)
            assert r['requested_algorithm']==r['planned_algorithm']==r['executed_algorithm']=='exact_qphi_'+operation


def test_supplied_exact_neural_hamiltonian_not_dense_substitution(profile):
    from chronos_one_igpu.igpu.exact_quantum import encode_expression
    task={'kind':'unitary','amplitudes':[1,0],'hamiltonian':[[0,1],[1,0]],'time':encode_expression(sp.pi/2)}
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            receipt=runtime.execute(task)
            assert runtime.verify(receipt)
            assert receipt['executed_algorithm']=='exact_hamiltonian_evolution'
            assert receipt['output']['amplitudes'][1]==encode_expression(-sp.I)


@pytest.mark.parametrize('field',['executed_algorithm','implementation_digests','substrate','sha256d_evaluations','iterations_work_performed','output'])
def test_feature_resealed_substitution_rejected(profile,field):
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            r=runtime.execute(neural_task());r[field]=123 if field=='sha256d_evaluations'else{}if field!='executed_algorithm'else'heuristic'
            body=dict(r);body.pop('receipt_digest');r['receipt_digest']=digest(body)
            with pytest.raises((ValueError,TypeError,KeyError)):runtime.verify(r)


def test_required_hardware_is_not_emulated(profile):
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            task=neural_task();task['require_host_gpu']=True
            with pytest.raises(BackendAbsent):runtime.execute(task)


def test_actual_readonly_zero_copy_shared_memory_and_pinning():
    arena=UnifiedArena(max_bytes=1024,max_blocks=1)
    handle=arena.put(b'actual shared payload')
    assert arena.put(b'actual shared payload')==handle
    with arena.borrow(handle)as view:
        assert view.readonly and bytes(view)==b'actual shared payload'
        with pytest.raises(TypeError):view[0]=0
        with pytest.raises(MemoryError):arena.put(b'other')
        with pytest.raises(RuntimeError):arena.close()
    arena.close();assert arena.inventory()['allocated_bytes']==0


def test_corrupt_shared_segment_is_rejected():
    arena=UnifiedArena();handle=arena.put(b'abc')
    memory=shared_memory.SharedMemory(name=handle['shared_memory'])
    try:
        memory.buf[0]=120
        with pytest.raises(ValueError,match='corrupted'):
            with arena.borrow(handle):pass
    finally:memory.close();arena.close()


def test_actual_pad_transport_retry_and_route_binding(profile):
    arena=UnifiedArena();handle=arena.put(b'finite shared data')
    transport=LocalPadTransport(profile,arena)
    try:
        receipt=transport.transfer(handle,0,1,'job')
        assert transport.verify(receipt,handle,0,1,'job')
        assert receipt==transport.transfer(handle,0,1,'job')
        assert receipt['payload_bytes_copied_between_pads']==0
        assert len(receipt['hops'])==2 and receipt['physical_network_bytes']is None
        with pytest.raises(ValueError):transport.transfer(handle,1,0,'job')
        broken=copy.deepcopy(receipt);broken['hops'][1]['pad']=0
        body=dict(broken);body.pop('receipt_digest');broken['receipt_digest']=digest(body)
        with pytest.raises(ValueError):transport.verify(broken,handle,0,1,'job')
    finally:transport.close();assert not any(t.is_alive()for t in transport.threads);arena.close()


def test_concurrent_transport_same_id_is_single_execution(profile):
    arena=UnifiedArena();handle=arena.put(b'concurrent')
    transport=LocalPadTransport(profile,arena)
    try:
        with ThreadPoolExecutor(max_workers=4)as pool:
            results=list(pool.map(lambda _:transport.transfer(handle,0,1,'same'),range(4)))
        assert all(r==results[0]for r in results)
        assert len(transport.records)==1
    finally:transport.close();arena.close()


def test_disconnected_route_fails_without_fake_transfer():
    arena=UnifiedArena();transport=LocalPadTransport(FeatureProfile((1,1),()),arena)
    try:
        with pytest.raises(ValueError):transport.transfer(arena.put(b'a'),0,1,'none')
    finally:transport.close();arena.close()


def test_durable_generic_feature_restart_replay(tmp_path,profile):
    path=tmp_path/'state.db'
    with OneIGPU(db_path=path)as gpu:
        with gpu.feature_runtime(profile)as runtime:
            object_id=runtime.checkpoint(runtime.execute(neural_task()))
    code='''import sys,json
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.igpu.feature_profile import FeatureProfile
with OneIGPU(db_path=sys.argv[1]) as gpu:
 with gpu.feature_runtime(FeatureProfile((2,2),((0,1),))) as runtime:
  r=runtime.restore(sys.argv[2]); assert runtime.verify(r)
print('DURABLE_REPLAY_VERIFIED')'''
    assert 'DURABLE_REPLAY_VERIFIED'in subprocess.check_output([sys.executable,'-I','-c',code,str(path),object_id],text=True)


def test_concurrent_primedb_custody(profile,tmp_path):
    with OneIGPU(db_path=tmp_path/'concurrent.db')as gpu:
        def store(i):
            obj=gpu.db.put({'actual':i},1,family='concurrency');assert gpu.db.get(obj.object_id).payload=={'actual':i}
            return obj.object_id
        with ThreadPoolExecutor(max_workers=4)as pool:ids=list(pool.map(store,range(12)))
        assert len(set(ids))==12 and gpu.db.count()==12


def test_abi_generic_features_and_retry(profile):
    work=Workload('real-feature','client','exact_features',{'profile':profile.to_dict(),'task':neural_task()},quota=10000)
    with OneIGPU()as gpu:
        first=gpu.execute_workload(work);assert VirtualRuntime.verify_receipt(first,work)
        assert gpu.execute_workload(work)==first
        assert first['backend']=='cpu_exact_features'
        changed=Workload('real-feature','client','exact_features',{'profile':profile.to_dict(),'task':{**neural_task(),'input':[[5,6]]}},quota=10000)
        with pytest.raises(ValueError):gpu.execute_workload(changed)


def test_runtime_cleans_owner_resources_and_can_retry_pinned_close(profile):
    gpu=OneIGPU();runtime=gpu.feature_runtime(profile);handle=runtime.arena.put(b'one')
    with runtime.arena.borrow(handle):
        with pytest.raises(RuntimeError):runtime.close()
    runtime.close();runtime.close();gpu.close()
    assert runtime.arena.inventory()['allocated_bytes']==0


def test_exact_32_term_neural_hamiltonian_sum(profile):
    from chronos_one_igpu.igpu.exact_quantum import encode_expression
    q=encode_expression(sp.Rational(1,32));term=[[0,q],[q,0]]
    task={'kind':'unitary_sum','amplitudes':[1,0],'hamiltonian_terms':[term]*32,'time':encode_expression(sp.pi/2)}
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            receipt=runtime.execute(task);assert runtime.verify(receipt)
            assert receipt['executed_algorithm']=='exact_hamiltonian_sum_evolution'
            assert receipt['iterations_work_performed']['hamiltonian_terms_added']==32
            assert receipt['output']['amplitudes'][1]==encode_expression(-sp.I)


@pytest.mark.parametrize('condition',['commutes','annihilates'])
def test_exact_unified_projector_conditions(profile,condition):
    task={'kind':'projector','projector':[[1,0],[0,0]],'hamiltonian':[[0,0],[0,1]],'condition':condition}
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            receipt=runtime.execute(task);assert runtime.verify(receipt)
            assert receipt['output']['verified']


def test_commutation_does_not_imply_annihilation(profile):
    task={'kind':'projector','projector':[[1,0],[0,0]],'hamiltonian':[[1,0],[0,2]],'condition':'commutes'}
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            assert runtime.execute(task)['output']['verified']
            with pytest.raises(ValueError):runtime.execute({**task,'condition':'annihilates'})


def test_generic_operator_commutation_and_rejection(profile):
    x=[[0,1],[1,0]];z=[[1,0],[0,-1]]
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            good=runtime.execute({'kind':'commutator','left_operator':x,'right_operator':x});assert runtime.verify(good)
            with pytest.raises(ValueError):runtime.execute({'kind':'commutator','left_operator':x,'right_operator':z})


def test_nonhermitian_terms_are_not_silently_cancelled(profile):
    task={'kind':'unitary_sum','amplitudes':[1,0],'hamiltonian_terms':[[[0,1],[0,0]],[[0,0],[1,0]]],'time':1}
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            with pytest.raises(ValueError,match='Hermitian'):runtime.execute(task)


def test_installed_generic_feature_cli(tmp_path,profile):
    path=tmp_path/'task.json';path.write_text(json.dumps(neural_task()))
    profile_path=tmp_path/'profile.json';profile_path.write_text(json.dumps(profile.to_dict()))
    output=json.loads(subprocess.check_output([sys.executable,'-I','-m','chronos_one_igpu.release_cli','feature-run',str(path),'--profile-file',str(profile_path),'--db-path',str(tmp_path/'cli.db'),'--checkpoint'],text=True))
    assert output['object_id']and output['receipt']['executed_algorithm']=='exact_qphi_neural'


def _shared_child_reader(handle,pipe):
    from multiprocessing import shared_memory
    import hashlib
    memory=shared_memory.SharedMemory(name=handle['shared_memory'])
    view=memory.buf[:handle['size']].toreadonly()
    try:pipe.send((hashlib.sha256(view).hexdigest(),view.readonly))
    finally:view.release();memory.close();pipe.close()


def test_real_cross_process_shared_memory_read():
    import multiprocessing
    context=multiprocessing.get_context('spawn');parent,child=context.Pipe()
    arena=UnifiedArena();handle=arena.put(b'actual cross-process shared-memory data')
    process=context.Process(target=_shared_child_reader,args=(handle,child))
    try:
        with arena.borrow(handle):
            process.start();child.close()
            assert parent.poll(10)
            observed,readonly=parent.recv();process.join(10)
            assert process.exitcode==0 and observed==handle['sha256']and readonly
    finally:
        if process.is_alive():process.terminate();process.join()
        parent.close();arena.close()


def test_exact_36_way_uniform_register_state(profile):
    n=36;zero=[[0]*n for _ in range(n)]
    with OneIGPU()as gpu:
        with gpu.feature_runtime(profile)as runtime:
            receipt=runtime.execute({'kind':'unitary','amplitudes':[1]*n,'hamiltonian':zero,'time':1})
            from chronos_one_igpu.igpu.exact_quantum import decode_expression
            assert all(decode_expression(a)==sp.Rational(1,6)for a in receipt['output']['amplitudes'])
            assert runtime.verify(receipt)


def test_owner_retains_pending_lease_cleanup(profile):
    gpu=OneIGPU();old=gpu.feature_runtime(profile);handle=old.arena.put(b'pinned')
    with old.arena.borrow(handle):
        with pytest.raises(RuntimeError):old.close()
        new=gpu.feature_runtime(profile)
        assert old in gpu._feature_runtimes and new in gpu._feature_runtimes
    gpu.close();assert old.arena.closed and new.arena.closed
