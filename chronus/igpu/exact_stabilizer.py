"""Exact bit-packed Clifford stabilizers, not statevector truncation or QPU.

A row encodes i**phase X**x Z**z. All updates and Born queries use integer
GF(2) algebra. Full declared register GHZ/cluster states need O(n**2) bits,
not an amplitude array. Arbitrary non-Clifford evolution is not substituted.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
from pathlib import Path
import time
from .feature_profile import FeatureProfile
from .resident import canonical


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def multiply(a, b):
    return (a[0] ^ b[0], a[1] ^ b[1], (a[2] + b[2] + 2 * (a[1] & b[0]).bit_count()) % 4)


def _commute(a, b):
    return ((a[0] & b[1]).bit_count() + (a[1] & b[0]).bit_count()) % 2 == 0


def _eliminate(rows, vector):
    """Exact row reduction; dependent projected rows become kernel generators."""
    basis = {}; kernel = []
    for original in rows:
        row = original
        bits = vector(row)
        while bits:
            pivot = bits.bit_length()-1
            if pivot not in basis:
                basis[pivot] = row
                break
            row = multiply(row, basis[pivot]); bits = vector(row)
        if not bits:
            kernel.append(row)
    return tuple(basis.values()), tuple(kernel)


@dataclass(frozen=True)
class StabilizerState:
    n: int
    rows: tuple

    @classmethod
    def zero(cls, n):
        if type(n) is not int or not 1 <= n <= 4096:
            raise ValueError("bounded stabilizer register required")
        return cls(n, tuple((0, 1 << i, 0) for i in range(n)))

    def gate(self, name, a, b=None):
        if type(a) is not int or not 0 <= a < self.n or name not in ('H','S','CX','CZ','SWAP'):
            raise ValueError("exact Clifford gate required")
        if name in ('CX','CZ','SWAP') and (type(b) is not int or not 0 <= b < self.n or a == b):
            raise ValueError("distinct bounded gate endpoints required")
        if name == 'CZ':
            return self.gate('H', b).gate('CX', a, b).gate('H', b)
        if name == 'SWAP':
            return self.gate('CX', a, b).gate('CX', b, a).gate('CX', a, b)
        rows = []
        for x, z, phase in self.rows:
            xa = (x >> a) & 1; za = (z >> a) & 1
            if name == 'H':
                phase = (phase + 2 * xa * za) % 4
                if xa != za:
                    x ^= 1 << a; z ^= 1 << a
            elif name == 'S':
                phase = (phase + xa) % 4
                z ^= xa << a
            else:
                x ^= xa << b; z ^= ((z >> b) & 1) << a
            rows.append((x, z, phase))
        return StabilizerState(self.n, tuple(rows))

    def verify(self):
        if type(self.n) is not int or not 1 <= self.n <= 4096:
            raise ValueError("bounded stabilizer register required")
        if len(self.rows) != self.n:
            raise ValueError("complete stabilizer generators required")
        limit = 1 << self.n
        for row in self.rows:
            if not isinstance(row, tuple) or len(row) != 3 or any(type(v) is not int for v in row):
                raise ValueError("exact integer Pauli row required")
            x,z,p = row
            if not 0 <= x < limit or not 0 <= z < limit or not 0 <= p < 4 or p % 2 != (x & z).bit_count() % 2:
                raise ValueError("Hermitian bounded Pauli row required")
        for i, row in enumerate(self.rows):
            if any(not _commute(row, other) for other in self.rows[i+1:]):
                raise ValueError("stabilizers do not commute")
        basis, kernel = _eliminate(self.rows, lambda r: r[0] | r[1] << self.n)
        if len(basis) != self.n or kernel:
            raise ValueError("independent pure-state generators required")
        return True

    def born(self, assignments):
        """Exact joint Z-basis probability, without enumerating 2**n outcomes."""
        if not isinstance(assignments, dict) or any(type(k) is not int or not 0 <= k < self.n or type(v) is not int or v not in (0,1) for k,v in assignments.items()):
            raise ValueError("bounded exact basis assignment required")
        self.verify()
        mask = sum(1 << k for k in assignments)
        bits = sum(v << k for k,v in assignments.items())
        _, diagonal = _eliminate(self.rows, lambda r: r[0])
        _, supported = _eliminate(diagonal, lambda r: r[1] & ~mask)
        # Kernel rows form independent diagonal constraints restricted to mask.
        for x,z,p in supported:
            if p not in (0,2) or x:
                raise ValueError("invalid diagonal stabilizer kernel")
            if (z & bits).bit_count() % 2 != p//2:
                return Fraction(0)
        return Fraction(1, 1 << (len(assignments)-len(supported)))

    def to_dict(self):
        return {'qubits': self.n, 'paulis': [[x,z,p] for x,z,p in self.rows], 'encoding':'i_phase_Xx_Zz/1'}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {'qubits','paulis','encoding'} or value['encoding'] != 'i_phase_Xx_Zz/1':
            raise ValueError("exact stabilizer encoding required")
        result = cls(value['qubits'], tuple(tuple(r) for r in value['paulis']))
        if type(result.n) is not int or not 1 <= result.n <= 4096:
            raise ValueError("stabilizer register quota")
        result.verify(); return result


def prepare(profile, algorithm, layout='full_register'):
    if not isinstance(profile, FeatureProfile) or algorithm not in ('exact_stabilizer_ghz','exact_stabilizer_cluster'):
        raise ValueError("explicit exact stabilizer profile/algorithm required")
    n, edges, offsets = profile.register_layout(layout)
    started = time.perf_counter(); state = StabilizerState.zero(n)
    if algorithm == 'exact_stabilizer_ghz':
        state = state.gate('H',0)
        for i in range(1,n): state = state.gate('CX',0,i)
        count = n
    else:
        for i in range(n): state = state.gate('H',i)
        for a,b in edges: state = state.gate('CZ',a,b)
        count = n + len(edges)
    state.verify()
    request = {'profile':profile.to_dict(),'algorithm':algorithm,'layout':layout}
    receipt = {'schema':'chronos.exact_stabilizer/1','request':request,
               'requested_algorithm':algorithm,'planned_algorithm':algorithm,'executed_algorithm':algorithm,
               'implementation_module':__name__,'implementation_digest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'plan_digest':digest(request),'geometry_digest':digest([n,[list(e) for e in edges],list(offsets)]),
               'execution_mode':'exact_clifford_algebra','substrate':{'kind':'cpu','arithmetic':'integer_gf2'},
               'state':state.to_dict(),'iterations_work_performed':{'gate_applications':count,'generator_rows':n},
               'elapsed_seconds':time.perf_counter()-started,'physical_quantum_execution':False,
               'sha256d_evaluations':0,'fallback_used':False,'fallback_reason':None}
    receipt['receipt_digest']=digest(receipt); verify_receipt(receipt,profile,algorithm,layout)
    return receipt


def verify_receipt(receipt, profile, algorithm, layout='full_register'):
    """Independent GHZ/graph-state generator construction (not gate replay)."""
    n, edges, offsets = profile.register_layout(layout)
    if algorithm == 'exact_stabilizer_ghz':
        expected_rows = (( (1 << n)-1,0,0),) + tuple((0,1 | 1 << i,0) for i in range(1,n))
        count=n
    elif algorithm == 'exact_stabilizer_cluster':
        neighbors=[0]*n
        for a,b in edges: neighbors[a] |= 1 << b; neighbors[b] |= 1 << a
        expected_rows = tuple((1<<i,neighbors[i],0) for i in range(n));count=n+len(edges)
    else: raise ValueError("unsupported exact stabilizer algorithm")
    request={'profile':profile.to_dict(),'algorithm':algorithm,'layout':layout}
    expected={'schema':'chronos.exact_stabilizer/1','request':request,
              'requested_algorithm':algorithm,'planned_algorithm':algorithm,'executed_algorithm':algorithm,
              'implementation_module':__name__,'implementation_digest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'plan_digest':digest(request),'geometry_digest':digest([n,[list(e) for e in edges],list(offsets)]),
              'execution_mode':'exact_clifford_algebra','substrate':{'kind':'cpu','arithmetic':'integer_gf2'},
              'state':StabilizerState(n,expected_rows).to_dict(),
              'iterations_work_performed':{'gate_applications':count,'generator_rows':n},
              'physical_quantum_execution':False,'sha256d_evaluations':0,'fallback_used':False,'fallback_reason':None}
    if not isinstance(receipt,dict) or set(receipt) != set(expected)|{'elapsed_seconds','receipt_digest'}:
        raise ValueError("stabilizer receipt fields mismatch")
    body=dict(receipt);seal=body.pop('receipt_digest')
    if digest(body)!=seal or any(receipt[k]!=v for k,v in expected.items()):
        raise ValueError("stabilizer identity/independent generator mismatch")
    if type(receipt['elapsed_seconds']) not in(int,float) or receipt['elapsed_seconds']<0:
        raise ValueError("invalid executed duration")
    StabilizerState.from_dict(receipt['state'])
    return True
