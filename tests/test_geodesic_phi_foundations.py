"""Evidence-first regressions for the shared H4 geometrical substrate.

These are software mathematical checks; no hardware, deployment, quantum
speedup or physical continuum Yang-Mills claim is inferred.
"""
from fractions import Fraction

import pytest

from chronus.geodesic.dual_120cell import build_dual_120_cell
from chronus.geodesic.embedding_11d import (
    PHI, Q5, embed_dual_vertex, embedding_certificate, project_4d,
    dual_vertex_4d,
)
from chronus.geodesic.m32 import build_m32_domains, assign_domain
from chronus.geodesic.spectral import H4GraphLaplacian
from chronus.geodesic.gauge import (
    GaussianRational, SU2Link, gauge_transform, triangle_holonomy, wilson_action,
)
from chronus.geodesic.fiber_bundle import (
    FiniteH4FiberBundle, IDENTITY, TOTAL_SECTIONS,
    encode_basis_index, decode_basis_index, inversion_transition,
)
from chronus.geodesic.root_systems import roots_e8, roots_d, roots_a
from chronus.geodesic.discovery import (
    ManifoldDiscovery, MetricConstraint, exact_determinant,
    is_spd, identity_metric,
)


def test_dual_120cell_f_vector_incidences_and_exact_centroids():
    dual = build_dual_120_cell()
    assert dual.invariants() == {
        "dimension": 4, "coordinate_field": "Q(sqrt(5))",
        "coordinate_denominator": 16, "vertices": 600,
        "edges": 1200, "pentagonal_faces": 720,
        "dodecahedral_cells": 120, "vertex_degree": 4,
        "euler_characteristic_boundary": 0,
    }
    assert len(set(dual.vertices)) == 600
    assert all(len(f) == len(set(f)) == 5 for f in dual.faces)
    assert all(len(c) == len(set(c)) == 20 for c in dual.cells)
    assert all(len(t) == 4 for t in dual.primal_tetrahedra)


def test_11d_embedding_exact_and_reversible():
    report = embedding_certificate()
    assert report["input_vertices"] == 600
    assert report["output_coordinates"] == 11
    assert report["distinct_images"] == 600
    assert report["left_inverse_verified"] is True
    assert report["affine_span_dimension"] <= 11
    assert report["H4_irreducible_representation_proven"] is False
    for i in (0, 1, 119, 120, 599):
        assert project_4d(embed_dual_vertex(i)) == dual_vertex_4d(i)
    assert PHI*PHI == PHI + 1


def test_m32_exact_face_directions():
    domains = build_m32_domains()
    assert len(domains) == 32
    assert len({x.normal for x in domains}) == 32
    assert [x.index for x in domains[:12]] == list(range(12))
    assert all(x.polyhedral == "dodecahedron-face" for x in domains[:12])
    assert all(x.polyhedral == "icosahedron-face" for x in domains[12:])
    assert assign_domain(domains[0].normal).lane == 0
    with pytest.raises(ValueError):
        assign_domain((Q5(0), Q5(0), Q5(0)))


def test_h4_laplacian_exact_quadratic_identity():
    graph = H4GraphLaplacian.canonical()
    assert graph.exact_invariants() == {
        "dimension": 120, "edges": 720, "degree": 12,
        "trace": 1440, "trace_square": 18720,
        "constant_kernel_verified": True,
        "positive_semidefinite_identity": True,
    }
    impulse = (1,) + (0,) * 119
    assert graph.quadratic_form(impulse) == 12
    assert graph.apply((3,)*120) == (0,)*120


def test_su2_wilson_holonomy_gauge_invariance():
    one = SU2Link.identity()
    nontrivial = SU2Link(GaussianRational(Fraction(3,5)),
                          GaussianRational(Fraction(4,5)))
    assert nontrivial * nontrivial.inverse() == one
    links = {(0,1): nontrivial, (1,2): one, (2,0): one}
    phase = SU2Link(GaussianRational(0,1), GaussianRational(0))
    transformed = gauge_transform(links, {0: phase, 1: one, 2: one})
    assert wilson_action((0,1,2), links) == Fraction(4,5)
    assert wilson_action((0,1,2), transformed) == Fraction(4,5)
    assert triangle_holonomy((2,1,0), links) == triangle_holonomy(
        (0,1,2), links).inverse()


