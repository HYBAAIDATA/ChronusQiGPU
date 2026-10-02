"""Typed Chronus IR v0.2 mathematical intrinsics and reference lowering."""
from __future__ import annotations
import json,math,struct
from dataclasses import dataclass
from typing import Any,Mapping
from aethel.fibonacci import binet_fibonacci,cassini_holds,fibonacci,lucas
from aethel.zeckendorf import HardenedZeckendorfCodec

INTRINSICS=frozenset({'FIBONACCI','LUCAS','BINET_EXACT','ZECKENDORF_ENCODE','ZECKENDORF_DECODE','CASSINI_VERIFY','PISOT_SCHEDULE','PHI_WEIGHT'})
RESULT_TYPES={'FIBONACCI':'u64','LUCAS':'u64','BINET_EXACT':'u64','ZECKENDORF_ENCODE':'zeckendorf93','ZECKENDORF_DECODE':'u64','CASSINI_VERIFY':'bool','PISOT_SCHEDULE':'candidate_set','PHI_WEIGHT':'f32'}
REFERENCE_CAPABILITIES={name:{'supported':True,'implementation':'REFERENCE_HOST','exact':name!='PHI_WEIGHT','physical_evidence':False,'cross_verified':name=='BINET_EXACT'} for name in INTRINSICS}
OPENCL_CAPABILITIES={name:{'supported':name in {'FIBONACCI','LUCAS','ZECKENDORF_ENCODE','ZECKENDORF_DECODE','CASSINI_VERIFY','PHI_WEIGHT'},'implementation':'opencl','exact':name!='PHI_WEIGHT','physical_evidence':False,'cross_verified':False} for name in INTRINSICS}

@dataclass(frozen=True)
class IntrinsicIR:
 schema:str;name:str;intrinsic:str;operands:Mapping[str,Any];result_type:str;lowering:str
 @classmethod
 def from_dict(cls,value:Mapping[str,Any])->'IntrinsicIR':
  if not isinstance(value,Mapping):raise ValueError('IR must be an object')
  allowed={'schema','name','op','intrinsic','operands','result_type','lowering'}
  if set(value)-allowed:raise ValueError('unknown IR fields')
  if value.get('op')!='intrinsic':raise ValueError('v0.2 mathematical IR requires op=intrinsic')
  obj=cls(str(value.get('schema','')),str(value.get('name','')),str(value.get('intrinsic','')).upper(),dict(value.get('operands') or {}),str(value.get('result_type','')),str(value.get('lowering','REFERENCE_HOST')));obj.validate();return obj
 def validate(self)->None:
  if self.schema!='chronus.ir.v0.2':raise ValueError('unsupported mathematical IR schema')
  if not self.name or not self.name.replace('_','a').isalnum():raise ValueError('invalid IR name')
  if self.intrinsic not in INTRINSICS:raise ValueError('unknown intrinsic')
  if self.result_type!=RESULT_TYPES[self.intrinsic]:raise ValueError('wrong intrinsic result type')
  if self.lowering not in {'REFERENCE_HOST','CHRONUS1','OPENCL'}:raise ValueError('unknown lowering')
  _validate_operands(self.intrinsic,self.operands)

@dataclass(frozen=True)
class IntrinsicPlan:
 ir:IntrinsicIR;artifact:bytes;backend:str;exact:bool

def _uint(value:Any,bits:int,name:str)->int:
 if type(value) is not int or value<0 or value>=(1<<bits):raise ValueError(f'{name} must be u{bits}')
 return value
def _keys(values:Mapping[str,Any],required:set[str])->None:
 if set(values)!=required:raise ValueError(f'operands must be {sorted(required)}')
