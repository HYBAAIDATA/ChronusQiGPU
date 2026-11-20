"""Optional numerical evaluation of exact descriptors; stdlib only.

This is not the exact Chronus execution namespace. The functions consume
symbolic coordinate/frequency descriptors supplied by the exact producer.
"""
import math
from fractions import Fraction
from .substrate import get_family

def project_q5(x):
    return float(x.a)+float(x.b)*math.sqrt(5)

def project_kronecker(points):
    return [project_q5(x) for x in points]

def project_phyllotaxis(points):
    result=[]
    for r2,turns in points:
        radius,theta=math.sqrt(float(r2)),math.tau*project_q5(turns)
        result.append((radius*math.cos(theta),radius*math.sin(theta)))
    return result

def golden_section_minimize(f, a, b, tol=1e-12, max_iter=200):
    """Numerical reference for a strictly unimodal floating objective."""
    if not all(math.isfinite(x) for x in (a, b, tol)) or not a < b or tol <= 0:
        raise ValueError("invalid bracket")
    ratio = (math.sqrt(5)-1)/2

    def evaluate(x):
        value = f(x)
        if not math.isfinite(value):
            raise ValueError("nonfinite objective")
        return value

    def probes(a,b):
        width=b-a
        if math.isfinite(width):
            return b-ratio*width, a+ratio*width
        return ratio*a+(1-ratio)*b, (1-ratio)*a+ratio*b

    c,d=probes(a,b)
    fc, fd, count = evaluate(c), evaluate(d), 2
    if type(max_iter) is not int or max_iter<0:
        raise ValueError("nonnegative integer iteration limit required")
    for _ in range(max_iter):
        if b-a <= tol:
            break
        if c >= d or not a < c < b or not a < d < b:
            candidates={c:fc,d:fd}
            for endpoint in (a,b):
                if endpoint not in candidates:
                    candidates[endpoint]=evaluate(endpoint)
                    count+=1
            x=min(candidates,key=candidates.get)
            # Return only when every representable candidate was evaluated.
            if any(math.nextafter(u,v)!=v for u,v in zip(sorted(candidates),sorted(candidates)[1:])):
                raise ArithmeticError("numerical resolution exhausted")
            return x,candidates[x],count
        if fc <= fd:
            b, d, fd = d, c, fc
            c = probes(a,b)[0]
            fc = evaluate(c)
        else:
            a, c, fc = c, d, fd
            d = probes(a,b)[1]
            fd = evaluate(d)
        count += 1
    if b-a > tol:
        raise ArithmeticError("requested bracket tolerance not reached")
    x = a/2+b/2
    return x, evaluate(x), count+1


def numeric_frequency(frequency,scale=Fraction(1)):
    # Isolate the family root exactly, then project for numerical reference.
    lo,hi=get_family(frequency.family).root_interval()
    phase=frequency.base*scale*(1+frequency.coefficient*(lo+hi)/2)
    try:
        projected=float(phase)
    except OverflowError as exc:
        raise ValueError("nonfinite projected phase") from exc
    if not math.isfinite(projected):
        raise ValueError("nonfinite projected phase")
    return projected

def evolve_blocks(state,frequencies,time_step):
    if not state or len(state)%2 or not math.isfinite(time_step):
        raise ValueError("nonempty even state and finite time required")
    if len(frequencies)!=len(state)//2:
        raise ValueError("frequency/state shape mismatch")
    state=[complex(x) for x in state]
    if any(not math.isfinite(x.real) or not math.isfinite(x.imag) for x in state):
        raise ValueError("nonfinite state")
    out,residual=[],0.0
    for i,frequency in enumerate(frequencies):
        phase=numeric_frequency(frequency,Fraction(str(time_step)))
        c,s=math.cos(phase),math.sin(phase)
        a,b=state[2*i:2*i+2]
        out.extend((c*a-1j*s*b,c*b-1j*s*a))
        residual=max(residual,abs(c*c+s*s-1))
    if any(not math.isfinite(x.real) or not math.isfinite(x.imag) for x in out):
        raise ValueError("nonfinite output")
    return out,residual
