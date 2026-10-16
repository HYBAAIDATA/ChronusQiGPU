"""Domain-separated local PYTHI-native computation receipts, not Bitcoin PoW.

The full 256-bit Fibonacci-matrix fold is bijective; its bounded rung
projection is deliberately many-to-one. This is not a cryptographic PRP,
Sybil-resistant consensus, chain implementation, or an ASIC performance claim.
"""
from dataclasses import dataclass,asdict
from functools import lru_cache
import hashlib,json,math,re
from .lucas_engine import fibonacci_pair,lucas,zeckendorf_encode,zeckendorf_decode
from .lucas_datapath import PrimeROM
DOMAIN=b'PYTHI-NATIVE-COMPUTE-v1\x00';MODULUS=1<<128
MAX_HEADER_BYTES=65536
STAGES=('digest','matrix_binet_fold','exact_lucas','cassini_zeckendorf','prime_address','certificate')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
@dataclass(frozen=True)
class NativePolicy:
 chain_id:str='local-pythi-v1'
 epoch:int=1
 fold_index:int=31
 rung_bits:int=8
 maximum_lucas:int|None=None
 schema:str='pythi_native_compute_v1'
 def validate(self):
  if self.schema!='pythi_native_compute_v1' or not isinstance(self.chain_id,str)or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',self.chain_id):raise ValueError('native protocol domain required')
  if type(self.epoch)is not int or not 0<=self.epoch<2**64:raise ValueError('bounded native epoch required')
  if type(self.fold_index)is not int or not 1<=self.fold_index<=256 or type(self.rung_bits)is not int or not 1<=self.rung_bits<=8:raise ValueError('bounded matrix/rung parameters required')
  if self.maximum_lucas is not None and(type(self.maximum_lucas)is not int or not 0<=self.maximum_lucas<2**256):raise ValueError('uint256 native threshold required')
  return True
 @classmethod
 def from_dict(cls,x):
  if not isinstance(x,dict)or set(x)-set(cls.__dataclass_fields__):raise ValueError('unknown native policy field')
  out=cls(**x);out.validate();return out
 def body(self):self.validate();return asdict(self)
 def digest(self):return hashlib.sha256(canonical(self.body())).hexdigest()

def matrix_fold(digest,index=31,half_bits=128):
 if type(half_bits)is not int or not 1<=half_bits<=128 or type(index)is not int or not 1<=index<=256:raise ValueError('bounded fold required')
 if not isinstance(digest,int) or isinstance(digest,bool)or not 0<=digest<1<<(2*half_bits):raise ValueError('digest outside fold domain')
 m=1<<half_bits;f,f1=fibonacci_pair(index);fprev=f1-f;x=digest>>half_bits;y=digest&(m-1)
 return ((f1*x+f*y)%m,(f*x+fprev*y)%m)
def matrix_unfold(pair,index=31,half_bits=128):
 if type(half_bits)is not int or not 1<=half_bits<=128 or type(index)is not int or not 1<=index<=256 or not isinstance(pair,(tuple,list))or len(pair)!=2:raise ValueError('bounded folded pair required')
 m=1<<half_bits
 if any(type(v)is not int or not 0<=v<m for v in pair):raise ValueError('coordinate outside fold domain')
 f,f1=fibonacci_pair(index);fprev=f1-f;sign=-1 if index%2 else 1;left,right=pair
 x=(sign*(fprev*left-f*right))%m;y=(sign*(-f*left+f1*right))%m
 return (x<<half_bits)|y
@lru_cache(maxsize=1)
def _prime_rom():return PrimeROM(5000)
def _payload(header,policy):
 policy.validate()
 if not isinstance(header,bytes)or not 1<=len(header)<=MAX_HEADER_BYTES:raise ValueError('nonempty bounded canonical header bytes required')
 domain=canonical(policy.body());raw=DOMAIN+len(domain).to_bytes(4,'big')+domain+len(header).to_bytes(4,'big')+header
 digest=hashlib.sha256(raw).digest();integer=int.from_bytes(digest,'big');left,right=matrix_fold(integer,policy.fold_index)
 if matrix_unfold((left,right),policy.fold_index)!=integer:raise ValueError('matrix fold round trip failed')
 rung=1+(left&((1<<policy.rung_bits)-1));f,f1=fibonacci_pair(rung);value=lucas(rung);neighbor=lucas(rung-1)*lucas(rung+1)-value*value
 expected=5*((-1)**(rung+1));norm=value*value-5*f*f
 if neighbor!=expected or norm!=4*((-1)**rung):raise ValueError('exact Cassini failure')
 mask=zeckendorf_encode(rung)
 if zeckendorf_decode(mask)!=rung:raise ValueError('Zeckendorf round trip failure')
 # Existing exact PrimeROM is one-based; n uses prime n+1 like LucasRecord.
 prime=_prime_rom().lookup(rung+1)
 admissible=policy.maximum_lucas is None or value<=policy.maximum_lucas
 return {'schema':'pythi_native_compute_v1','policy':policy.body(),'policy_digest':policy.digest(),'header_digest':digest.hex(),'header_bytes':len(header),'folded_left':f'{left:032x}','folded_right':f'{right:032x}','rung':rung,'rung_projection_is_bijective':False,'lucas_value':value,'fibonacci_pair':[f,f1],'lucas_neighbor_residue':neighbor,'cassini_expected':expected,'norm_residue':norm,'zeckendorf_mask':mask,'prime_address':prime,'pisot_bound':{'numerator':2**rung,'denominator':3**rung,'exponent':rung},'stages':list(STAGES),'work_digest_evaluations':1,'nonce_enumeration_evaluations':0,'admissible':admissible,'refusal':None if admissible else'native policy Lucas threshold','bitcoin_compatible':False,'network_submitted':False,'consensus_security_proven':False}
