"""Geometric reasoning: verified operations and an honest negative case."""

from __future__ import annotations

import numpy as np
import pytest

from toe.geometry import (
    GeometryError,
    PoincareBall,
    SpectralGeometry,
    bfs_tree,
    disk_distance,
    embed_tree,
    routing_study,
)
from toe.poincare_golden_11d import poincare_golden_distance
from toe.voyage import fixture_graph


def _points(ball, n, seed, scale=0.4):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        x = rng.normal(size=ball.dim) * scale
        if ball.contains(x):
            out.append(x)
    return out


def test_golden_ball_is_the_11d_metric():
    ball = PoincareBall.golden_11d()
    pts = _points(ball, 20, 1)
    worst = max(abs(ball.distance(a, b) - poincare_golden_distance(a, b)) for a in pts for b in pts)
    assert worst < 1e-12


def test_metric_axioms_and_geodesics():
    ball = PoincareBall.golden_11d()
    pts = _points(ball, 12, 2)
    for a in pts:
        assert ball.distance(a, a) == pytest.approx(0.0, abs=1e-12)
        for b in pts:
            assert ball.distance(a, b) == pytest.approx(ball.distance(b, a), abs=1e-12)
            for c in pts[:6]:
                assert ball.distance(a, c) <= ball.distance(a, b) + ball.distance(b, c) + 1e-9
    u, v = pts[0], pts[1]
    for t in (0.1, 0.5, 0.9):
        g = ball.geodesic(u, v, t)
        assert ball.distance(u, g) + ball.distance(g, v) == pytest.approx(ball.distance(u, v), abs=1e-9)
        assert ball.distance(u, g) == pytest.approx(t * ball.distance(u, v), abs=1e-9)
    assert np.allclose(ball.exp_map(u, ball.log_map(u, v)), v, atol=1e-12)


def test_mobius_translation_is_an_isometry():
    ball = PoincareBall(3)
    pts = _points(ball, 6, 3)
    shift = np.array([0.2, -0.1, 0.3])
    for a in pts:
        for b in pts:
            ta, tb = ball.mobius_add(shift, a), ball.mobius_add(shift, b)
            assert ball.distance(ta, tb) == pytest.approx(ball.distance(a, b), abs=1e-9)


def test_boundary_points_are_refused_not_clamped():
    ball = PoincareBall(2)
    with pytest.raises(GeometryError):
        ball.distance([1.0, 0.0], [0.0, 0.0])
    proj = ball.project([3.0, 4.0])
    assert proj["clipped"] is True


def test_frechet_mean_converges():
    ball = PoincareBall(2)
    out = ball.frechet_mean([[0.3, 0.0], [-0.3, 0.0], [0.0, 0.3], [0.0, -0.3]])
    assert np.allclose(out["mean"], [0.0, 0.0], atol=1e-9)
    assert out["gradient_norm"] < 1e-9


def test_hyperbolic_routing_delivers_where_euclidean_strands():
    fx = fixture_graph()
    edges = [tuple(e) for e in fx["edges"]]
    coords = {k: tuple(v) for k, v in fx["positions"].items()}
    study = routing_study(edges, euclidean=coords, tau=2.5)
    assert study["hyperbolic"]["delivery_rate"] == 1.0
    assert study["euclidean"]["delivery_rate"] < 0.8


def test_negative_case_plain_grid_gains_nothing():
    nodes = [(x, y) for x in range(6) for y in range(6)]
    edges = [((x, y), (x + 1, y)) for x, y in nodes if x < 5] + [((x, y), (x, y + 1)) for x, y in nodes if y < 5]
    study = routing_study(edges, euclidean={n: (float(n[0]), float(n[1])) for n in nodes}, tau=2.5)
    # Euclidean greedy is already perfect here; the hyperbolic tree route
    # delivers too but with longer paths — no advantage, recorded as such.
    assert study["euclidean"]["delivery_rate"] == 1.0
    assert study["euclidean"]["mean_stretch"] == pytest.approx(1.0)
    assert study["hyperbolic"]["mean_stretch"] > study["euclidean"]["mean_stretch"]


def test_tree_embedding_edge_length_and_resolution_bound():
    parent = bfs_tree([(0, 1), (0, 2), (1, 3), (1, 4), (2, 5)], 0)
    emb = embed_tree(parent, tau=2.0)
    for n, p in parent.items():
        if p is not None:
            assert disk_distance(emb["coords"][n], emb["coords"][p]) == pytest.approx(2.0, abs=1e-9)
    deep = {0: None, **{i: i - 1 for i in range(1, 20)}}
    with pytest.raises(GeometryError):
        embed_tree(deep, tau=2.5)


def test_spectral_clustering_recovers_planted_blocks():
    rng = np.random.default_rng(7)
    n = 20
    A = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            same = (i < 10) == (j < 10)
            if rng.random() < (0.8 if same else 0.05):
                A[i, j] = A[j, i] = 1.0
    labels = SpectralGeometry(A).spectral_clustering(2)
    first = set(labels[:10].tolist())
    second = set(labels[10:].tolist())
    assert len(first) == 1 and len(second) == 1 and first != second
