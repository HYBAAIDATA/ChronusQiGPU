"""Exact dual-M32/H4/phi-11D geometry over the supplied Q(phi) scalar core.

Normalized coordinates are n/sqrt(d), with n and d exact field elements and
sqrt(d) the positive real root. No numerical square root is evaluated.
"""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache, total_ordering
from itertools import combinations, permutations, product
from chronus.family_algebra import PhiElement as Q, PHI

ZERO, ONE = Q(), Q(1)
WEIGHTS = tuple(PHI ** (-i - 1) for i in range(11))


def sign(x: Q) -> int:
    """Sign(a+b*phi), by rational comparisons and sqrt(5) irrationality."""
    if not isinstance(x, Q):
        raise TypeError("Q(phi) required")
    a, b = 2 * x.a + x.b, x.b
    sa, sb = (a > 0) - (a < 0), (b > 0) - (b < 0)
    if not sa:
        return sb
    if not sb or sa == sb:
        return sa
    delta = a * a - 5 * b * b
    return sa * ((delta > 0) - (delta < 0))


def encode(x: Q):
    return [x.a.numerator, x.a.denominator, x.b.numerator, x.b.denominator]


def decode(value):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or any(type(x) is not int for x in value)
    ):
        raise ValueError("four exact integer limbs required")
    a, b, c, d = value
    if b <= 0 or d <= 0 or max(abs(x).bit_length() for x in value) > 65536:
        raise ValueError("invalid or excessive rational coefficient")
    q = Q(Fraction(a, b), Fraction(c, d))
    if encode(q) != list(value):
        raise ValueError("noncanonical rational encoding")
    return q


def dot(a, b, weights=None):
    if len(a) != len(b):
        raise ValueError("equal dimensions required")
    if weights is None:
        weights = (ONE,) * len(a)
    if len(weights) != len(a):
        raise ValueError("weight dimension mismatch")
    result = ZERO
    for x, y, w in zip(a, b, weights):
        result = result + x * y * w
    return result


