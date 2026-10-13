"""Generic prepared dense/activation kernels over the preserved exact Q(phi).

No trained model, ANE dispatch or quantum neural speedup is invented. These are
exact tensor/neural operations; requested Hamiltonian evolution stays in the
separate exact quantum engine. Zero-elimination follows exact field equality.
"""
from fractions import Fraction
from dataclasses import dataclass
import hashlib
from pathlib import Path
from ..family_algebra import PhiElement
from .resident import canonical

MAX_BITS=4096


def value(v):
    if isinstance(v,PhiElement): result=v
    elif type(v)is int or isinstance(v,Fraction): result=PhiElement(v)
    elif isinstance(v,dict) and set(v)=={'encoding','a','b'} and v['encoding']=='q_phi_v1':
        coeff=[]
        for pair in (v['a'],v['b']):
            if not isinstance(pair,list) or len(pair)!=2 or any(type(n)is not int for n in pair) or pair[1]<=0:
                raise ValueError('canonical exact rational coefficients required')
            f=Fraction(*pair)
            if [f.numerator,f.denominator]!=pair:raise ValueError('noncanonical coefficient')
            coeff.append(f)
        result=PhiElement(*coeff)
    else: raise ValueError('exact Q(phi) scalar required; no float fallback')
    if any(max(abs(f.numerator).bit_length(),f.denominator.bit_length())>MAX_BITS for f in (result.a,result.b)):
        raise ValueError('neural coefficient bit quota')
    return result


def sign(v):
    v=value(v);u=2*v.a+v.b;w=v.b
    if not u:return (w>0)-(w<0)
    if not w:return (u>0)-(u<0)
    if (u>0)==(w>0):return 1 if u>0 else -1
    dominant=u if u*u>5*w*w else w
    return 1 if dominant>0 else -1


def matrix(rows,max_items=16384):
    if not isinstance(rows,(tuple,list)) or not rows or len(rows)>128:
        raise ValueError('bounded nonempty exact matrix required')
    if any(not isinstance(row,(tuple,list)) for row in rows) or not rows[0] or len(rows[0])>128 or any(len(row)!=len(rows[0])for row in rows) or len(rows)*len(rows[0])>max_items:
        raise ValueError('bounded rectangular exact matrix required')
    return tuple(tuple(value(v)for v in row)for row in rows)


def encode(rows):return [[value(v).to_dict()for v in row]for row in rows]


def _digest(x):return hashlib.sha256(canonical(x)).hexdigest()


@dataclass(frozen=True)
class PreparedLayer:
    weights:tuple
    bias:tuple
    activation:str
    columns:tuple

    @classmethod
    def create(cls,weights,bias,activation='relu'):
        w=matrix(weights)
        if activation not in('identity','relu')or not isinstance(bias,(tuple,list))or len(bias)!=len(w[0]):
            raise ValueError('explicit bounded activation and bias required')
        b=tuple(value(v)for v in bias)
        cols=tuple(tuple((i,w[i][j])for i in range(len(w))if w[i][j]!=PhiElement())for j in range(len(w[0])))
        return cls(w,b,activation,cols)

    def execute(self,inputs,max_scalar_ops=1000000):
        x=matrix(inputs)
        if len(x[0])!=len(self.weights):raise ValueError('network input width mismatch')
        dense=len(x)*len(self.weights)*len(self.bias)
        if dense>max_scalar_ops:raise ValueError('admitted dense-work quota exceeded')
        rational=all(v.b==0 for row in x for v in row)and all(v.b==0 for row in self.weights for v in row)and all(v.b==0 for v in self.bias)
        out=[]
        for row in x:
            vals=[]
            for bias,column in zip(self.bias,self.columns):
                total=bias
                if rational:
                    exact=total.a
                    for index,coefficient in column:exact+=row[index].a*coefficient.a
                    total=value(PhiElement(exact))
                else:
                    for index,coefficient in column:total=value(total+value(row[index]*coefficient))
                vals.append(PhiElement()if self.activation=='relu'and sign(total)<0 else total)
            out.append(tuple(vals))
        return tuple(out),{'scalar_products':len(x)*sum(len(c)for c in self.columns),'dense_scalar_products':dense,
                          'zero_coefficients_eliminated':len(x)*(len(self.weights)*len(self.bias)-sum(len(c)for c in self.columns)),
                          'kernel_branch':'exact_rational_subfield'if rational else'exact_qphi_field'}

    def reference(self,inputs):
        # Separate full dense summation, never the prepared sparse-column loop.
        x=matrix(inputs);out=[]
        if len(x[0])!=len(self.weights):raise ValueError('reference width mismatch')
        for row in x:
            result=[]
            for j,bias in enumerate(self.bias):
                products=[value(row[i]*self.weights[i][j])for i in range(len(row))]
                total=bias
                for product in products:total=value(total+product)
                result.append(PhiElement()if self.activation=='relu'and sign(total)<0 else total)
            out.append(tuple(result))
        return tuple(out)

    def manifest(self):
        return {'weights':encode(self.weights),'bias':[v.to_dict()for v in self.bias],'activation':self.activation}


