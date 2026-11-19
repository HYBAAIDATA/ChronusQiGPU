"""First-principles equalities, without numerical geometry or tolerance oracles."""

from fractions import Fraction
import ast
from pathlib import Path
import pytest

pytestmark = pytest.mark.real
from chronus.math.exact_geometry import (
    Q,
    PHI,
    ZERO,
    ONE,
    sign,
    encode,
    decode,
    dot,
    ExactRay,
    RadicalScore,
    m32,
    m32_relations,
    h4,
)


def test_phi_identity_and_exact_sign_at_near_cancellation():
    assert PHI * PHI == PHI + ONE
    assert PHI.norm() == -1
    for n in range(1, 101):
        # Conjugate^n is extremely small but its sign is still decided exactly.
        term = PHI.conjugate() ** n
        assert sign(term) == (-1) ** n
    assert sign(PHI - Q(Fraction(1618, 1000))) == 1
    assert sign(PHI - Q(Fraction(1619, 1000))) == -1
    assert sign(ZERO) == 0


def test_no_float_coercion_or_noncanonical_rationals():
    with pytest.raises(ValueError):
        Q(0.5)
    with pytest.raises(ValueError):
        decode([1, 2, 0, 2])
    with pytest.raises(ValueError):
        decode([1, 2, 0.0, 1])
    assert decode(encode((~PHI) ** 31)) == (~PHI) ** 31


def test_symbolic_radical_ordering_is_exact():
    assert RadicalScore(Q(1), Q(2)) == RadicalScore(Q(2), Q(8))
    assert RadicalScore(Q(-1), Q(2)) > RadicalScore(Q(-2), Q(2))
    assert RadicalScore(PHI, Q(1)) > RadicalScore(Q(1), Q(1))
    assert RadicalScore(ZERO, Q(1)) > RadicalScore(Q(-1), Q(1))


def test_exact_m32_incidence():
    rays = m32()
    adj, dual = m32_relations()
    assert len(rays) == 32 and all(r.is_unit() for r in rays)
    for i in range(32):
        assert len(adj[i]) == (5 if i < 12 else 3)
        assert len(dual[i]) == (5 if i < 12 else 3)
        assert all(i in adj[j] for j in adj[i])
        assert all(i in dual[j] for j in dual[i])


def test_twenty_directions_are_actual_icosahedral_triangle_centroids():
    from itertools import combinations

    ico = tuple(r.numerator for r in m32()[:12])
    centroids = []
    for triangle in combinations(range(12), 3):
        if all(
            dot(
                tuple(a - b for a, b in zip(ico[i], ico[j])),
                tuple(a - b for a, b in zip(ico[i], ico[j])),
            )
            == Q(4)
            for i, j in combinations(triangle, 2)
        ):
            centroids.append(
                tuple(sum((ico[i][j] for i in triangle), ZERO) for j in range(3))
            )
    assert len(centroids) == 20
    matched = set()
    for direction in m32()[12:]:
        matches = [
            i
            for i, c in enumerate(centroids)
            if sign(dot(c, direction.numerator)) == 1
            and dot(c, direction.numerator) ** 2
            == dot(c, c) * dot(direction.numerator, direction.numerator)
        ]
        assert len(matches) == 1
        matched.add(matches[0])
    assert len(matched) == 20


def test_exact_h4_coverage_and_incidence():
    vertices, cells, rays, adj = h4()
    assert len(vertices) == 120 and len(cells) == len(rays) == 600
    assert len(set(cells)) == 600
    assert all(dot(v, v) == ONE for v in vertices)
    assert all(r.is_unit() for r in rays)
    seen = set()
    todo = [0]
    while todo:
        x = todo.pop()
        if x not in seen:
            seen.add(x)
            todo.extend(adj[x])
    assert len(seen) == 600 and sum(map(len, adj)) == 2400


def test_fold_certificates_restore_every_exact_m32_and_h4_normal():
    rays = m32() + h4()[2]
    for r in rays:
        f = r.fold11()
        assert f.in_phi_ball()
        assert f.unfold(len(r.numerator)) == r
        assert ExactRay.restore(f.transport()) == f


def test_mathematical_geometry_has_no_numeric_escape_hatch():
    import chronus.math.exact_geometry as module

    tree = ast.parse(Path(module.__file__).read_text())
    assert not any(
        isinstance(n, ast.Constant) and isinstance(n.value, float)
        for n in ast.walk(tree)
    )
    forbidden = {
        "float",
        "sqrt",
        "evalf",
        "isclose",
        "allclose",
        "nearest_vertex",
        "approx",
        "random",
    }
    assert not any(
        isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id in forbidden)
            or (isinstance(n.func, ast.Attribute) and n.func.attr in forbidden)
        )
        for n in ast.walk(tree)
    )


def test_quantum_rank_matches_independent_exact_complex_integer_replay():
    from chronus.math.exact_geometry import exact_walk_reference
    from chronus.pythia.exact_search import _exact_hilbert_walk_rank

    assert exact_walk_reference() == _exact_hilbert_walk_rank()
    assert sorted(exact_walk_reference()[0]) == list(range(600))


def test_exact_pythia_directive_is_header_bound_without_learned_inputs():
    from chronus.pythia.exact_search import (
        exact_mining_directive,
        exact_vertex_itinerary,
    )

    header = bytes(80)
    directive = exact_mining_directive(
        header=header, target_be=bytes(32), base_step=100, window=1000
    )
    evidence = directive.as_evidence()
    assert evidence["authority"] == "PYTHIA"
    assert evidence["heuristics_used"] is evidence["approximations_used"] is False
    assert len(set(directive.lane_order)) == 32
    assert directive == exact_mining_directive(
        header=header, target_be=bytes(32), base_step=100, window=1000
    )
    with pytest.raises(ValueError, match="advisory face"):
        exact_vertex_itinerary(
            header, preferred_face=(directive.lane_order[0] + 1) % 32
        )
    with pytest.raises(ValueError):
        exact_mining_directive(
            header=header, target_be=bytes(32), base_step=2**32 - 1, window=2
        )
