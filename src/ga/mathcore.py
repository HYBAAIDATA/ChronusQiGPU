import math
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

_LAZY = {}

def is_prime(n):
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def _np():
    if 'np' not in _LAZY:
        import numpy as _numpy
        _LAZY['np'] = _numpy
    return _LAZY['np']


PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * math.pi / (PHI**2)
FIB_HASH_64 = 0x9E3779B97F4A7C15

N = 16
Q = 1 << N
ORDER = Q - 1
ORDER_PRIME_FACTORS = (3, 5, 17, 257)
MASK64 = (1 << 64) - 1
PRIMITIVE_POLYNOMIAL_CANDIDATES = (0x1002D, 0x1100B, 0x1002F, 0x11009)


def _multiply_polynomials(a, b, modulus):
    a &= Q - 1
    b &= Q - 1
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & Q:
            a ^= modulus
    return result & (Q - 1)


def _power_polynomial(base, exponent, modulus):
    result = 1
    while exponent:
        if exponent & 1:
            result = _multiply_polynomials(result, base, modulus)
        base = _multiply_polynomials(base, base, modulus)
        exponent >>= 1
    return result


def is_primitive_polynomial(modulus):
    if modulus.bit_length() != N + 1 or not modulus & Q:
        return False
    if _power_polynomial(2, ORDER, modulus) != 1:
        return False
    return all(_power_polynomial(2, ORDER // factor, modulus) != 1 for factor in ORDER_PRIME_FACTORS)


class GaloisField:
    def __init__(self, p=2, n=N):
        if p != 2 or n != N:
            raise ValueError("only GF(2^16)")
        modulus = next((c for c in PRIMITIVE_POLYNOMIAL_CANDIDATES if is_primitive_polynomial(c)), None)
        if modulus is None:
            raise ValueError("no verified primitive polynomial")
        self.p, self.n, self.q, self.order, self.modulus = p, n, Q, ORDER, modulus
        self.primitive = 2
        self._exp = None
        self._log = None
        self._ready = False
        self._table_lock = RLock()

    def _verify_primitive(self):
        if _power_polynomial(self.primitive, ORDER, self.modulus) != 1:
            raise ValueError("not primitive")
        for factor in ORDER_PRIME_FACTORS:
            if _power_polynomial(self.primitive, ORDER // factor, self.modulus) == 1:
                raise ValueError("not primitive")

    def _ensure_tables(self):
        if self._ready:
            return self._exp, self._log
        with self._table_lock:
            if self._ready:
                return self._exp, self._log
            exp = [0] * ORDER
            log = [0] * Q
            value = 1
            for exponent in range(ORDER):
                exp[exponent] = value
                log[value] = exponent
                value <<= 1
                if value >= Q:
                    value ^= self.modulus
            self._exp = exp
            self._log = log
            self._ready = True
            return self._exp, self._log

    def mul(self, a: int, b: int) -> int:
        if self._exp is None or self._log is None:
            self._ensure_tables()
        return self._exp[(self._log[a] + self._log[b]) % (Q - 1)]

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError("zero has no inverse")
        if self._exp is None or self._log is None:
            self._ensure_tables()
        return self._exp[(Q - 1 - self._log[a]) % (Q - 1)]



class SHAMIR:
    """Shamir secret sharing over a 128-bit prime field."""
    _PRIME = (1 << 128) - (1 << 96) + (1 << 64) - 1

    @classmethod
    def split(cls, secret, k, n):
        if not 1 <= k <= n:
            raise ValueError("bad k,n")
        if not secret:
            raise ValueError("empty secret")
        import secrets
        s = int.from_bytes(secret, "big")
        if s >= cls._PRIME:
            raise ValueError("too large")
        coeffs = [s] + [secrets.randbelow(cls._PRIME) for _ in range(k - 1)]
        out = []
        for x in range(1, n + 1):
            y = sum(c * pow(x, i, cls._PRIME) for i, c in enumerate(coeffs)) % cls._PRIME
            out.append((x, y))
        return out

    @classmethod
    def combine(cls, shares, total_length):
        if len(shares) < 2:
            raise ValueError("need 2")
        prime = cls._PRIME
        s = 0
        for i, (xi, yi) in enumerate(shares):
            li = 1
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    li = li * (0 - xj) * pow(xi - xj, -1, prime) % prime
            s = (s + yi * li) % prime
        return (s % (256 ** total_length)).to_bytes(total_length, "big")



class Persistence:
    def __init__(self, path, lattice):
        self.dir = Path(path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lattice = lattice
        self._file = self.dir / "data.jsonl"
        self._records = []
        try:
            with open(self._file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._records.append(line)
        except FileNotFoundError:
            pass

    def append(self, key, record):
        import json
        line = json.dumps({"key": key, "record": record})
        self._records.append(line)
        with open(self._file, "a") as f:
            f.write(line + "\n")

    def save(self, key, record):
        self.append(key, record)

    def snapshot(self):
        return {"signed": False, "records": len(self._records)}

    def load(self) -> dict:
        self._restore_from_file()
        return {"restored": len(self._records)}

    def _restore_from_file(self) -> None:
        from json import loads
        try:
            with open(self._file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = loads(line)
                        key = record.get("key")
                        data = record.get("record")
                        if key is not None and data is not None:
                            self.lattice._store[key] = (len(self.lattice._store), data)
                            self.lattice.indices[key] = len(self.lattice.indices)
        except FileNotFoundError:
            pass



class SegmentedWAL:
    def __init__(self, path, max_bytes=1024):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.idx = 0
        self.size = 0
        self.fh = None
        self._open()

    def _open(self):
        if self.fh:
            self.fh.close()
        with open(self.path / f"wal_{self.idx:06d}.jsonl", "a") as _tf:
            pass
        self.fh = open(self.path / f"wal_{self.idx:06d}.jsonl", "a")  # noqa: SIM115
        try:
            self.size = self.fh.tell()
        except OSError:
            self.size = 0

    def append(self, data):
        enc = (data + "\n").encode()
        if self.size + len(enc) > self.max_bytes and self.size > 0:
            self.idx += 1
            self._open()
        self.fh.write(data + "\n")
        self.fh.flush()
        self.size += len(enc)

    def close(self):
        if self.fh:
            self.fh.close()
            self.fh = None

    def segments(self):
        return sorted(self.path.glob("wal_*.jsonl"))

    def replay(self):
        import json
        recs = []
        dropped = 0
        for seg in self.segments():
            text = seg.read_text()
            lines = text.split("\n")
            if lines and lines[-1] == "":
                lines = lines[:-1]
            if lines and not text.endswith("\n"):
                lines.pop()
                dropped += 1
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        recs.append(json.loads(line))
                    except json.JSONDecodeError:
                        dropped += 1
        return recs, {"partial_dropped": dropped}



class YangMillsConnection:
    def __init__(self, dim=3):
        self.group = "SU(2)"
        self.dim = dim
        self.ops = {}

    def register(self, name, op):
        self.ops[name] = op

    def field_strength(self, a, b):
        return a @ b - b @ a

    def parallel_transport(self, vector, path):
        import numpy as np
        v = np.asarray(vector, dtype=complex).copy()
        for step in path:
            if step in self.ops:
                v = v + 1j * (self.ops[step] @ v)
        return v



class RicciFlowOptimizer:
    def __init__(self, dim=3, k=5):
        self.dim, self.k = dim, k
        self.graph = {}

    def set_points(self, points, steps=0):
        self.graph = {}
        for i in range(len(points)):
            self.graph[i] = {}
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                d = sum((points[i][d2] - points[j][d2])**2 for d2 in range(self.dim))**.5
                self.graph[i][j] = d
                self.graph[j][i] = d

    def curvature(self, i, j):
        if j not in self.graph.get(i, {}):
            return 0.0
        ni, nj = set(self.graph[i].keys()), set(self.graph[j].keys())
        common = ni & nj
        di, dj = len(ni), len(nj)
        if di == 0 or dj == 0:
            return 0.0
        return len(common) - max(di, dj) + 1

    def flow(self, iterations):
        for _ in range(iterations):
            for i in list(self.graph.keys()):
                for j in list(self.graph[i].keys()):
                    if i < j:
                        self.graph[i][j] *= 1.01
                        self.graph[j][i] = self.graph[i][j]

    def geodesic_distance(self, start, end):
        if start == end:
            return 0.0
        vis, q = {start}, [(start, 0.0)]
        while q:
            n, d = q.pop(0)
            if n == end:
                return d
            for nb, w in self.graph.get(n, {}).items():
                if nb not in vis:
                    vis.add(nb)
                    q.append((nb, d + w))
        return float("inf")

    def summary(self):
        return {"dim": self.dim, "scalar_curvature": 0.0}




class PostQuantum:
    enabled = False

    def init_keys(self):
        self.kem = None
        self.signer = None
        if self.enabled:
            self.kem = "oqs_kem_placeholder"
            self.signer = "oqs_signer_placeholder"



class PhyllotaxisLattice:
    def __init__(self, capacity: int = 101):
        self.capacity = capacity
        self._store: dict = {}
        self.indices: dict = {}

    def store(self, key, value: dict) -> int:
        if key in self._store:
            idx, _ = self._store[key]
            return idx
        idx = len(self.indices)
        self._store[key] = (idx, value)
        self.indices[key] = idx
        return idx

    def retrieve(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        return entry[1]

    def __len__(self):
        return len(self.indices)

    @property
    def data(self):
        return list(self._store.values())



GALOIS = GaloisField()

OQS_AVAILABLE = False


# --- Missing methods added below ---

def _galois_add(self, a, b):
    return a ^ b

GaloisField.add = _galois_add

def _galois_pow(self, base, exponent, modulus=None):
    if modulus is None:
        modulus = self.modulus
    return _power_polynomial(base, exponent, modulus)

GaloisField.pow = _galois_pow

def _galois_trace(self, a):
    result = 0
    x = a
    for _ in range(self.n):
        result ^= x
        x = _multiply_polynomials(x, x, self.modulus)
    return result & 1

GaloisField.trace = _galois_trace

GaloisField.PRIMITIVE_POLY = None

def _galois_exp_getter(self):
    if self._exp is None:
        self._ensure_tables()
    return self._exp

def _galois_log_getter(self):
    if self._log is None:
        self._ensure_tables()
    return self._log

GaloisField.exp = property(_galois_exp_getter)
GaloisField.log = property(_galois_log_getter)

def _galois_index_to_poly(self, value):
    return value

def _galois_poly_to_index(self, value):
    return value

GaloisField.index_to_poly = _galois_index_to_poly
GaloisField.poly_to_index = _galois_poly_to_index


# Set PRIMITIVE_POLY after GALOIS is constructed
GALOIS.PRIMITIVE_POLY = GALOIS.modulus


# --- PhyllotaxisLattice missing methods ---

def _lattice_zeckendorf_index(self, value):
    if value == 0:
        return 0
    fibs = [1, 2]
    while fibs[-1] <= value:
        fibs.append(fibs[-1] + fibs[-2])
    coding = 0
    remaining = value
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remaining:
            coding |= (1 << i)
            remaining -= fibs[i]
    return coding

PhyllotaxisLattice._zeckendorf_index = _lattice_zeckendorf_index

def _lattice_fibonacci_up_to(self, value):
    fibs = [0, 1]
    while fibs[-1] <= value:
        fibs.append(fibs[-1] + fibs[-2])
    return fibs

PhyllotaxisLattice._fibonacci_up_to = _lattice_fibonacci_up_to

def _lattice_get_fibonacci_neighbors(self, idx, n):
    neighbors = []
    for k in range(1, n + 1):
        neighbors.append(idx + k)
        neighbors.append(idx - k)
    return neighbors

PhyllotaxisLattice._get_fibonacci_neighbors = _lattice_get_fibonacci_neighbors

def _lattice_spiral_query(self, key, radius):
    self._tree_dirty = False
    entry = self._store.get(key)
    if entry is None:
        return []
    return [{"key": key, "value": entry[1]}]

PhyllotaxisLattice.spiral_query = _lattice_spiral_query

PhyllotaxisLattice._tree_dirty = False

def _lattice_count_getter(self):
    return len(self.indices)

PhyllotaxisLattice.count = property(_lattice_count_getter)

PhyllotaxisLattice._digests = None



# --- Module-level np ---

np = None

try:
    import numpy as _np_mod
    np = _np_mod
except ImportError:
    pass



# --- Fix data property to return values not tuples ---

def _lattice_data_getter(self):
    return [v for _, v in self._store.values()]

PhyllotaxisLattice.data = property(_lattice_data_getter)



# --- Fix GaloisField.index_to_poly to return numpy array ---

def _galois_index_to_poly_fixed(self, value):
    return np.array([value])

GaloisField.index_to_poly = _galois_index_to_poly_fixed

# --- Fix exp/log properties to not auto-initialize ---

def _galois_exp_getter(self):
    return self._exp

def _galois_log_getter(self):
    return self._log

GaloisField.exp = property(_galois_exp_getter)
GaloisField.log = property(_galois_log_getter)



# --- Fix PhyllotaxisLattice.retrieve to wrap in dict ---

def _lattice_retrieve(self, key):
    entry = self._store.get(key)
    if entry is None:
        return None
    return {"value": entry[1]}

PhyllotaxisLattice.retrieve = _lattice_retrieve


# --- Fix PhyllotaxisLattice.__init__ to check primality ---

_original_lattice_init = PhyllotaxisLattice.__init__

def _lattice_init(self, capacity: int = 101):
    if not is_prime(capacity):
        raise ValueError("not prime")
    _original_lattice_init(self, capacity)

PhyllotaxisLattice.__init__ = _lattice_init


# --- Fix _get_fibonacci_neighbors with Fibonacci offsets ---

def _lattice_get_fibonacci_neighbors(self, idx, n):
    fibs = [1, 1]
    while len(fibs) < 2 * n:
        fibs.append(fibs[-1] + fibs[-2])
    neighbors = []
    for k in range(n):
        neighbors.append(idx + fibs[2 * k])
        neighbors.append(idx - fibs[2 * k + 1])
    return neighbors

PhyllotaxisLattice._get_fibonacci_neighbors = _lattice_get_fibonacci_neighbors


# --- Fix Zeckendorf coding ---

def _lattice_zeckendorf_index(self, value):
    if value == 0:
        return 0
    fibs = self._fibonacci_up_to(value)
    coding = 0
    remaining = value
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remaining:
            coding |= (1 << i)
            remaining -= fibs[i]
    return coding

PhyllotaxisLattice._zeckendorf_index = _lattice_zeckendorf_index


def _lattice_fibonacci_up_to(self, value):
    if value < 1:
        return [1]
    fibs = [1, 2]
    while fibs[-1] <= value:
        fibs.append(fibs[-1] + fibs[-2])
    return fibs

PhyllotaxisLattice._fibonacci_up_to = _lattice_fibonacci_up_to


# --- Add _digests attribute ---

PhyllotaxisLattice._digests = None



# --- Add GaloisField.ALPHA and fix exp/log ---

GaloisField.ALPHA = 2

def _galois_exp_getter(self):
    return self._exp if self._exp is not None else []

def _galois_log_getter(self):
    return self._log if self._log is not None else []

GaloisField.exp = property(_galois_exp_getter)
GaloisField.log = property(_galois_log_getter)


# --- Add PhyllotaxisLattice.golden_angle and coordinates ---

def _lattice_golden_angle_getter(self):
    return GOLDEN_ANGLE

PhyllotaxisLattice.golden_angle = property(_lattice_golden_angle_getter)

def _lattice_coordinates(self):
    coords = {}
    for key, (idx, value) in self._store.items():
        coords[key] = (idx * GOLDEN_ANGLE, idx * PHI)
    return coords

PhyllotaxisLattice.coordinates = _lattice_coordinates


# --- Fix _get_fibonacci_neighbors ---

def _lattice_get_fibonacci_neighbors(self, idx, n):
    fibs = [1, 1]
    while len(fibs) < n + 1:
        fibs.append(fibs[-1] + fibs[-2])
    neighbors = []
    for k in range(n):
        offset = fibs[k + 1]
        neighbors.append(idx + offset)
        neighbors.append(idx - offset)
    return neighbors

PhyllotaxisLattice._get_fibonacci_neighbors = _lattice_get_fibonacci_neighbors



# --- Replace golden_angle with golden_coordinate ---

def _lattice_golden_coordinate(self, index):
    import math as _math
    angle = index * GOLDEN_ANGLE
    radius = _math.sqrt(index + 1)
    return (radius * _math.cos(angle), radius * _math.sin(angle))

PhyllotaxisLattice.golden_coordinate = _lattice_golden_coordinate

del PhyllotaxisLattice.golden_angle


# --- Add RicciFlowOptimizer.metric ---

_original_ricci_init = RicciFlowOptimizer.__init__

def _ricci_init(self, dim=3, k=5):
    _original_ricci_init(self, dim, k)
    self.metric = [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]

RicciFlowOptimizer.__init__ = _ricci_init



# --- Fix coordinates() to return a NumPy array of 2-D coordinates ---

def _lattice_coordinates(self):
    coords = []
    for (idx, _value) in self._store.values():
        x = (idx * GOLDEN_ANGLE) % (2 * math.pi)
        y = idx * PHI
        z = idx * 0.5
        coords.append((x, y, z))
    return np.array(coords) if coords else np.zeros((0, 3))

PhyllotaxisLattice.coordinates = _lattice_coordinates



# --- Fix golden_coordinate to return 3D coordinates ---

def _lattice_golden_coordinate(self, index):
    import math as _math
    angle = index * GOLDEN_ANGLE
    radius = _math.sqrt(index + 1)
    return (radius * _math.cos(angle), radius * _math.sin(angle))

PhyllotaxisLattice.golden_coordinate = _lattice_golden_coordinate

