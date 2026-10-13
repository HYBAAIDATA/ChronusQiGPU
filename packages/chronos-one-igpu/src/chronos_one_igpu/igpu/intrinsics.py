"""Typed exact mathematical intrinsics, reusing the preserved sequence core."""
import hashlib,json
from fractions import Fraction
from ..lucas_engine import fibonacci_pair,lucas,zeckendorf_encode,zeckendorf_decode
from ..family_algebra import PHI
OPS=('fibonacci','lucas','binet_exact','cassini','zeckendorf_encode','zeckendorf_decode','pisot_schedule','phi_weight')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def integer(n,maximum=10000):
    if type(n)is not int or not 0<=n<=maximum:raise ValueError('bounded exact integer required')
    return n

def execute_intrinsic(node):
    if not isinstance(node,dict)or node.get('op') not in OPS:raise ValueError('typed intrinsic required')
    node=json.loads(canonical(node));op=node['op'];fields={'op','n'}
    if op=='cassini':fields|={'previous','current','next'}
    if op=='pisot_schedule':fields|={'modulus','count'}
    if op=='phi_weight':fields|={'numerator','denominator'}
    if set(node)!=fields:raise ValueError('exact intrinsic fields required')
    n=integer(node['n'],2**93-1 if op=='zeckendorf_decode'else 2**64-1 if op=='zeckendorf_encode'else 10000)
    if op=='fibonacci':value=fibonacci_pair(n)[0]
    elif op=='lucas':value=lucas(n)
    elif op=='binet_exact':
        power=PHI**n;f=fibonacci_pair(n)[0]
        if power.trace()!=lucas(n)or power.b!=f or power.norm()!=(-1)**n:raise ValueError('exact Binet identity failed')
        value={'phi_power':power.to_dict(),'fibonacci':f,'lucas':lucas(n),'norm':int(power.norm())}
    elif op=='cassini':
        if n<1:raise ValueError('Cassini index must be positive')
        for key in ('previous','current','next'):integer(node[key],1<<16384)
        p,c,t=(node[key]for key in ('previous','current','next'))
        residue=p*t-c*c
        if (p,c,t)!=(lucas(n-1),lucas(n),lucas(n+1))or residue!=5*(-1)**(n+1):raise ValueError('supplied Lucas Cassini witnesses invalid')
        value={'residue':residue,'verified_supplied_witnesses':True}
    elif op=='zeckendorf_encode':value=zeckendorf_encode(n)
    elif op=='zeckendorf_decode':
        value=zeckendorf_decode(n)
        if value>2**64-1 or zeckendorf_encode(value)!=n:raise ValueError('noncanonical Zeckendorf mask')
    elif op=='pisot_schedule':
        modulus=integer(node['modulus'],2**64-1);count=integer(node['count'],4096)
        if modulus<1:raise ValueError('positive modulus required')
        # Exact modular recurrence; no floating power or ever-growing integers.
        a,b=lucas(n)%modulus,lucas(n+1)%modulus;value=[]
        for _ in range(count):value.append(a);a,b=b,(a+b)%modulus
    else:
        num=node['numerator'];den=node['denominator']
        if type(num)is not int or type(den)is not int or not 0<den<=2**64 or abs(num)>2**64:raise ValueError('bounded rational weight required')
        value=(PHI**n*Fraction(num,den)).to_dict()
    body={'schema':'chronos_exact_intrinsic_v1','node':node,'value':value,'authority':'preserved_lucas_engine','execution_backend':'cpu_exact'}
    return {**body,'digest':hashlib.sha256(canonical(body)).hexdigest()}

def verify_intrinsic(receipt):
    if not isinstance(receipt,dict)or canonical(receipt)!=canonical(execute_intrinsic(receipt['node'])):raise ValueError('intrinsic certificate mismatch')
    return True
