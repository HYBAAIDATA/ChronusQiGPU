"""Exact modular arithmetic and immutable unimodular PV registry."""
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

class UnregisteredFamilyError(ValueError):
    pass

def _nat(n):
    if type(n) is not int or n < 0:
        raise ValueError("nonnegative integer required")
    return n

def _mod(mod):
    if mod is not None and (type(mod) is not int or mod <= 0):
        raise ValueError("positive integer modulus required")
    return mod

def fib_pair(n, mod=None):
    _nat(n)
    _mod(mod)
    a, b = 0, 1 if mod is None else 1 % mod
    for bit in bin(n)[2:]:
        c, d = a*(2*b-a), a*a+b*b
        if mod is not None:
            c, d = c % mod, d % mod
        a, b = (d, c+d) if bit == "1" else (c,d)
        if mod is not None:
            b %= mod
    return a,b

def mat_identity(d):
    if type(d) is not int or d <= 0:
        raise ValueError("positive dimension required")
    return tuple(tuple(int(i==j) for j in range(d)) for i in range(d))

def _matrix(m):
    if not isinstance(m, (tuple,list)) or not m or any(
        not isinstance(row,(tuple,list)) or len(row)!=len(m) or
        any(type(v) is not int for v in row) for row in m):
        raise ValueError("square integer matrix required")
    return tuple(tuple(row) for row in m)

def mat_mul(a,b,mod=None):
    a,b = _matrix(a),_matrix(b)
    _mod(mod)
    d = len(a)
    if len(b) != d:
        raise ValueError("dimension mismatch")
    def entry(i,j):
        v = sum(a[i][k]*b[k][j] for k in range(d))
        return v if mod is None else v % mod
    return tuple(tuple(entry(i,j) for j in range(d)) for i in range(d))

def mat_pow(m,n,mod=None):
    m = _matrix(m)
    _nat(n)
    _mod(mod)
    res = mat_identity(len(m))
    if mod is not None:
        res = tuple(tuple(v%mod for v in row) for row in res)
        m = tuple(tuple(v%mod for v in row) for row in m)
    while n:
        if n & 1:
            res = mat_mul(res,m,mod)
        n >>= 1
        if n:
            m = mat_mul(m,m,mod)
    return res

def lucas_uv(n,p,q,mod=None):
    _nat(n)
    _mod(mod)
    if type(p) is not int or type(q) is not int:
        raise ValueError("integer recurrence coefficients required")
    m = mat_pow(((p,-q),(1,0)),n,mod)
    u,v = m[1][0],2*m[0][0]-p*m[1][0]
    return (u,v) if mod is None else (u%mod,v%mod)

def determinant(m):
    m = _matrix(m)
    if len(m)==1:
        return m[0][0]
    return sum((-1)**j*v*determinant(tuple(
        tuple(row[k] for k in range(len(m)) if k!=j)
        for row in m[1:])) for j,v in enumerate(m[0]))

def polynomial_value(poly,x):
    v = 0
    for c in poly:
        v = v*x+c
    return v

