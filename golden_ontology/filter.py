"""Certified PV algebraic bounds and separate numerical filtering.

A symmetric normalized kernel smooths a sequence; the PV conjugate bound
is not a theorem about RMSE, noise removal or a finite-record phase response.
"""
from dataclasses import dataclass
from fractions import Fraction
import math
from .substrate import get_family

@dataclass(frozen=True)
class ContractionCertificate:
    family: str
    radius: int
    mu_upper: Fraction
    bound_at_radius: Fraction
    alpha_polynomial: tuple
    alpha_root_interval: tuple
    alpha_exponent: Fraction

class PisotFilter:
    def __init__(self,family="golden",radius=4):
        if type(radius) is not int or radius<1:
            raise ValueError("positive integer radius required")
        self.family=get_family(family)
        self.radius=radius
        lo,hi=self.family.root_interval()
        alpha=float((lo+hi)/2)
        raw=[alpha**(-abs(k)) for k in range(-radius,radius+1)]
        total=math.fsum(raw)
        self.kernel=tuple(w/total for w in raw)
        self.certificate=ContractionCertificate(
            family,radius,self.family.mu_upper,self.family.contraction_bound(radius),
            self.family.polynomial,(lo,hi),self.family.conjugate_power_exponent(radius))

    def apply(self,signal):
        if any(type(v) is bool or not math.isfinite(v) for v in signal):
            raise ValueError("finite ordered samples required")
        n,r=len(signal),self.radius
        return [math.fsum(self.kernel[k+r]*signal[min(max(i+k,0),n-1)]
                          for k in range(-r,r+1)) for i in range(n)]

class NonMonotoneWarpError(ValueError):
    pass

def _finite(values):
    if any(type(v) is bool or not isinstance(v,(int,float,Fraction)) or
           (isinstance(v,float) and not math.isfinite(v)) for v in values):
        raise NonMonotoneWarpError("finite real values required")

class ZeckendorfMap:
    @staticmethod
    def encode_ranks(values):
        _finite(values)
        ranks={v:i+1 for i,v in enumerate(sorted(set(values)))}
        return [ZeckendorfMap._zeckendorf(ranks[v]) for v in values]

    @staticmethod
    def _zeckendorf(n):
        if type(n) is not int or n<0:
            raise ValueError("nonnegative integer required")
        fibs=[1,2]
        while fibs[-1]<=n:
            fibs.append(fibs[-1]+fibs[-2])
        out=[]
        for f in reversed(fibs):
            if f<=n:
                out.append(f)
                n-=f
        return tuple(out)

    @staticmethod
    def verify_monotone_warp(original,warped):
        if len(original)!=len(warped):
            raise NonMonotoneWarpError("length mismatch")
        _finite(original)
        _finite(warped)
        order=sorted(range(len(original)),key=original.__getitem__)
        for i,j in zip(order,order[1:]):
            if (original[i]==original[j] and warped[i]!=warped[j]) or (
                original[i]<original[j] and not warped[i]<warped[j]):
                raise NonMonotoneWarpError("order or tie class changed")
