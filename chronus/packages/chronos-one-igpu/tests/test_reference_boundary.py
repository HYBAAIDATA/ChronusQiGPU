"""Mechanical reference approval, revocation, caching and production refusal."""
import json,time,importlib,sys
import pytest
from chronos_one_igpu.reference_contract import (ReferenceUnavailable,reference_execution,require_reference,require_production_context,reference_only)
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.igpu.structured_solver import StructuredHamiltonian

@pytest.fixture
def approval(tmp_path,monkeypatch):
    path=tmp_path/'approved.json'
    record={'schema':'chronos.reference_approvals/1','approvals':{'qc-local':{'approved':True,'approved_by':'local-test-operator','purpose':'boundary verification, not production evidence','mode':'reference','expires_unix':time.time()+120,'capabilities':['structured_ground.interval_or_fp64','structured_matvec.float_projection','chronus.h4_600','pythia_search.fp64','poincare_11d_order','mining.GroverStyleSearch','test.cache']}}}
    path.write_text(json.dumps(record));monkeypatch.setenv('CHRONOS_REFERENCE_APPROVALS_FILE',str(path));return path,record

@pytest.mark.parametrize('backend',['auto','certified','native','python','dense'])
def test_public_solver_never_executes_reference_without_contract(backend):
    with pytest.raises(ReferenceUnavailable):OneIGPU().structured_ground([1,0],backend=backend)

@pytest.mark.parametrize('backend',['auto','certified','native','python','dense'])
def test_direct_solver_module_cannot_bypass_contract(backend):
    with pytest.raises(ReferenceUnavailable):StructuredHamiltonian([1,0],1.5).ground(backend)

def test_direct_interval_solvers_guard_before_computation():
    from chronos_one_igpu.igpu.exact_dense import certified_dense_ground_state
    from chronos_one_igpu.igpu.exact_solver import certified_ground_state
    with pytest.raises(ReferenceUnavailable):certified_dense_ground_state([[1]])
    with pytest.raises(ReferenceUnavailable):certified_ground_state(StructuredHamiltonian([1],1.5))

def test_matvec_float_projection_is_not_exact_production_output():
    with pytest.raises(ReferenceUnavailable):OneIGPU().structured_matvec([1,0],[1,0])

def test_approved_legacy_ground_capability_remains_functional(approval):
    with reference_execution('qc-local'):
        result=OneIGPU().structured_ground([1],phi=1.5,backend='certified')
        assert result.evidence['certified'] is True
        assert len(result.vector)==1
        with pytest.raises(ReferenceUnavailable):require_production_context()
        with pytest.raises(ReferenceUnavailable):OneIGPU().execute_hendrix({},b'',b'')
    require_production_context()

def test_revocation_and_expiry_rechecked(approval):
    path,record=approval
    with reference_execution('qc-local'):
        require_reference('test.cache')
        record['approvals']['qc-local']['approved']=False;path.write_text(json.dumps(record))
        with pytest.raises(ReferenceUnavailable):require_reference('test.cache')
    record['approvals']['qc-local']['approved']=True;record['approvals']['qc-local']['expires_unix']=time.time()-1;path.write_text(json.dumps(record))
    with pytest.raises(ReferenceUnavailable):
        with reference_execution('qc-local'):pass

def test_unknown_or_out_of_scope_approval_denied(approval):
    with pytest.raises(ReferenceUnavailable):
        with reference_execution('unknown'):pass
    with reference_execution('qc-local'):
        with pytest.raises(ReferenceUnavailable):require_reference('unapproved')

def test_warm_cache_does_not_escape_contract(approval):
    from functools import lru_cache
    @reference_only('test.cache')
    @lru_cache(maxsize=1)
    def retained():return 42
    with reference_execution('qc-local'):assert retained()==42
    with pytest.raises(ReferenceUnavailable):retained()

@pytest.mark.parametrize('module,name,args',[
 ('chronus.h4_600','generate_600cell_vertices',()),
 ('chronus.h4_600','build_600_frame',()),
 ('chronus.mla1517.mining.pythia_search','precompute_pythia_search',()),
 ('chronus.mla1517.mining.pythia_search','pythia_hendrix_nonces',(b'\0'*80,0,0)),
 ('chronus.mla1517.mining.poincare_11d_order','poincare_11d_nonces',(b'\0'*80,0,0)),
 ])
def test_canonical_reference_entrypoints_guard_before_work(module,name,args):
    loaded=importlib.import_module(module)
    with pytest.raises(ReferenceUnavailable):getattr(loaded,name)(*args)

def test_approved_h4_geometry_is_preserved(approval):
    from chronus.h4_600 import generate_600cell_vertices
    with reference_execution('qc-local'):assert len(generate_600cell_vertices())==120

def test_grover_style_reference_is_not_available_as_quantum_production(approval):
    from mining.search import GroverStyleSearch
    with pytest.raises(ReferenceUnavailable):GroverStyleSearch.optimal_iterations(4)
    with reference_execution('qc-local'):
        assert GroverStyleSearch.optimal_iterations(4)==1
        assert GroverStyleSearch().search(b'',[],0)['candidates']==0


def test_legacy_planner_cannot_catch_reference_refusal_into_fallback():
    from chronos_one_igpu.golden_quantum import NonceLease
    gpu=OneIGPU()
    with pytest.raises(ReferenceUnavailable):gpu.golden.plan(NonceLease(0,1,'job',0))
    with pytest.raises(ReferenceUnavailable):gpu.search([1],lambda _:True)
    with pytest.raises(ReferenceUnavailable):gpu.scaled_search(1,lambda _:True)
