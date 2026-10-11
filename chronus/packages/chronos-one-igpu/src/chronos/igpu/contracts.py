"""Certified MLA objects and explicit exact/folded/projection/proof/executable views."""
from dataclasses import dataclass
from fractions import Fraction
from decimal import Decimal,localcontext
import hashlib,json
from .exact_fold import ExactFoldState
from ..lucas_engine import fibonacci_pair,lucas,nth_prime,zeckendorf_encode,zeckendorf_decode
FAMILIES=('pisot_binet','fibonacci_zeckendorf','exact_state_vector')
OPERATORS=('fold','unfold','scale','seal','verify','resonance_scan')
@dataclass(frozen=True)
class FoldContract:
    family:str
    encoding:str='exact_sum_left_v1'
    mode:str='PRESERVE'
    def validate(self):
        if self.family not in FAMILIES or self.mode not in('TRANSFORM','REHYDRATE','PRESERVE')or self.encoding!='exact_sum_left_v1':raise ValueError('unsupported fold contract')
        return True
@dataclass(frozen=True)
class OperatorContract:
    operator:str
    mode:str='PRESERVE'
    def validate(self):
        if self.operator not in OPERATORS or self.mode not in('TRANSFORM','REHYDRATE','PRESERVE'):raise ValueError('unsupported operator contract')
        return True
@dataclass(frozen=True)
class CertifiedMLAObject:
    body_json:str
    object_id:str
    @classmethod
    def create(cls,values,sequence_index=15,scale_index=15,family='exact_state_vector',lineage=()):
        if type(sequence_index)is not int or not 1<=sequence_index<=10000 or type(scale_index)is not int or not 2<=scale_index<=110:raise ValueError('object mathematical domain exceeded')
        FoldContract(family).validate();values=list(values)
        if not 1<=len(values)<=4096:raise ValueError('certified state quota')
        exact=[]
        for value in values:
            if isinstance(value,complex):real,imag=Fraction(value.real),Fraction(value.imag)
            else:real,imag=Fraction(value),Fraction(0)
            exact.append([real.numerator,real.denominator,imag.numerator,imag.denominator])
        flattened=[Fraction(v[j],v[j+1])for v in exact for j in(0,2)]
        fold=ExactFoldState.fold(flattened).to_dict();f,f1=fibonacci_pair(sequence_index)
        with localcontext()as ctx:
            ctx.prec=120;phi=(Decimal(1)+Decimal(5).sqrt())/2
            view={'phi_power':str(phi**scale_index),'nearest_lucas':lucas(scale_index),'absolute_residual_bound':str(phi**(-scale_index)),'authoritative':False}
        from ..manifold import M32Manifold
        point=M32Manifold(32).face_positions[(sequence_index-1)%32].tolist()
        body={'schema':'certified_mla_object_v2','payload_type':'exact_rational_complex_vector','exact_state':exact,
              'scale_index':scale_index,'lucas_state':lucas(scale_index),'pisot_fold':fold,'binet_view':view,
              'fibonacci_pair':[f,f1],'zeckendorf_code':zeckendorf_encode(sequence_index),'prime_address':nth_prime(sequence_index),
              'sequence_index':sequence_index,'polyhedral_location':{'manifold':'M32','face_index':(sequence_index-1)%32,'frame_11d':point+[0.0]*8},
              'transform_state':{'family':family,'encoding':'exact_sum_left_v1','mode':'PRESERVE'},
              'cassini_seal':fibonacci_pair(sequence_index-1)[0]*fibonacci_pair(sequence_index+1)[0]-f*f,
              'residual_boundary':view['absolute_residual_bound'],'lineage':list(lineage),'version':2}
        text=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False)
        obj=cls(text,hashlib.sha256(text.encode()).hexdigest());obj.validate();return obj
    def to_dict(self):return {'body':json.loads(self.body_json),'object_id':self.object_id}
    @classmethod
    def from_dict(cls,data):
        text=json.dumps(data['body'],sort_keys=True,separators=(',',':'),allow_nan=False);obj=cls(text,data['object_id']);obj.validate();return obj
    def validate(self):
        if hashlib.sha256(self.body_json.encode()).hexdigest()!=self.object_id:raise ValueError('certified object digest mismatch')
        b=json.loads(self.body_json);n=b['sequence_index']
        if type(n)is not int or not 1<=n<=10000 or type(b['scale_index'])is not int or not 2<=b['scale_index']<=110:raise ValueError('certified object domain exceeded')
        f,f1=fibonacci_pair(n)
        if b['schema']!='certified_mla_object_v2'or b['version']!=2 or b['fibonacci_pair']!=[f,f1]or b['lucas_state']!=lucas(b['scale_index']):raise ValueError('certified sequence invariant failure')
        if zeckendorf_decode(b['zeckendorf_code'])!=n or b['prime_address']!=nth_prime(n)or b['cassini_seal']!=(-1)**n:raise ValueError('certified address/seal invariant failure')
        fold=ExactFoldState.from_dict(b['pisot_fold']);flat=tuple(Fraction(v[j],v[j+1])for v in b['exact_state']for j in(0,2))
        if fold.unfold()!=flat:raise ValueError('certified exact-state/fold mismatch')
        FoldContract(**b['transform_state']).validate()
        if b['payload_type']!='exact_rational_complex_vector' or not 1<=len(b['exact_state'])<=4096 or not all(len(v)==4 and all(type(x)is int for x in v) and v[1]>0 and v[3]>0 for v in b['exact_state']):raise ValueError('certified rational shape mismatch')
        with localcontext()as ctx:
            ctx.prec=120;phi=(Decimal(1)+Decimal(5).sqrt())/2
            view={'phi_power':str(phi**b['scale_index']),'nearest_lucas':lucas(b['scale_index']),'absolute_residual_bound':str(phi**(-b['scale_index'])),'authoritative':False}
        if b['binet_view']!=view or b['residual_boundary']!=view['absolute_residual_bound']:raise ValueError('certified projection/residual mismatch')
        from ..manifold import M32Manifold
        expected_point=M32Manifold(32).face_positions[(n-1)%32].tolist()+[0.0]*8
        if b['polyhedral_location']!={'manifold':'M32','face_index':(n-1)%32,'frame_11d':expected_point}:raise ValueError('certified polyhedral frame mismatch')
        return True
    def retrieve(self,mode='GET EXACT'):
        self.validate();b=json.loads(self.body_json)
        if mode=='GET EXACT':return {'object_id':self.object_id,'exact_state':b['exact_state'],'rehydrated_internally':False,'authoritative':True}
        if mode=='GET FOLDED':return {'object_id':self.object_id,'fold':b['pisot_fold'],'contract':b['transform_state'],'rehydrated_internally':False}
        if mode=='GET PROJECTION':return {'object_id':self.object_id,'projection':b['binet_view'],'authoritative':False,'residual_boundary':b['residual_boundary']}
        if mode=='GET PROOF':return {'object_id':self.object_id,'cassini_valid':True,'zeckendorf_valid':True,'fold_valid':True,'lineage':b['lineage'],'version':2}
        if mode=='GET EXECUTABLE':return {'object_id':self.object_id,'object':b,'contract':b['transform_state'],'operators':list(OPERATORS)}
        raise ValueError('undeclared retrieval mode')