def test_fiber_bijection_automorphism_and_finite_basis():
    inv = inversion_transition()
    assert inv != IDENTITY
    assert FiniteH4FiberBundle({(0,1): inv}).transport((0,1,0), 14) == 14
    assert FiniteH4FiberBundle({(0,1): inv}).holonomy((0,1,0)) == IDENTITY
    assert encode_basis_index(31,599) == TOTAL_SECTIONS - 1
    assert decode_basis_index(TOTAL_SECTIONS-1) == (31,599)
    with pytest.raises(ValueError):
        FiniteH4FiberBundle({(0,1): tuple(reversed(IDENTITY[:-1])) + (0,)})


def test_exact_root_system_generators():
    assert len(roots_a(3)) == 12
    assert len(roots_d(4)) == 24
    assert len(roots_e8()) == 240
    assert all(sum(x*x for x in r) == 2 for r in roots_e8())


def test_exact_metric_discovery_monotone_spd_and_no_false_isomorphism():
    discovery = ManifoldDiscovery(2, Fraction(1,16))
    constraints = (
        MetricConstraint((Fraction(1),Fraction(0)), Fraction(4)),
        MetricConstraint((Fraction(0),Fraction(1)), Fraction(1)),
    )
    result = discovery.learn_metric(constraints, max_steps=10)
    assert result.objective <= result.initial_objective
    assert result.steps > 0
    assert is_spd(result.metric)
    assert exact_determinant(identity_metric(2)) == 1
    proposals = ManifoldDiscovery.propose_manifold(
        graph_vertices=120, graph_edges=720, regular_degree=12)
    assert "H4_600_CELL_GRAPH" in proposals["candidates"]
    assert "NOT_GROUP_ISOMORPHISM" in proposals["classification"]


def test_legacy_bilinear_proxy_and_true_alternating_extension_component():
    from chronus.quantum.geometric_polychoron import (
        F257Phi, QuantumGeometricTensor,
    )
    from chronus.geodesic.hermitian import conjugate
    zero, one, phi = F257Phi.zero(), F257Phi.one(), F257Phi.phi()
    state = (one,zero)
    di = (zero,one)
    dj = (zero,phi)
    qij = QuantumGeometricTensor.evaluate_hermitian(state,di,dj)
    qji = QuantumGeometricTensor.evaluate_hermitian(state,dj,di)
    assert qij.tensor == phi
    assert qij.alternating_coefficient == 1
    assert qji.tensor == conjugate(phi)
    assert qji.alternating_coefficient == (-1) % 257
    assert qij.is_hermitian_partner_of(qji)
    assert QuantumGeometricTensor.evaluate([1,0],[0,1],[0,2])[1] == 0


def test_public_120cell_facade_exact_tetrahedron_dual_bijection():
    from chronus.geodesic.dual_120cell import Polychoron120Cell
    cell = Polychoron120Cell()
    assert len(cell.vertices) == 600
    assert len(cell.edges) == 1200
    assert len(cell.pentagonal_faces) == 720
    assert len(cell.dodecahedral_cells) == 120
    assert cell.coordinate_denominator == 16
    for i, tetra in enumerate(build_dual_120_cell().primal_tetrahedra):
        assert cell.index_of_tetrahedron(tetra) == i
    with pytest.raises(ValueError):
        cell.index_of_tetrahedron((0,0,1,2))


def test_m32_public_exact_partition_and_numeric_ridges():
    from chronus.geodesic.m32 import M32DomainPartition
    import numpy as np

    m32 = M32DomainPartition()
    assert len(m32.dodeca_faces) == 12
    assert len(m32.icosa_faces) == 20
    assert len(m32.all_normals) == 32
    assert m32.assign_lane(m32.all_normals[0]) == 0
    adjacency = m32.adjacency
    assert adjacency.shape == (32,32)
    assert np.array_equal(adjacency, adjacency.T)
    assert not np.any(np.diag(adjacency))
    assert int(adjacency.sum()) == 180
    assert m32.adjacency_classification.startswith("APPROXIMATE_FLOAT64_")
