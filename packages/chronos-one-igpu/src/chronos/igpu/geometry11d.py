"""Finite 11D phi geometry with exact IEEE transport certificates."""
import math,struct,hashlib,json
from ..lucas_engine import zeckendorf_encode,zeckendorf_decode
PHI=(1+math.sqrt(5))/2
WEIGHTS=tuple(PHI**i for i in range(11))
def vector11d(values):
    v=tuple(float(x)for x in values)
    if len(v)!=11 or not all(math.isfinite(x)for x in v):raise ValueError('finite 11D vector required')
    return v
def phi_norm(values):
    v=vector11d(values);n=math.hypot(*(x*math.sqrt(w)for x,w in zip(v,WEIGHTS)))
    if not math.isfinite(n):raise ValueError('11D norm overflow')
    return n
def fold_11d(values):
    v=vector11d(values);n=phi_norm(v);denominator=1+math.hypot(1,n)
    folded=tuple(x/denominator for x in v)
    if phi_norm(folded)>=1:raise ValueError('fold reaches unrepresentable floating boundary; use exact certificate')
    return folded
def unfold_11d(values):
    v=vector11d(values);n=phi_norm(v)
    if n>=1:raise ValueError('folded vector must lie inside phi unit ball')
    return tuple(2*x/(1-n*n)for x in v)
def zeckendorf_certificate(values):
    v=vector11d(values);bits=[struct.unpack('<Q',struct.pack('<d',x))[0]for x in v]
    codes=[zeckendorf_encode(x)for x in bits]
    body={'encoding':'ieee754_binary64_exact','bits':bits,'codes':codes,'dimensions':11}
    return {**body,'digest':hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
def restore_certificate(certificate):
    body=dict(certificate);digest=body.pop('digest')
    if body.get('dimensions')!=11 or body.get('encoding')!='ieee754_binary64_exact' or len(body.get('bits',[]))!=11 or len(body.get('codes',[]))!=11:raise ValueError('11D certificate shape mismatch')
    if hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=digest:raise ValueError('11D certificate tamper')
    if any(zeckendorf_decode(code)!=bits for code,bits in zip(body['codes'],body['bits'])):raise ValueError('Zeckendorf witness mismatch')
    return vector11d(struct.unpack('<d',struct.pack('<Q',bits))[0]for bits in body['bits'])