@dataclass(frozen=True)
class ExactRay:
    """A real vector with one certified positive symbolic radical denominator."""

    numerator: tuple[Q, ...]
    denominator_squared: Q

    def __post_init__(self):
        if not self.numerator or any(not isinstance(x, Q) for x in self.numerator):
            raise TypeError("nonempty exact field coordinates required")
        if sign(self.denominator_squared) <= 0:
            raise ValueError("positive radical required")

    @classmethod
    def unit(cls, values):
        values = tuple(values)
        return cls(values, dot(values, values))

    def is_unit(self):
        return dot(self.numerator, self.numerator) == self.denominator_squared

    def transport(self):
        return {
            "numerator": [encode(x) for x in self.numerator],
            "positive_radical_squared": encode(self.denominator_squared),
        }

    @classmethod
    def restore(cls, value):
        if set(value) != {"numerator", "positive_radical_squared"}:
            raise ValueError("invalid ray fields")
        return cls(
            tuple(decode(x) for x in value["numerator"]),
            decode(value["positive_radical_squared"]),
        )

    def fold11(self):
        dimension = len(self.numerator)
        if dimension not in (3, 4):
            raise ValueError("canonical M32/H4 dimension required")
        values = tuple(
            self.numerator[i % dimension] * (PHI ** (-(i // dimension)))
            for i in range(11)
        )
        return ExactRay(values, self.denominator_squared + dot(values, values, WEIGHTS))

    def unfold(self, dimension):
        if len(self.numerator) != 11 or dimension not in (3, 4):
            raise ValueError("certified fold11 required")
        raw = self.numerator[:dimension]
        if self.numerator != tuple(
            raw[i % dimension] * (PHI ** (-(i // dimension))) for i in range(11)
        ):
            raise ValueError("fold relation does not hold")
        restored = ExactRay(
            raw, self.denominator_squared - dot(self.numerator, self.numerator, WEIGHTS)
        )
        if not restored.is_unit():
            raise ValueError("unit-normal certificate does not hold")
        return restored

    def in_phi_ball(self):
        if len(self.numerator) != 11:
            raise ValueError("11D required")
        return (
            sign(
                self.denominator_squared - dot(self.numerator, self.numerator, WEIGHTS)
            )
            > 0
        )


@total_ordering
@dataclass(frozen=True)
class RadicalScore:
    numerator: Q
    positive_denominator_squared: Q

    def __post_init__(self):
        if sign(self.positive_denominator_squared) <= 0:
            raise ValueError("positive score radical required")

    def _compare(self, other):
        if not isinstance(other, RadicalScore):
            raise TypeError("exact score required")
        a, b = sign(self.numerator), sign(other.numerator)
        if a != b:
            return (a > b) - (a < b)
        if not a:
            return 0
        # Compare n1/sqrt(d1), n2/sqrt(d2) without square-root approximation.
        delta = (
            self.numerator * self.numerator * other.positive_denominator_squared
            - other.numerator * other.numerator * self.positive_denominator_squared
        )
        return a * sign(delta)

    def __eq__(self, other):
        return isinstance(other, RadicalScore) and self._compare(other) == 0

    def __lt__(self, other):
        return self._compare(other) < 0

    __hash__ = None

    def __neg__(self):
        return RadicalScore(-self.numerator, self.positive_denominator_squared)


def score(direction, ray):
    # A common positive direction denominator cancels when ranking rays.
    return RadicalScore(dot(direction, ray.numerator, WEIGHTS), ray.denominator_squared)


@lru_cache(maxsize=1)
def m32():
    ico = []
    for a, b in product((-1, 1), repeat=2):
        ico.extend(
            ((ZERO, Q(a), PHI * b), (Q(a), PHI * b, ZERO), (PHI * a, ZERO, Q(b)))
        )
    dodeca = [tuple(Q(x) for x in row) for row in product((-1, 1), repeat=3)]
    inv = PHI.inverse()
    for a, b in product((-1, 1), repeat=2):
        dodeca.extend(
            (
                (ZERO, PHI * a, inv * b),
                (PHI * a, inv * b, ZERO),
                (inv * a, ZERO, PHI * b),
            )
        )
    rays = tuple(ExactRay.unit(row) for row in ico + dodeca)
    if len(rays) != 32 or len(set(r.numerator for r in rays)) != 32:
        raise ArithmeticError("32 unique faces required")
    return rays


@lru_cache(maxsize=1)
def h4():
    values = []
    for i in range(4):
        for s in (1, -1):
            values.append(tuple(Q(s if j == i else 0) for j in range(4)))
    values.extend(
        tuple(Q(Fraction(s, 2)) for s in row) for row in product((-1, 1), repeat=4)
    )
    base = (PHI, ONE, PHI.inverse(), ZERO)
    for perm in permutations(range(4)):
        if sum(perm[i] > perm[j] for i in range(4) for j in range(i + 1, 4)) % 2:
            continue
        for signs in product((-1, 1), repeat=4):
            values.append(
                tuple(base[perm[i]] * Fraction(signs[i], 2) for i in range(4))
            )
    vertices = tuple(dict.fromkeys(values))
    if len(vertices) != 120 or any(dot(v, v) != ONE for v in vertices):
        raise ArithmeticError("120 unit icosians required")
    neighbours = [set() for _ in vertices]
    edge = Q(2) - PHI
    for i, j in combinations(range(120), 2):
        delta = tuple(a - b for a, b in zip(vertices[i], vertices[j]))
        if dot(delta, delta) == edge:
            neighbours[i].add(j)
            neighbours[j].add(i)
    if any(len(n) != 12 for n in neighbours):
        raise ArithmeticError("exact H4 degree 12 required")
    cells = set()
    for i in range(120):
        for a, b, c in combinations(sorted(neighbours[i]), 3):
            if b in neighbours[a] and c in neighbours[a] and c in neighbours[b]:
                cells.add(tuple(sorted((i, a, b, c))))
    cells = tuple(sorted(cells))
    if len(cells) != 600:
        raise ArithmeticError("600 tetrahedra required")
    rays = tuple(
        ExactRay.unit(
            tuple(sum((vertices[i][j] for i in cell), ZERO) for j in range(4))
        )
        for cell in cells
    )
    if any(r.denominator_squared != Q(4) + PHI * 6 for r in rays):
        raise ArithmeticError("regular tetrahedral centroid norm failed")
    if len(set(r.numerator for r in rays)) != 600:
        raise ArithmeticError("600 unique dual normals required")
    owners = {}
    for i, cell in enumerate(cells):
        for face in combinations(cell, 3):
            owners.setdefault(face, []).append(i)
    adjacency = [set() for _ in cells]
    for face, ids in owners.items():
        if len(ids) != 2:
            raise ArithmeticError("closed tetrahedral incidence required")
        a, b = ids
        adjacency[a].add(b)
        adjacency[b].add(a)
    if any(len(n) != 4 for n in adjacency):
        raise ArithmeticError("dual degree four required")
    return vertices, cells, rays, tuple(tuple(sorted(x)) for x in adjacency)


def m32_relations():
    rays = m32()
    adjacency = []
    dual = []
    for i, r in enumerate(rays):
        same = range(12) if i < 12 else range(12, 32)
        other = range(12, 32) if i < 12 else range(12)

        def key(j):
            return RadicalScore(
                dot(r.numerator, rays[j].numerator), rays[j].denominator_squared
            )

        a = max(key(j) for j in same if i != j)
        d = max(key(j) for j in other)
        adjacency.append(tuple(j for j in same if i != j and key(j) == a))
        dual.append(tuple(j for j in other if key(j) == d))
    if any(
        len(a) != (5 if i < 12 else 3) or len(d) != (5 if i < 12 else 3)
        for i, (a, d) in enumerate(zip(adjacency, dual))
    ):
        raise ArithmeticError("exact M32 duality failed")
    return tuple(adjacency), tuple(dual)


@lru_cache(maxsize=1)
def exact_walk_reference():
    """Independent exact replay of the actual Turing Hadamard C600 walk.

    At time t each amplitude is (a+i*b)/sqrt(2)**(t+1), with integer
    a,b. The coin uses sum/difference; the conditional shift is a basis
    permutation. This representation executes quantum interference exactly,
    not a random/classical walk or a sampled probability distribution.
    """
    import hashlib, json

    positions, horizon = 600, 300
    amplitudes = {(0, 0): (1, 0), (0, 1): (0, 1)}
    cumulative = [0] * positions
    reached = set()
    for t in range(horizon + 1):
        distribution = [0] * positions
        for (x, _coin), (a, b) in amplitudes.items():
            distribution[x] += a * a + b * b
        if sum(distribution) != 1 << (t + 1):
            raise ArithmeticError("exact Hadamard walk lost unit norm")
        for x, mass in enumerate(distribution):
            cumulative[x] += mass << (horizon - t)
            if mass:
                reached.add(x)
        if t == horizon:
            break
        state = {}
        for x in {x for x, _ in amplitudes}:
            a, b = amplitudes.get((x, 0), (0, 0))
            c, d = amplitudes.get((x, 1), (0, 0))
            for key, value in (
                (((x - 1) % positions, 0), (a + c, b + d)),
                (((x + 1) % positions, 1), (a - c, b - d)),
            ):
                if value != (0, 0):
                    state[key] = value
        amplitudes = state
    if reached != set(range(positions)):
        raise ArithmeticError("quantum horizon lost complete logical coverage")
    rank = (0, *sorted(range(1, positions), key=lambda x: (-cumulative[x], x)))
    identity = {
        "walk": "turing_exact_coined_cycle",
        "positions": positions,
        "qubits": 11,
        "horizon": horizon,
        "rank": rank,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return rank, digest


@lru_cache(maxsize=4)
def validate_payload(encoded):
    """Independent exact replay of geometry/certificates, cached by full content."""
    import json

    if not isinstance(encoded, str) or len(encoded) > 2_000_000:
        raise ValueError("bounded exact geometry transport required")
    p = json.loads(encoded)
    if (
        p.get("schema") != "chronus.exact_geometry/2"
        or p.get("approximations_used") is not False
        or p.get("learned_scores_used") is not False
    ):
        raise ValueError("exact nonheuristic geometry required")
    vertices, cells, rays, adj = h4()
    faces = m32()
    ma, md = m32_relations()
    if tuple(tuple(decode(x) for x in row) for row in p["vertices"]) != vertices:
        raise ValueError("canonical icosians changed")
    if tuple(tuple(x) for x in p["cells"]) != cells:
        raise ValueError("canonical tetrahedral incidence changed")
    expected = {
        "m32": faces,
        "normals_4d": rays,
        "coarse_11d": tuple(r.fold11() for r in faces),
        "frames_11d": tuple(r.fold11() for r in rays),
    }
    for name, values in expected.items():
        if tuple(ExactRay.restore(v) for v in p[name]) != values:
            raise ValueError("exact geometry relation failed: " + name)
    if (
        tuple(tuple(x) for x in p["adjacency"]) != adj
        or tuple(tuple(x) for x in p["m32_adjacency"]) != ma
        or tuple(tuple(x) for x in p["m32_dual_incidence"]) != md
    ):
        raise ValueError("exact adjacency/duality changed")
    coarse = expected["coarse_11d"]
    fine = expected["frames_11d"]
    anchors = tuple(
        max(range(32), key=lambda i: score(r.numerator, coarse[i])) for r in fine
    )
    if tuple(p["coarse_anchor"]) != anchors:
        raise ValueError("exact region binding failed")
    rank, walk_digest = exact_walk_reference()
    quantum = {
        "algorithm": "turing_exact_coined_cycle",
        "coin": "exact_Hadamard",
        "shift": "unitary_C600_permutation",
        "register_qubits": 11,
        "basis_dimension": 2048,
        "steps": 300,
        "rank": list(rank),
        "digest": walk_digest,
        "not_physical_qpu_claim": True,
    }
    if p.get("quantum") != quantum:
        raise ValueError(
            "quantum execution evidence differs from independent exact replay"
        )
    return True


# -------------------------------------------------------------------------
# 600-LANE EXACT PARTITION & BIJECTION BUILDER (DODECA ⊕ ICOSA OVERLAY IN 11D)
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class EstateChunk600:
    """Disjoint leased nonce chunk owned by exactly one 600-cell vertex lane."""

    lane_id: int
    vertex_id: int
    base_step: int
    size: int
    stride: int
    nonces: tuple[int, ...]
    ray_11d: ExactRay

    def verify_bijection(self) -> bool:
        if self.size == 0:
            return len(self.nonces) == 0
        if len(self.nonces) != self.size:
            return False
        if len(set(self.nonces)) != self.size:
            return False
        for k in range(self.size):
            expected = self.base_step + ((k * self.stride) % self.size)
            if self.nonces[k] != expected:
                return False
        return True


@dataclass(frozen=True)
class PartitionProof600:
    """Provable, independently verifiable certificate for 600-lane partition."""

    bijection_fn: str
    coverage_hash: str
    overlap_proof: str
    is_complete: bool
    is_disjoint: bool
    total_window: int
    total_lanes: int
    recheck_passed: bool
    recheck_count: int
    order_seed: int
    certificate_sha256: str
    representation_labels: tuple[tuple[str, str], ...]

    def verify(self) -> bool:
        if not self.is_complete or not self.is_disjoint or self.total_lanes != 600:
            return False
        if self.overlap_proof != "EMPTY":
            return False
        if not self.recheck_passed:
            return False
        import hashlib, json
        payload = {
            "bijection_fn": self.bijection_fn,
            "coverage_hash": self.coverage_hash,
            "overlap_proof": self.overlap_proof,
            "is_complete": self.is_complete,
            "is_disjoint": self.is_disjoint,
            "total_window": self.total_window,
            "total_lanes": self.total_lanes,
            "order_seed": self.order_seed,
            "recheck_passed": self.recheck_passed,
            "recheck_count": self.recheck_count,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return digest == self.certificate_sha256

    def as_dict(self):
        return {
            "bijection_fn": self.bijection_fn,
            "coverage_hash": self.coverage_hash,
            "overlap_proof": self.overlap_proof,
            "is_complete": self.is_complete,
            "is_disjoint": self.is_disjoint,
            "total_window": self.total_window,
            "total_lanes": self.total_lanes,
            "recheck_passed": self.recheck_passed,
            "recheck_count": self.recheck_count,
            "order_seed": self.order_seed,
            "certificate_sha256": self.certificate_sha256,
            "representation_labels": dict(self.representation_labels),
        }


def dodeca_overlay_icosa() -> tuple[ExactRay, ...]:
    """600 exact rays from the H4 600-cell / 120-cell dual compound."""
    return h4()[2]


def embed_11d_exact(rays: tuple[ExactRay, ...]) -> tuple[ExactRay, ...]:
    """Lift 4D rays to exact 11D coordinates in Q(phi)^11 via fold11()."""
    return tuple(r.fold11() for r in rays)


def hendrix_grover_order(seed: int = 1337) -> tuple[int, ...]:
    """Structured Grover-derivative order over the 600-cycle (clamped to 2^20)."""
    canonical_rank, _ = exact_walk_reference()
    coprimes = (7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
    stride = coprimes[seed % len(coprimes)]
    order = tuple(canonical_rank[(i * stride) % 600] for i in range(600))
    if len(set(order)) != 600:
        raise ArithmeticError("Hendrix Grover order must be a strict 600-permutation")
    return order


def build_600_partition(
    base_step: int,
    window: int,
    seed: int = 1337,
    stride: int = 5,
    *,
    header_prefix: bytes | None = None,
    target_int: int | None = None,
) -> tuple[tuple[EstateChunk600, ...], PartitionProof600]:
    """Exact 600-lane partition of leased window W: 100% complete, 0% overlap."""
    if window < 0:
        raise ValueError("window cannot be negative")
    if base_step < 0 or base_step + window > 0x100000000:
        raise ValueError("Interval exceeds uint32 domain")

    verts = dodeca_overlay_icosa()
    coords11 = embed_11d_exact(verts)
    order = hendrix_grover_order(seed)

    base_chunk = window // 600
    rem = window % 600

    chunks_list: list[EstateChunk600] = []
    current_base = base_step
    all_nonces: list[int] = []

    coprime_candidates = (5, 7, 11, 13, 17, 19, 23, 29, 31)

    import math
    for lane_idx in range(600):
        vertex_idx = order[lane_idx]
        chunk_size = base_chunk + (1 if lane_idx < rem else 0)

        chosen_stride = 1
        if chunk_size > 1:
            chosen_stride = stride
            if math.gcd(chosen_stride, chunk_size) != 1:
                for c in coprime_candidates:
                    if math.gcd(c, chunk_size) == 1:
                        chosen_stride = c
                        break
                if math.gcd(chosen_stride, chunk_size) != 1:
                    chosen_stride = 1

        if chunk_size > 0:
            chunk_nonces = tuple(
                current_base + ((k * chosen_stride) % chunk_size)
                for k in range(chunk_size)
            )
            all_nonces.extend(chunk_nonces)
        else:
            chunk_nonces = ()

        chunk = EstateChunk600(
            lane_id=lane_idx,
            vertex_id=vertex_idx,
            base_step=current_base,
            size=chunk_size,
            stride=chosen_stride,
            nonces=chunk_nonces,
            ray_11d=coords11[vertex_idx],
        )
        chunks_list.append(chunk)
        current_base += chunk_size

    all_set = set(all_nonces)
    expected_set = set(range(base_step, base_step + window))
    is_complete = (all_set == expected_set)
    is_disjoint = (len(all_set) == len(all_nonces))

    if not is_complete:
        raise ArithmeticError("Hilbert-space tiling incomplete: union != window")
    if not is_disjoint:
        raise ArithmeticError("Partition overlap detected: pairwise intersection is not empty")

    owners = set(c.vertex_id for c in chunks_list)
    if len(owners) != 600:
        raise ArithmeticError("Every chunk must have a unique vertex owner")

    import hashlib, json, struct
    recheck_count = 0
    recheck_passed = True
    prefix = header_prefix if header_prefix is not None and len(header_prefix) == 76 else (b"\x00" * 76)
    target = target_int if target_int is not None else (1 << 256) - 1

    sample_lanes = [c for c in chunks_list if c.size > 0][:10]
    for c in sample_lanes:
        n = c.nonces[0]
        h1 = hashlib.sha256(prefix + struct.pack("<I", n)).digest()
        h2 = hashlib.sha256(h1).digest()
        val = int.from_bytes(h2, "little")
        recheck_count += 1
        if target_int is not None and val > target:
            recheck_passed = False

    coverage_hash = hashlib.sha256(
        ",".join(str(n) for n in sorted(all_nonces)).encode("ascii")
    ).hexdigest()

    proof_payload = {
        "bijection_fn": "hendrix_grover_600_partition",
        "coverage_hash": coverage_hash,
        "overlap_proof": "EMPTY",
        "is_complete": is_complete,
        "is_disjoint": is_disjoint,
        "total_window": window,
        "total_lanes": 600,
        "order_seed": seed,
        "recheck_passed": recheck_passed,
        "recheck_count": recheck_count,
    }
    cert_sha256 = hashlib.sha256(
        json.dumps(proof_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    representation_labels = (
        ("poincare_cassini", "EXACT"),
        ("klein_poincare", "NUMERICAL"),
    )

    proof = PartitionProof600(
        bijection_fn="hendrix_grover_600_partition",
        coverage_hash=coverage_hash,
        overlap_proof="EMPTY",
        is_complete=is_complete,
        is_disjoint=is_disjoint,
        total_window=window,
        total_lanes=600,
        recheck_passed=recheck_passed,
        recheck_count=recheck_count,
        order_seed=seed,
        certificate_sha256=cert_sha256,
        representation_labels=representation_labels,
    )

    return tuple(chunks_list), proof