@dataclass(frozen=True)
class PVFamily:
    name: str
    polynomial: tuple
    companion: tuple
    det: int
    alpha_lower: Fraction
    mu_upper: Fraction

    @property
    def degree(self):
        return len(self.companion)

    def conjugate_power_exponent(self,k):
        """Exact descriptor: |mu|max**k is the designated root alpha to this power."""
        return Fraction(-_nat(k),1 if self.degree==2 else 2)

    def contraction_bound(self,k):
        return self.mu_upper**_nat(k)

    def certify(self):
        # The stated root bounds are exact. Cubic discriminants < 0
        # imply the other roots are complex conjugate; their product
        # is 1/alpha. Quadratic conjugate modulus is 1/alpha.
        p = self.polynomial
        if determinant(self.companion)!=self.det or abs(self.det)!=1:
            raise ArithmeticError("non-unimodular companion")
        # Cayley-Hamilton witness by polynomial evaluation.
        ident = mat_identity(self.degree)
        acc = tuple(tuple(0 for _ in row) for row in ident)
        for c in p:
            acc = mat_mul(acc,self.companion)
            acc = tuple(tuple(acc[i][j]+c*ident[i][j]
                              for j in range(self.degree)) for i in range(self.degree))
        if any(v for row in acc for v in row):
            raise ArithmeticError("companion polynomial mismatch")
        if not 1 < self.alpha_lower < 3 or not 0 < self.mu_upper < 1:
            raise ArithmeticError("invalid isolating bounds")
        if not polynomial_value(p,self.alpha_lower)<0<polynomial_value(p,Fraction(3)):
            raise ArithmeticError("root bracket failed")
        if self.degree==3:
            _,a,b,c = p
            disc = a*a*b*b-4*b**3-4*a**3*c-27*c*c+18*a*b*c
            if disc>=0 or p[-1]!=-1 or self.alpha_lower*self.mu_upper**2<1:
                raise ArithmeticError("cubic conjugate bound failed")
        elif self.degree==2:
            if p[-1]!=-1 or self.alpha_lower*self.mu_upper<1:
                raise ArithmeticError("quadratic conjugate bound failed")
        else:
            raise ArithmeticError("unsupported degree")
        return True

    def root_interval(self, refinements=80):
        self.certify()
        lo,hi = self.alpha_lower,Fraction(3)
        for _ in range(_nat(refinements)):
            mid=(lo+hi)/2
            if polynomial_value(self.polynomial,mid)>0:
                hi=mid
            else:
                lo=mid
        return lo,hi

PV_REGISTRY = MappingProxyType({
    "golden": PVFamily("golden",(1,-1,-1),((1,1),(1,0)),-1,Fraction(8,5),Fraction(5,8)),
    "silver": PVFamily("silver",(1,-2,-1),((2,1),(1,0)),-1,Fraction(12,5),Fraction(5,12)),
    "plastic": PVFamily("plastic",(1,0,-1,-1),((0,1,0),(0,0,1),(1,1,0)),1,Fraction(5,4),Fraction(9,10)),
    "supergolden": PVFamily("supergolden",(1,-1,0,-1),((1,0,1),(1,0,0),(0,1,0)),1,Fraction(13,9),Fraction(5,6)),
    "tribonacci": PVFamily("tribonacci",(1,-1,-1,-1),((1,1,1),(1,0,0),(0,1,0)),1,Fraction(9,5),Fraction(3,4)),
})

def get_family(name):
    if type(name) is not str or name not in PV_REGISTRY:
        raise UnregisteredFamilyError("unregistered PV family")
    return PV_REGISTRY[name]

def pisano_period_pow2(bits):
    if type(bits) is not int or bits<1:
        raise ValueError("positive integer width required")
    return 3 << (bits-1)

def generalized_pisano_period(family_name,mod,max_steps=100_000):
    fam = get_family(family_name)
    _mod(mod)
    if mod is None or type(max_steps) is not int or max_steps<1:
        raise ValueError("positive modulus and search bound required")
    if mod==1:
        return 1
    if family_name=="golden" and mod&(mod-1)==0:
        return pisano_period_pow2(mod.bit_length()-1)
    ident,cur = mat_identity(fam.degree),mat_identity(fam.degree)
    for k in range(1,max_steps+1):
        cur=mat_mul(cur,fam.companion,mod)
        if cur==ident:
            return k
    raise RuntimeError("exact order exceeds search bound")

def generalized_lucas(family_name,n,mod=None):
    """Exact power sum of all conjugate roots: trace(C_family**n)."""
    family=get_family(family_name)
    matrix=mat_pow(family.companion,n,mod)
    value=sum(matrix[i][i] for i in range(family.degree))
    return value if mod is None else value%mod