class PreparedNetwork:
    def __init__(self,layers):
        if not isinstance(layers,(list,tuple))or not 1<=len(layers)<=16:raise ValueError('bounded exact network layers required')
        built=[]
        for layer in layers:
            if not isinstance(layer,dict)or set(layer)!={'weights','bias','activation'}:raise ValueError('sealed layer fields required')
            built.append(PreparedLayer.create(**layer))
        if any(len(a.bias)!=len(b.weights)for a,b in zip(built,built[1:])):raise ValueError('network layer shape mismatch')
        self.layers=tuple(built);self._spec_bytes=canonical([layer.manifest()for layer in self.layers]);self.digest=hashlib.sha256(self._spec_bytes).hexdigest()

    @property
    def spec(self):
        import json
        return json.loads(self._spec_bytes)

    def execute(self,inputs,max_scalar_ops=1000000):
        x=matrix(inputs);total=0;dense=0;eliminated=0;stages=[]
        # Admit the complete network before executing any layer.
        remaining=sum(len(x)*len(layer.weights)*len(layer.bias)for layer in self.layers)
        if remaining>max_scalar_ops:raise ValueError('complete network work quota exceeded')
        for layer in self.layers:
            x,work=layer.execute(x,max_scalar_ops);stages.append(work)
            total+=work['scalar_products'];dense+=work['dense_scalar_products'];eliminated+=work['zero_coefficients_eliminated']
        return x,{'scalar_products':total,'dense_scalar_products':dense,'zero_coefficients_eliminated':eliminated,'layers':stages}

    def reference(self,inputs):
        x=matrix(inputs)
        for layer in self.layers:x=layer.reference(x)
        return x

    def verify(self,inputs,output):
        if encode(self.reference(inputs))!=output:raise ValueError('independent exact neural verification failed')
        return True


def tensor(operation,left,right,max_scalar_ops=1000000):
    a=matrix(left);b=matrix(right)
    if operation=='matmul':
        layer=PreparedLayer.create(b,[0]*len(b[0]),'identity')
        output,work=layer.execute(a,max_scalar_ops)
        if layer.reference(a)!=output:raise ValueError('independent exact tensor verification failed')
    elif operation in('add','hadamard'):
        if len(a)!=len(b)or len(a[0])!=len(b[0]):raise ValueError('matching exact shapes required')
        if len(a)*len(a[0])>max_scalar_ops:raise ValueError('tensor work quota')
        output=tuple(tuple(value(x+y if operation=='add'else x*y)for x,y in zip(ar,br))for ar,br in zip(a,b))
        work={'scalar_products':0 if operation=='add'else len(a)*len(a[0]),'dense_scalar_products':0 if operation=='add'else len(a)*len(a[0]),'zero_coefficients_eliminated':0}
    else:raise ValueError('explicit exact tensor algorithm required')
    return encode(output),work
