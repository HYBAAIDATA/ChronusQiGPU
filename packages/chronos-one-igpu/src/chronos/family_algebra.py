"""Exact additive extension of the supplied Fibonacci/Lucas core in Q(phi).

phi^2=phi+1, conjugate(phi)=1-phi. No floating-point inference of integers.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib,json
from .lucas_engine import fibonacci_pair,lucas,zeckendorf_encode,zeckendorf_decode

def _bounded(value):
    if isinstance(value,bool)or not isinstance(value,(int,Fraction)):raise ValueError('exact integer/rational coefficients required')
    value=Fraction(value)
    if max(value.numerator.bit_length(),value.denominator.bit_length())>65536:raise ValueError('coefficient bit quota exceeded')
    return value

def _index(n):
    if type(n)is not int or not 0<=n<=10000:raise ValueError('index must lie in [0,10000]')

def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

@dataclass(frozen=True)
class PhiElement:
    """a+b*phi, with exact rational coefficients and ring operations."""
    a:Fraction=Fraction(0)
    b:Fraction=Fraction(0)
    def __post_init__(self):
        object.__setattr__(self,'a',_bounded(self.a));object.__setattr__(self,'b',_bounded(self.b))
    def __add__(self,other):
        if not isinstance(other,PhiElement):other=PhiElement(other)
        return PhiElement(self.a+other.a,self.b+other.b)
    def __neg__(self):return PhiElement(-self.a,-self.b)
    def __sub__(self,other):return self+(-other if isinstance(other,PhiElement)else PhiElement(-_bounded(other)))
    def __mul__(self,other):
        if not isinstance(other,PhiElement):other=PhiElement(other)
        return PhiElement(self.a*other.a+self.b*other.b,self.a*other.b+self.b*other.a+self.b*other.b)
    def conjugate(self):return PhiElement(self.a+self.b,-self.b)
    def trace(self):return 2*self.a+self.b
    def norm(self):return self.a*self.a+self.a*self.b-self.b*self.b
    def inverse(self):
        n=self.norm()
        if not n:raise ZeroDivisionError('zero field element')
        c=self.conjugate();return PhiElement(c.a/n,c.b/n)
    def __pow__(self,n):
        if type(n)is not int or not -10000<=n<=10000:raise ValueError('bounded integer power required')
        if n<0:return self.inverse()**(-n)
        base=self;result=PhiElement(1)
        while n:
            if n&1:result=result*base
            n>>=1
            if n:base=base*base
        return result
    def to_dict(self):return {'encoding':'q_phi_v1','a':[self.a.numerator,self.a.denominator],'b':[self.b.numerator,self.b.denominator]}

PHI=PhiElement(0,1)

@dataclass(frozen=True)
class FibonacciOrbit:
    index:int
    f:int
    next_f:int
    @classmethod
    def at(cls,n):
        _index(n);return cls(n,*fibonacci_pair(n))
    def verify(self):
        _index(self.index)
        if type(self.f)is not int or type(self.next_f)is not int or (self.f,self.next_f)!=fibonacci_pair(self.index):raise ValueError('orbit does not match supplied exact core')
        return True
    def compose(self,other):
        self.verify();other.verify();_index(self.index+other.index)
        # Q^(m+n)=Q^m Q^n; compose directly from the stored pair.
        result=FibonacciOrbit(self.index+other.index,self.f*other.next_f+(self.next_f-self.f)*other.f,self.f*other.f+self.next_f*other.next_f)
        result.verify();return result
    def phi_power(self):return PhiElement(self.next_f-self.f,self.f)
    def lucas(self):return 2*self.next_f-self.f

class FamilyCertificate:
    """A replayable exact identity certificate; derives from original core values."""
    @staticmethod
    def create(indices):
        indices=list(indices)
        if not 1<=len(indices)<=16:raise ValueError('1–16 family indices required')
        for n in indices:_index(n)
        _index(sum(indices));orbit=FibonacciOrbit.at(0);product=PhiElement(1)
        for n in indices:
            term=FibonacciOrbit.at(n);orbit=orbit.compose(term);product=product*term.phi_power()
        n=sum(indices);f,fn=fibonacci_pair(n);ln=lucas(n);sign=(-1)**n
        assert product==orbit.phi_power() and product.trace()==ln and product.norm()==sign
        assert ln*ln-5*f*f==4*sign
        body={'schema':'chronos_family_certificate_v1','indices':indices,'combined_index':n,'fibonacci_pair':[f,fn],'lucas':ln,'phi_power':product.to_dict(),'norm':sign,'pell_cassini_residual':ln*ln-5*f*f,'zeckendorf':{'fibonacci':zeckendorf_encode(f),'lucas':zeckendorf_encode(ln)},'authority':'supplied_exact_lucas_engine','proof_kind':'exact_identity_replay'}
        return {**body,'digest':hashlib.sha256(_json(body)).hexdigest()}
    @staticmethod
    def verify(certificate):
        if not isinstance(certificate,dict):raise ValueError('certificate mapping required')
        expected=FamilyCertificate.create(certificate['indices'])
        if certificate!=expected:raise ValueError('family certificate identity or custody mismatch')
        assert zeckendorf_decode(certificate['zeckendorf']['fibonacci'])==certificate['fibonacci_pair'][0]
        return True

def triple_identity(n):
    _index(n);_index(3*n);f=fibonacci_pair(n)[0];l=lucas(n);sign=(-1)**n
    result={'index':n,'L_3n':l*l*l-3*sign*l,'F_3n':f*(l*l-sign),'norm':sign}
    if result['L_3n']!=lucas(3*n)or result['F_3n']!=fibonacci_pair(3*n)[0]:raise ValueError('triple identity mismatch')
    return result
