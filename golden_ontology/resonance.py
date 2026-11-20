"""Exact Q(sqrt(5)) certificates; explicit numerical projection."""
from dataclasses import dataclass
from .substrate import fib_pair

@dataclass(frozen=True)
class AlgebraicCertificate:
    k: int
    p: int
    q: int
    norm: int
    expected_norm: int

    @property
    def norm_certified(self):
        return self.norm==self.expected_norm

    def to_float(self):
        # Reject forged certificates and avoid cancellation of large
        # conjugate coefficients. This method is numerical only.
        if self!=phi_neg_power_cert(self.k) or not self.norm_certified:
            raise ValueError("invalid algebraic certificate")
        return ((5**0.5-1)/2)**self.k

def phi_neg_power_cert(k):
    f,g=fib_pair(k)
    sign=-1 if k%2 else 1
    p,q=sign*(2*g-f),-sign*f
    cert=AlgebraicCertificate(k,p,q,p*p-5*q*q,4*sign)
    if not cert.norm_certified:
        raise ArithmeticError("field norm mismatch")
    return cert

def certify_pairwise_irrationality(indices):
    if any(type(k) is not int or k<0 for k in indices) or len(set(indices))!=len(indices):
        raise ValueError("distinct nonnegative integer indices required")
    return [(i,j,fib_pair(abs(j-i))[0])
            for a,i in enumerate(indices) for j in indices[a+1:]]