def compute_receipt(header,policy=None):
 policy=policy or NativePolicy();out=_payload(header,policy);out['certificate_id']=hashlib.sha256(canonical(out)).hexdigest();return out

def verify_receipt(receipt,header,policy=None):
 policy=policy or NativePolicy()
 if not isinstance(receipt,dict)or len(canonical(receipt))>65536:raise ValueError('bounded native receipt required')
 expected=_payload(header,policy);body=dict(receipt);identity=body.pop('certificate_id',None)
 if canonical(body)!=canonical(expected) or identity!=hashlib.sha256(canonical(body)).hexdigest():raise ValueError('native receipt verification failed')
 return True

def bounded_pisot_adjustment(current,observed_seconds,desired_seconds,max_delta=1):
 if type(current)is not int or not 1<=current<=8 or type(max_delta)is not int or not 0<=max_delta<=7:raise ValueError('bounded coordinate difficulty required')
 if not all(isinstance(x,(int,float))and not isinstance(x,bool)and math.isfinite(x)and x>0 for x in (observed_seconds,desired_seconds)):raise ValueError('positive measured durations required')
 phi=(1+math.sqrt(5))/2;raw=(math.log(desired_seconds)-math.log(observed_seconds))/math.log(phi)
 delta=max(-max_delta,min(max_delta,math.floor(raw)if raw>=0 else math.ceil(raw)));updated=max(1,min(8,current+delta))
 return {'previous':current,'updated':updated,'delta':updated-current,'max_delta':max_delta,'observed_seconds':observed_seconds,'desired_seconds':desired_seconds,'purpose':'bounded coordinate budget; not established consensus difficulty'}

def security_gate():
 from .projection_analysis import projection_contract
 return {'projection_analysis':projection_contract(),'deployable':False,'protocol':'pythi_native_compute_v1','kind':'local computation certificate, not consensus PoW','blocking_obligations':['adversarial header grinding and Sybil economics','difficulty and accumulated-work design','fork choice and reorg security','uniform-header/digest assumptions','formal theorem/compiler receipts','target hardware initiation interval, clock and energy measurement','testnet peer/chain implementation'],'testnet_deployed':False,'mainnet_deployed':False}

def capacity_model(cores,clock_hz,initiation_interval,occupancy=1.0,admissibility=1.0):
 if type(cores)is not int or cores<1 or type(initiation_interval)is not int or initiation_interval<1 or not math.isfinite(clock_hz)or clock_hz<=0 or not 0<=occupancy<=1 or not 0<=admissibility<=1:raise ValueError('explicit bounded hardware model inputs required')
 return {'classification':'MODELED_NOT_MEASURED','cores':cores,'clock_hz':clock_hz,'pipeline_depth':6,'initiation_interval_cycles':initiation_interval,'occupancy':occupancy,'admissibility':admissibility,'modeled_receipts_per_second':cores*clock_hz/initiation_interval*occupancy*admissibility,'hardware_measured':False}

def landauer_model(temperature_kelvin,erased_bits):
 if not isinstance(temperature_kelvin,(int,float))or not math.isfinite(temperature_kelvin)or temperature_kelvin<=0 or type(erased_bits)is not int or not 0<=erased_bits<=2**64:raise ValueError('positive temperature and explicit bounded erasure count required')
 return {'classification':'CONDITIONAL_LOWER_BOUND_NOT_MEASURED','temperature_kelvin':temperature_kelvin,'assumed_erased_bits':erased_bits,'joules_lower_bound':erased_bits*1.380649e-23*temperature_kelvin*math.log(2),'erasure_count_derived_from_algorithm':False,'physical_reversible_hardware_measured':False}
