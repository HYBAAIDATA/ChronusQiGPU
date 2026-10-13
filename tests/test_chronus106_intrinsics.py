import math,struct
import pytest
from aethel.fibonacci import binet_fibonacci,cassini_quadruple,fibonacci,lucas
from aethel.zeckendorf import HardenedZeckendorfCodec
from compiler.intrinsics import INTRINSICS,compile_intrinsic,execute_reference

def ir(name,operands,result):return {'schema':'chronus.ir.v0.2','name':'test','op':'intrinsic','intrinsic':name,'operands':operands,'result_type':result,'lowering':'REFERENCE_HOST'}
def test_exact_sequences_and_independent_binet():
 for n in range(94):assert execute_reference(compile_intrinsic(ir('FIBONACCI',{'n':n},'u64')))==fibonacci(n)==binet_fibonacci(n)
 for n in range(93):assert execute_reference(compile_intrinsic(ir('LUCAS',{'n':n},'u64')))==lucas(n)
def test_sequence_overflow_fails_closed():
 for name,n in [('FIBONACCI',94),('BINET_EXACT',94),('LUCAS',93)]:
  with pytest.raises(ValueError):compile_intrinsic(ir(name,{'n':n},'u64'))
def test_zeckendorf_full_u64_and_malformed():
 for x in (0,1,2,3,2**32,2**63,2**64-1):
  mask=execute_reference(compile_intrinsic(ir('ZECKENDORF_ENCODE',{'value':x},'zeckendorf93')));assert HardenedZeckendorfCodec.verify_non_adjacent(mask);assert execute_reference(compile_intrinsic(ir('ZECKENDORF_DECODE',{'mask':mask},'u64')))==x
 with pytest.raises(ValueError):compile_intrinsic(ir('ZECKENDORF_DECODE',{'mask':3},'u64'))
def test_cassini_consumes_and_rejects_witness():
 n=20;a,b,c,_=cassini_quadruple(n);base=ir('CASSINI_VERIFY',{'n':n,'f_prev':a,'f_n':b,'f_next':c},'bool');assert execute_reference(compile_intrinsic(base))
 bad={**base,'operands':{**base['operands'],'f_n':b+1}};assert not execute_reference(compile_intrinsic(bad))
def test_pisot_proposes_conventional_remains():
 result=execute_reference(compile_intrinsic(ir('PISOT_SCHEDULE',{'extent':1024,'maximum_candidates':16,'maximum_work_group_size':256},'candidate_set')));assert any(x['provenance']=='CONVENTIONAL' for x in result);assert all(x['value']<=256 for x in result)
def test_phi_weight_is_explicit_float32():
 value=execute_reference(compile_intrinsic(ir('PHI_WEIGHT',{'index':0},'f32')));assert struct.pack('<f',value)==struct.pack('<f',1/((1+math.sqrt(5))/2))
def test_chronus1_fails_closed_without_encoding():
 value={**ir('FIBONACCI',{'n':10},'u64'),'lowering':'CHRONUS1'}
 with pytest.raises(ValueError):compile_intrinsic(value)
def test_opencl_cassini_rejects_unsafe_intermediate_width():
 n=47;a,b,c,_=cassini_quadruple(n);value={**ir('CASSINI_VERIFY',{'n':n,'f_prev':a,'f_n':b,'f_next':c},'bool'),'lowering':'OPENCL'}
 with pytest.raises(ValueError):compile_intrinsic(value)