def _validate_operands(name:str,o:Mapping[str,Any])->None:
 if name in {'FIBONACCI','BINET_EXACT'}:_keys(o,{'n'});n=_uint(o['n'],32,'n');
 elif name=='LUCAS':_keys(o,{'n'});n=_uint(o['n'],32,'n')
 elif name=='ZECKENDORF_ENCODE':_keys(o,{'value'});_uint(o['value'],64,'value');return
 elif name=='ZECKENDORF_DECODE':_keys(o,{'mask'});_uint(o['mask'],93,'mask');return
 elif name=='CASSINI_VERIFY':
  _keys(o,{'n','f_prev','f_n','f_next'});n=_uint(o['n'],32,'n');
  if n<1:raise ValueError('Cassini requires n>=1')
  for k in ('f_prev','f_n','f_next'):_uint(o[k],64,k)
  return
 elif name=='PISOT_SCHEDULE':
  _keys(o,{'extent','maximum_candidates','maximum_work_group_size'});_uint(o['extent'],32,'extent');m=_uint(o['maximum_candidates'],32,'maximum_candidates');w=_uint(o['maximum_work_group_size'],32,'maximum_work_group_size')
  if not m or not w:raise ValueError('planner bounds must be positive')
  return
 else:_keys(o,{'index'});_uint(o['index'],32,'index');return
 if name in {'FIBONACCI','BINET_EXACT'} and n>93:raise ValueError('u64 Fibonacci domain is 0..93')
 if name=='LUCAS' and n>92:raise ValueError('u64 Lucas domain is 0..92')

def compile_intrinsic(value:Mapping[str,Any])->IntrinsicPlan:
 ir=IntrinsicIR.from_dict(value)
 if ir.lowering=='CHRONUS1':raise ValueError('Chronus-1 v1.1 lacks certified wide-integer intrinsic lowering')
 caps=REFERENCE_CAPABILITIES if ir.lowering=='REFERENCE_HOST' else OPENCL_CAPABILITIES
 if not caps[ir.intrinsic]['supported']:raise ValueError(f'{ir.intrinsic} unsupported by {ir.lowering}')
 plan={'schema':'chronus.intrinsic-plan.v1','intrinsic':ir.intrinsic,'semantic_version':'1.0.0','operands':dict(ir.operands),'result_type':ir.result_type,'backend':ir.lowering,'numeric_class':'APPROXIMATE' if ir.intrinsic=='PHI_WEIGHT' else 'EXACT','assembler_bypassed':False if ir.lowering=='CHRONUS1' else None}
 artifact=json.dumps(plan,sort_keys=True,separators=(',',':')).encode()
 return IntrinsicPlan(ir,artifact,ir.lowering,ir.intrinsic!='PHI_WEIGHT')

def execute_reference(plan:IntrinsicPlan)->Any:
 if plan.backend!='REFERENCE_HOST':raise ValueError('reference executor cannot masquerade as physical backend')
 n=plan.ir.intrinsic;o=plan.ir.operands
 if n=='FIBONACCI':return fibonacci(o['n'])
 if n=='LUCAS':return lucas(o['n'])
 if n=='BINET_EXACT':return binet_fibonacci(o['n'])
 if n=='ZECKENDORF_ENCODE':return HardenedZeckendorfCodec.encode(o['value'])
 if n=='ZECKENDORF_DECODE':
  mask=o['mask']
  if not HardenedZeckendorfCodec.verify_non_adjacent(mask):raise ValueError('non-canonical adjacent Zeckendorf bits')
  value=HardenedZeckendorfCodec.decode(mask)
  if value>0xffffffffffffffff or HardenedZeckendorfCodec.encode(value)!=mask:raise ValueError('non-canonical Zeckendorf mask')
  return value
 if n=='CASSINI_VERIFY':return cassini_holds((o['f_prev'],o['f_n'],o['f_next'],(-1)**o['n']))
 if n=='PISOT_SCHEDULE':return _schedule(o['extent'],o['maximum_candidates'],o['maximum_work_group_size'])
 phi=(1.0+math.sqrt(5.0))/2.0;return struct.unpack('<f',struct.pack('<f',phi**(-(o['index']+1))))[0]

def _schedule(extent:int,limit:int,max_wg:int)->list[Mapping[str,Any]]:
 conventional=(1,2,4,8,16,32,64,128,256);items=[]
 for v in conventional:
  if v<=extent and v<=max_wg:items.append({'value':v,'provenance':'CONVENTIONAL'})
 i=0
 while True:
  v=lucas(i)
  if v>extent or v>max_wg:break
  if v>0:items.append({'value':v,'provenance':'LUCAS_PISOT'})
  i+=1
 dedup={x['value']:x for x in items};return [dedup[k] for k in sorted(dedup)][:limit]
