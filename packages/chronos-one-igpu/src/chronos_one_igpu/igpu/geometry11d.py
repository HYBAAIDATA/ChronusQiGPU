"""Finite 11D phi geometry with exact Q(phi) certificates.

Fold: folded_i = v_i / (1 + sqrt(1 + ||v||^2_phi)) — carried exactly as
(certificate['numerator']_i, radical_squared = 1 + ||v||^2_phi in Q(phi));
the float API returns the certified projection. Unfold:
x_i = 2 f_i / (1 - ||f||^2_phi), exact in Q(phi).

The binary64 transport certificate is retained verbatim (it is honest:
IEEE-754 bit transport with Zeckendorf witnesses).
"""
import math, struct, hashlib, json
from fractions import Fraction
from ..lucas_engine import zeckendorf_encode, zeckendorf_decode
from ..family_algebra import PhiElement as Q, PHI

PHI_F = (1 + math.sqrt(5)) / 2
WEIGHTS_Q = tuple(PHI ** i for i in range(11))


def _q_float(x):
    return float(x.a) + float(x.b) * PHI_F


def _exact_vector(values):
    v = vector11d(values)
    return tuple(Fraction(x) for x in v)


def phi_norm_squared_exact(values):
    """Exact ||v||^2_phi = sum_i phi^i v_i^2 as a Q(phi) element."""
    v = _exact_vector(values)
    n2 = Q()
    for i, x in enumerate(v):
        n2 = n2 + Q(x * x) * WEIGHTS_Q[i]
    return n2


def fold_11d_exact(values):
    """Exact fold certificate: folded_i = v_i / (1 + sqrt(radical))."""
    v = _exact_vector(values)
    radical = Q(1) + phi_norm_squared_exact(v)
    from .exact_geometry import sign
    if sign(radical) <= 0:
        raise ValueError('fold radical must be positive')
    return {
        'form': 'v/(1+sqrt(radical_squared))',
        'numerator': [x for x in v],
        'radical_squared': radical,
        'dimensions': 11,
        'encoding': 'q_phi_11d_fold_v1',
    }


def fold_11d(values):
    """Certified float projection of the exact fold (contract preserved)."""
    cert = fold_11d_exact(values)
    t = math.sqrt(_q_float(cert['radical_squared']))
    return tuple(float(x) / (1.0 + t) for x in cert['numerator'])


def unfold_11d_exact(values):
    """Exact unfold: for folded f with ||f||^2_phi = n2, out_i = 2 f_i /
    (1 - n2), exact in Q(phi). Returns tuple of PhiElement."""
    v = _exact_vector(values)
    n2 = phi_norm_squared_exact(v)
    denom = Q(1) - n2
    from .exact_geometry import sign
    if sign(denom) <= 0:
        raise ValueError('folded vector must lie inside phi unit ball')
    inv = denom.inverse()
    return tuple(Q(2 * x) * inv for x in v)


def unfold_11d(values):
    """Certified float projection of the exact unfold (contract preserved)."""
    return tuple(_q_float(x) for x in unfold_11d_exact(values))


def vector11d(values):
    v = tuple(float(x) for x in values)
    if len(v) != 11 or not all(math.isfinite(x) for x in v):
        raise ValueError('finite 11D vector required')
    return v


def phi_norm(values):
    n2 = phi_norm_squared_exact(values)
    from .exact_geometry import sign
    if sign(n2) < 0:
        raise ValueError('11D phi norm must be non-negative')
    n = math.sqrt(_q_float(n2))
    if not math.isfinite(n):
        raise ValueError('11D norm overflow')
    return n


def zeckendorf_certificate(values):
    v = vector11d(values)
    bits = [struct.unpack('<Q', struct.pack('<d', x))[0] for x in v]
    codes = [zeckendorf_encode(x) for x in bits]
    body = {'encoding': 'ieee754_binary64_exact', 'bits': bits, 'codes': codes, 'dimensions': 11}
    return {**body, 'digest': hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def restore_certificate(certificate):
    body = dict(certificate); digest = body.pop('digest')
    if body.get('dimensions') != 11 or body.get('encoding') != 'ieee754_binary64_exact' or len(body.get('bits', [])) != 11 or len(body.get('codes', [])) != 11:
        raise ValueError('11D certificate shape mismatch')
    if hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != digest:
        raise ValueError('11D certificate tamper')
    if any(zeckendorf_decode(code) != bits for code, bits in zip(body['codes'], body['bits'])):
        raise ValueError('Zeckendorf witness mismatch')
    return vector11d(struct.unpack('<d', struct.pack('<Q', bits))[0] for bits in body['bits'])
