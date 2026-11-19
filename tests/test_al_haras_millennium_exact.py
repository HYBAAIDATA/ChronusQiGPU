"""Exact behaviour of the AL HARAS classes that carry legacy "Millennium" names.

Known answers come from independent computations in this file (closed forms,
a brute-force Kantorovich-Rubinstein dual, exhaustive point counts, LMFDB
values); mutation tests show that a wrong implementation is rejected. This file
does not import fastapi.
"""

import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import pytest

from chronus.security.al_haras import expander
from chronus.security.al_haras import millennium_security as ms
from chronus.security.al_haras import millennium_unification as mu
from chronus.security.al_haras import (
    AnosovColdBootScrambler,
    GrandMillenniumUnificationNexus,
    HarmonicCohomologyBridge,
    HodgeCovertChannelFilter,
    NetworkGraphEdge,
    ParabolicFlowSingularityBridge,
    PicardLefschetzAntiJammingFilter,
    RicciCurvatureDeCloaker,
    SpectralDualityBridge,
    UltrametricMemorySandbox,
)

pytestmark = pytest.mark.simulated

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    REPO_ROOT / "src/chronus/security/al_haras/millennium_security.py",
    REPO_ROOT / "src/chronus/security/al_haras/millennium_unification.py",
]

TWO_TRIANGLES = [
    ("a", "b", 1), ("b", "c", 1), ("c", "a", 1),
    ("d", "e", 1), ("e", "f", 1), ("f", "d", 1),
    ("c", "d", 1),
]


# ---------------------------------------------------------------- helpers


def _graph(edges, alpha=0, threshold=Fraction(-2, 5)):
    decloaker = RicciCurvatureDeCloaker(curvature_threshold=threshold, idleness=alpha)
    for edge in edges:
        decloaker.add_edge(*edge)
    return decloaker


def _adjacency(edges):
    adj = {}
    for a, b, _ in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def _all_hop_distances(adj):
    table = {}
    for start in adj:
        dist, frontier = {start: 0}, [start]
        while frontier:
            nxt = []
            for u in frontier:
                for v in adj[u]:
                    if v not in dist:
                        dist[v] = dist[u] + 1
                        nxt.append(v)
            frontier = nxt
        table[start] = dist
    return table


def _measure(edges, x, alpha):
    weights = {}
    for a, b, w in edges:
        if a == x:
            weights[b] = weights.get(b, 0) + Fraction(w)
        if b == x:
            weights[a] = weights.get(a, 0) + Fraction(w)
    total = sum(weights.values())
    measure = {z: (1 - alpha) * w / total for z, w in weights.items()}
    if alpha:
        measure[x] = Fraction(alpha)
    return measure


def _kantorovich_dual_w1(mu_, nu_, dist):
    """W1 = max sum_z f(z) (mu - nu)(z) over 1-Lipschitz f on the support.

    The dual constraint matrix (rows e_a - e_b) is totally unimodular and hop
    distances are integers, so an optimal f is integral with f(anchor) = 0 and
    |f(z)| <= d(anchor, z): exhaustive search over those integers is exact.
    """
    support = sorted(set(mu_) | set(nu_), key=str)
    weight = {z: mu_.get(z, 0) - nu_.get(z, 0) for z in support}
    anchor, rest = support[0], support[1:]
    best = [None]
    assigned = {anchor: 0}

    def extend(i, value):
        if i == len(rest):
            if best[0] is None or value > best[0]:
                best[0] = value
            return
        z = rest[i]
        for f in range(-dist[anchor][z], dist[anchor][z] + 1):
            if all(abs(f - assigned[w]) <= dist[z][w] for w in assigned):
                assigned[z] = f
                extend(i + 1, value + f * weight[z])
                del assigned[z]

    extend(0, Fraction(0))
    return best[0]


def _lcg(seed):
    state = seed
    while True:
        state = (6364136223846793005 * state + 1442695040888963407) % (1 << 64)
        yield state >> 33


def _sample_graphs(count):
    gen = _lcg(2026)
    graphs = []
    while len(graphs) < count:
        n = 3 + next(gen) % 5
        edges = {}
        for _ in range(n - 1 + next(gen) % (n + 1)):
            a, b = next(gen) % n, next(gen) % n
            if a != b:
                edges[frozenset((a, b))] = (a, b, Fraction(1 + next(gen) % 5, 1 + next(gen) % 3))
        if edges:
            graphs.append(list(edges.values()))
    return graphs


def _northwest_corner(supply, demand):
    plan = [[Fraction(0)] * len(demand) for _ in supply]
    s, d = list(supply), list(demand)
    i = j = 0
    while i < len(s) and j < len(d):
        q = min(s[i], d[j])
        plan[i][j] = q
        s[i] -= q
        d[j] -= q
        if s[i] == 0:
            i += 1
        else:
            j += 1
    return plan


# ------------------------------------------------ Ollivier-Ricci curvature


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_curvature_closed_form(n):
    edges = [(i, j, 1) for i in range(n) for j in range(i + 1, n)]
    for alpha in (Fraction(0), Fraction(1, 2), Fraction(1, 5)):
        expected = 1 - abs(alpha - (1 - alpha) / (n - 1))
        assert set(_graph(edges, alpha).compute_ollivier_ricci_curvatures().values()) == {expected}


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_cycle_graph_curvature_is_zero(n):
    edges = [(i, (i + 1) % n, 1) for i in range(n)]
    assert set(_graph(edges).compute_ollivier_ricci_curvatures().values()) == {Fraction(0)}


def test_tree_curvature_matches_closed_form():
    # On a tree with alpha = 0: kappa(x, y) = -2 * max(0, 1 - 1/d_x - 1/d_y).
    edges = [("h1", f"a{i}", 1) for i in range(3)] + [("h2", f"b{i}", 1) for i in range(2)]
    edges += [("h1", "h2", 1), ("b0", "c0", 1)]
    degree = {}
    for a, b, _ in edges:
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
    curvatures = _graph(edges).compute_ollivier_ricci_curvatures()
    for a, b, _ in edges:
        expected = -2 * max(Fraction(0), 1 - Fraction(1, degree[a]) - Fraction(1, degree[b]))
        assert curvatures[f"{a}->{b}"] == expected
    assert curvatures["h1->h2"] == Fraction(-5, 6)


def test_weighted_curvature_matches_brute_force_kantorovich_dual():
    checked = 0
    for edges in _sample_graphs(30):
        dist = _all_hop_distances(_adjacency(edges))
        for alpha in (Fraction(0), Fraction(1, 2)):
            decloaker = _graph(edges, alpha)
            curvatures = decloaker.compute_ollivier_ricci_curvatures()
            for edge in decloaker.edges:
                x, y = edge.source, edge.target
                w1 = _kantorovich_dual_w1(_measure(edges, x, alpha), _measure(edges, y, alpha), dist)
                assert curvatures[f"{x}->{y}"] == 1 - w1 == edge.curvature
                checked += 1
            assert decloaker.execute_perelman_surgery()["transport_optimality_certified"] is True
    assert checked > 100


def test_heavy_leaf_edge_is_flat_and_the_light_edges_beside_it_are_negative():
    # Hand computation (alpha = 0): m_HQ1 = (2, 2, 100)/104 on (HQ2, HQ3, leaf), m_HQ2 = 1/2 on HQ1 and HQ3.
    # Optimal transport: leaf -> HQ1 52/104 (cost 1), leaf -> HQ3 48/104 (cost 2), HQ2 -> HQ3 2/104 (cost 1):
    # W1 = 150/104, kappa = -23/52. The leaf edge itself has W1 = 1, kappa = 0.
    edges = [("HQ_1", "HQ_2", 2), ("HQ_2", "HQ_3", 2), ("HQ_3", "HQ_1", 2), ("HQ_1", "leaf", 100)]
    res = _graph(edges).execute_perelman_surgery()
    assert res["curvatures"] == {
        "HQ_1->HQ_2": "-23/52",
        "HQ_2->HQ_3": "1/2",
        "HQ_3->HQ_1": "-23/52",
        "HQ_1->leaf": "0",
    }
    assert sorted((e["source"], e["target"]) for e in res["removed_edges"]) == [("HQ_1", "HQ_2"), ("HQ_3", "HQ_1")]
    lazy = _graph(edges, alpha=Fraction(1, 2)).compute_ollivier_ricci_curvatures()
    assert lazy["HQ_1->leaf"] == Fraction(25, 26)


def test_surgery_removes_exactly_the_edges_below_threshold():
    decloaker = _graph(TWO_TRIANGLES)
    res = decloaker.execute_perelman_surgery()
    assert res["status"] == "EDGES_REMOVED"
    assert res["transport_optimality_certified"] is True
    assert (res["removed_edge_count"], res["remaining_edge_count"]) == (1, 6)
    bridge = res["removed_edges"][0]
    assert (bridge["source"], bridge["target"]) == ("c", "d")
    assert (bridge["ollivier_ricci_curvature"], bridge["wasserstein_1"]) == ("-2/3", "5/3")
    assert res["curvatures"]["a->b"] == "1/2" and res["curvatures"]["b->c"] == "1/3"
    assert (res["connected_components_before"], res["connected_components_after"]) == (1, 2)
    assert {frozenset((e.source, e.target)) for e in decloaker.edges} == {
        frozenset(edge[:2]) for edge in TWO_TRIANGLES if set(edge[:2]) != {"c", "d"}
    }
    json.dumps(res)
    again = decloaker.execute_perelman_surgery()
    assert again["status"] == "NO_EDGE_BELOW_THRESHOLD" and again["removed_edge_count"] == 0
    assert again["connected_components_before"] == again["connected_components_after"] == 2


def test_threshold_is_strict_and_exact():
    at = _graph(TWO_TRIANGLES, threshold="-2/3").execute_perelman_surgery()
    assert at["removed_edge_count"] == 0 and at["edges_below_threshold"] == 0
    just_above = _graph(TWO_TRIANGLES, threshold=Fraction(-2, 3) + Fraction(1, 10**30)).execute_perelman_surgery()
    assert just_above["removed_edge_count"] == 1


def test_float_inputs_are_read_exactly():
    decloaker = RicciCurvatureDeCloaker(curvature_threshold=-0.4)
    decloaker.add_edge("x", "y", 0.1)
    assert decloaker.curvature_threshold == Fraction(-2, 5)
    assert decloaker.edges[0] == NetworkGraphEdge("x", "y", Fraction(1, 10))
    curvature = decloaker.compute_ollivier_ricci_curvatures()["x->y"]
    assert isinstance(curvature, Fraction) and curvature == 0


def test_parallel_edges_are_merged_by_adding_weights():
    base = [("a", "b", 1), ("b", "c", 1), ("c", "a", 1), ("c", "d", 3), ("d", "e", 1)]
    split = base[:3] + [("c", "d", 1), ("d", "c", 2), ("d", "e", 1)]
    assert _graph(base).compute_ollivier_ricci_curvatures() == _graph(split).compute_ollivier_ricci_curvatures()


def test_invalid_edges_and_parameters_are_rejected():
    decloaker = RicciCurvatureDeCloaker()
    with pytest.raises(ValueError):
        decloaker.add_edge("a", "a", 1)
    for bad in (0, -1, "-1/2", float("nan"), float("inf")):
        with pytest.raises(ValueError):
            decloaker.add_edge("a", "b", bad)
    with pytest.raises(TypeError):
        decloaker.add_edge("a", "b", True)
    with pytest.raises(ValueError):
        RicciCurvatureDeCloaker(idleness=1)
    assert decloaker.edges == []
    assert RicciCurvatureDeCloaker().execute_perelman_surgery()["status"] == "NO_EDGES"


def test_degree_limit_is_enforced():
    decloaker = RicciCurvatureDeCloaker()
    for i in range(ms.MAX_NODE_DEGREE + 1):
        decloaker.add_edge("hub", i, 1)
    with pytest.raises(ValueError, match="degree"):
        decloaker.execute_perelman_surgery()


def test_transport_certificate_rejects_wrong_plans_and_duals():
    supply = [Fraction(1, 2), Fraction(1, 2)]
    demand = [Fraction(1, 2), Fraction(1, 2)]
    cost = [[1, 0], [0, 1]]
    plan, total, phi, psi = ms.solve_transport(supply, demand, cost)
    assert total == 0 and ms.certify_transport(supply, demand, cost, plan, phi, psi)
    diagonal = [[Fraction(1, 2), Fraction(0)], [Fraction(0), Fraction(1, 2)]]  # feasible, cost 1
    assert not ms.certify_transport(supply, demand, cost, diagonal, phi, psi)
    wrong_marginals = [[Fraction(0), Fraction(1, 2)], [Fraction(1, 2), Fraction(1, 10)]]
    assert not ms.certify_transport(supply, demand, cost, wrong_marginals, phi, psi)
    assert not ms.certify_transport(supply, demand, cost, plan, [phi[0] + 1, phi[1]], psi)


def test_surgery_fails_closed_when_the_transport_solver_is_wrong(monkeypatch):
    def northwest(supply, demand, cost):
        plan = _northwest_corner(supply, demand)
        total = sum(plan[i][j] * cost[i][j] for i in range(len(supply)) for j in range(len(demand)))
        return plan, total, [Fraction(0)] * len(supply), [Fraction(0)] * len(demand)

    monkeypatch.setattr(ms, "solve_transport", northwest)
    decloaker = _graph(TWO_TRIANGLES)
    res = decloaker.execute_perelman_surgery()
    assert res["transport_optimality_certified"] is False
    assert res["status"] == "CURVATURE_NOT_CERTIFIED_NOTHING_REMOVED"
    assert res["removed_edge_count"] == 0 and len(decloaker.edges) == len(TWO_TRIANGLES)


# ---------------------------------------------------------- Hodge decomposition


def test_cycle_decomposition_known_answer():
    res = HodgeCovertChannelFilter.sanitize_side_channels([1, 5, 2, 8])
    assert res["status"] == "DECOMPOSITION_VERIFIED"
    assert res["projection"] == ["-3", "1", "-2", "4"]
    assert res["residual"] == ["4"] * 4
    assert res["potential"] == ["0", "-3", "-2", "-4"]
    assert (res["trace_norm_sq"], res["projection_norm_sq"], res["residual_norm_sq"]) == ("94", "30", "64")
    assert all(res["identities_verified"].values())
    for legacy in ("side_channel_nullified", "covert_leakage_power_after", "sanitized_trace"):
        assert legacy not in res
    json.dumps(res)


def test_decompose_signal_is_exact_and_its_co_exact_part_vanishes():
    exact, co_exact, harmonic = HodgeCovertChannelFilter.decompose_signal([0.1, 0.2, 0.3])
    assert harmonic == [Fraction(1, 5)] * 3
    assert exact == [Fraction(-1, 10), Fraction(0), Fraction(1, 10)]
    assert co_exact == [Fraction(0)] * 3


def test_the_variation_of_a_trace_is_kept_not_removed():
    trace = [10, 25, 11, 28, 10, 26, 11, 27]
    res = HodgeCovertChannelFilter.sanitize_side_channels(trace)
    mean = Fraction(sum(trace), len(trace))
    assert [Fraction(x) for x in res["projection"]] == [x - mean for x in trace]
    assert Fraction(res["projection_norm_sq"]) == sum((x - mean) ** 2 for x in trace) > 0


@pytest.mark.parametrize("n", [3, 4, 7])
def test_general_decomposition_agrees_with_the_cycle_closed_form(n):
    trace = [Fraction(3 * i * i - 2, i + 1) for i in range(n)]
    general = HodgeCovertChannelFilter.decompose_edge_flow(list(range(n)), [(i, (i + 1) % n) for i in range(n)], trace)
    exact, co_exact, harmonic = HodgeCovertChannelFilter.decompose_signal(trace)
    assert general["verified"] is True
    assert general["gradient"] == exact and general["harmonic"] == harmonic
    assert general["curl"] == co_exact == [Fraction(0)] * n
    assert general["dimensions"] == {"edges": n, "gradient_space": n - 1, "curl_space": 0, "harmonic_space": 1}


def test_filling_a_triangle_turns_its_circulation_into_curl():
    nodes, edges, circulation = ["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")], [1, 1, 1]
    hollow = HodgeCovertChannelFilter.decompose_edge_flow(nodes, edges, circulation)
    filled = HodgeCovertChannelFilter.decompose_edge_flow(nodes, edges, circulation, triangles=[("a", "b", "c")])
    assert hollow["harmonic"] == [1, 1, 1] and hollow["curl"] == [0, 0, 0]
    assert filled["curl"] == [1, 1, 1] and filled["harmonic"] == [0, 0, 0]
    assert (hollow["dimensions"]["harmonic_space"], filled["dimensions"]["harmonic_space"]) == (1, 0)
    assert hollow["verified"] and filled["verified"]


def test_gradient_flow_is_recovered_with_its_potential():
    nodes = ["p", "q", "r", "s"]
    edges = [("p", "q"), ("q", "r"), ("p", "r"), ("r", "s"), ("s", "p")]
    f = {"p": Fraction(0), "q": Fraction(3), "r": Fraction(-1, 2), "s": Fraction(7, 3)}
    flow = [f[b] - f[a] for a, b in edges]
    res = HodgeCovertChannelFilter.decompose_edge_flow(nodes, edges, flow, triangles=[("p", "q", "r")])
    assert res["gradient"] == flow and not any(res["curl"]) and not any(res["harmonic"])
    potential = dict(zip(nodes, res["potential"]))
    assert [potential[b] - potential[a] for a, b in edges] == flow


def test_identity_checks_reject_the_previous_central_difference_gradient():
    trace = [Fraction(x) for x in (1, 5, 2, 8, 3, 7)]
    n = len(trace)
    mean = sum(trace) / n
    centred = [x - mean for x in trace]
    legacy = [(centred[(i + 1) % n] - centred[i - 1]) / 2 for i in range(n)]
    potential = [Fraction(0)]
    for value in legacy[:-1]:
        potential.append(potential[-1] + value)
    checks = HodgeCovertChannelFilter.verify_cycle_decomposition(trace, legacy, [mean] * n, potential)
    assert checks["reconstruction"] is False


def test_sanitize_reports_failure_when_the_decomposition_is_wrong(monkeypatch):
    real = HodgeCovertChannelFilter._cycle_parts

    def shifted(trace):
        parts = real(trace)
        parts["harmonic"] = [h + 1 for h in parts["harmonic"]]
        return parts

    monkeypatch.setattr(HodgeCovertChannelFilter, "_cycle_parts", staticmethod(shifted))
    assert HodgeCovertChannelFilter.sanitize_side_channels([1, 5, 2, 8])["status"] == "DECOMPOSITION_CHECK_FAILED"


def test_trace_validation():
    assert HodgeCovertChannelFilter.sanitize_side_channels([])["status"] == "EMPTY_TRACE"
    assert HodgeCovertChannelFilter.decompose_signal([]) == ([], [], [])
    with pytest.raises(ValueError):
        HodgeCovertChannelFilter.sanitize_side_channels([1.0, float("nan")])
    with pytest.raises(ValueError):
        HodgeCovertChannelFilter.sanitize_side_channels([0] * (ms.MAX_TRACE_SAMPLES + 1))
    single = HodgeCovertChannelFilter.sanitize_side_channels([7])
    assert (single["projection"], single["residual"]) == (["0"], ["7"])
    with pytest.raises(ValueError):
        HodgeCovertChannelFilter.decompose_edge_flow(["a", "b", "c"], [("a", "b")], [1], triangles=[("a", "b", "c")])


# ------------------------------------------------------- p-adic distances and balls


def test_p_adic_valuation_and_distance_are_exact():
    sandbox = UltrametricMemorySandbox(prime_p=257)
    assert sandbox.p_adic_valuation(257**3 * 5) == 3
    assert sandbox.p_adic_valuation(-257) == 1
    assert sandbox.p_adic_valuation(0) is None
    assert sandbox.p_adic_distance(1000, 1000) == 0
    assert sandbox.p_adic_distance(0, 257) == Fraction(1, 257)
    assert sandbox.p_adic_distance(0, 257**2 * 7) == Fraction(1, 257**2)
    assert sandbox.p_adic_distance(0, 1) == 1
    assert isinstance(sandbox.p_adic_distance(0, 257), Fraction)


def test_strong_triangle_inequality_exhaustively():
    sandbox = UltrametricMemorySandbox(prime_p=3)
    points = range(-13, 14)
    absolute = {x: sandbox.p_adic_absolute_value(x) for x in range(-27, 28)}
    for x in points:
        for y in points:
            assert absolute[x + y] <= max(absolute[x], absolute[y])
            for z in points:
                assert sandbox.p_adic_distance(x, z) <= max(sandbox.p_adic_distance(x, y), sandbox.p_adic_distance(y, z))


def test_ball_relation_matches_brute_force_enumeration():
    p = 3
    sandbox = UltrametricMemorySandbox(prime_p=p)
    window = range(-120, 120)
    for ca in range(-6, 7):
        for cb in range(-6, 7):
            for ka in (1, 2, 3):
                for kb in (1, 2, 3):
                    ball_a = {x for x in window if (x - ca) % p**ka == 0}
                    ball_b = {x for x in window if (x - cb) % p**kb == 0}
                    relation = sandbox.ball_relation(ca, ka, cb, kb)
                    assert (relation == "disjoint") == (not ball_a & ball_b)
                    if relation == "equal":
                        assert ball_a == ball_b
                    if relation == "a_inside_b":
                        assert ball_a < ball_b
                    if relation == "b_inside_a":
                        assert ball_b < ball_a


def test_enclave_check_reports_the_computed_relation():
    sandbox = UltrametricMemorySandbox(prime_p=257)
    sandbox.register_enclave("kernel", 0x1000)
    sandbox.register_enclave("user", 0x5000)
    res = sandbox.verify_non_overlapping_isolation("kernel", "user")
    assert (0x1000 - 0x5000) % 257 != 0
    assert res["balls_disjoint"] is True and res["status"] == "ADDRESS_SETS_DISJOINT"
    assert res["valuation_of_center_difference"] == 0 and res["p_adic_distance"] == "1"
    assert res["ball_a"]["address_set"] == f"{0x1000 % 257} mod 257^1"
    for legacy in ("speculative_cross_bleed_possible", "isolation_guarantee", "intersection_topology"):
        assert legacy not in res
    json.dumps(res)


def test_congruent_enclaves_are_reported_as_intersecting():
    # The previous code shifted centres by registration order, so every pair looked disjoint.
    sandbox = UltrametricMemorySandbox(prime_p=257)
    sandbox.register_enclave("a", 5)
    sandbox.register_enclave("b", 5 + 3 * 257)
    res = sandbox.verify_non_overlapping_isolation("a", "b")
    assert res["balls_disjoint"] is False and res["relation"] == "equal"
    assert res["status"] == "ADDRESS_SETS_INTERSECT" and res["p_adic_distance"] == "1/257"
    sandbox.register_enclave("c", 5 + 257, ball_exponent=2)
    assert sandbox.verify_non_overlapping_isolation("c", "a")["relation"] == "a_inside_b"


def test_sandbox_input_validation():
    with pytest.raises(ValueError):
        UltrametricMemorySandbox(prime_p=256)
    sandbox = UltrametricMemorySandbox(prime_p=5)
    with pytest.raises(TypeError):
        sandbox.register_enclave("x", True)
    with pytest.raises(ValueError):
        sandbox.register_enclave("x", 1, ball_exponent=0)
    sandbox.register_enclave("x", 1)
    with pytest.raises(ValueError):
        sandbox.verify_non_overlapping_isolation("x", "missing")


# --------------------------------------------- zeroisation and the cat map


def _pisano_period(m):
    a, b, t = 0, 1, 0
    while True:
        a, b, t = b, (a + b) % m, t + 1
        if (a, b) == (0, 1):
            return t


def test_cat_map_step_and_inverse():
    x, y = 42, 99
    assert AnosovColdBootScrambler.iterate_arnold_map(x, y, iterations=1) == ((2 * x + y) % 257, (x + y) % 257)
    for m in (256, 257):
        for px, py in ((0, 1), (42, 99), (255, 255)):
            forward = AnosovColdBootScrambler.iterate_arnold_map(px, py, iterations=5, modulus=m)
            assert AnosovColdBootScrambler.inverse_arnold_map(*forward, iterations=5, modulus=m) == (px % m, py % m)


def test_cat_map_period_matches_the_pisano_period():
    # A = F^2 for the Fibonacci matrix F, whose order mod m is the Pisano period.
    for m in (2, 3, 10, 256, 257):
        pisano = _pisano_period(m)
        assert AnosovColdBootScrambler.map_period(m) == (pisano // 2 if pisano % 2 == 0 else pisano)


def test_scramble_is_a_reversible_permutation_not_erasure():
    data = bytes(range(256)) + b"!"
    for rounds in (1, 7, 191):
        scrambled = AnosovColdBootScrambler.scramble_bytes(data, rounds)
        assert scrambled != data
        assert AnosovColdBootScrambler.unscramble_bytes(scrambled, rounds) == data
    assert AnosovColdBootScrambler.scramble_bytes(data, 192) == data
    images = {AnosovColdBootScrambler.scramble_bytes(bytes((x, y))) for x in range(256) for y in range(256)}
    assert len(images) == 256 * 256


def test_purge_zeroises_a_mutable_buffer_in_place():
    secret = bytearray(b"TEST_KEY_MATERIAL_0123456789")
    res = AnosovColdBootScrambler.emergency_ram_purge(secret)
    assert secret == bytearray(len(secret))
    assert res["status"] == "ZEROISED_AND_VERIFIED"
    assert (res["zeroised_in_place"], res["nonzero_bytes_after"], res["buffer_length"]) == (True, 0, len(secret))
    backing = bytearray(b"abcdef")
    view_res = AnosovColdBootScrambler.emergency_ram_purge(memoryview(backing)[2:5])
    assert backing == bytearray(b"ab\x00\x00\x00f") and view_res["buffer_length"] == 3
    json.dumps(res)


def test_purge_reports_immutable_input_as_not_zeroised():
    secret = b"immutable"
    res = AnosovColdBootScrambler.emergency_ram_purge(secret)
    assert res["status"] == "NOT_ZEROISED_IMMUTABLE_INPUT" and res["zeroised_in_place"] is False
    assert secret == b"immutable"
    readonly = AnosovColdBootScrambler.emergency_ram_purge(memoryview(bytearray(b"xy")).toreadonly())
    assert readonly["status"] == "NOT_ZEROISED_IMMUTABLE_INPUT"
    for legacy in ("cold_boot_recovery_possible", "remanence_state", "lyapunov_exponent", "shannon_entropy_bits"):
        assert legacy not in res
    with pytest.raises(TypeError):
        AnosovColdBootScrambler.emergency_ram_purge("text")


class _IgnoresWrites(bytearray):
    def __setitem__(self, key, value):
        pass


def test_purge_detects_a_buffer_that_ignores_writes():
    res = AnosovColdBootScrambler.emergency_ram_purge(_IgnoresWrites(b"secret"))
    assert res["status"] == "ZEROISATION_VERIFY_FAILED"
    assert res["zeroised_in_place"] is False and res["nonzero_bytes_after"] == 6


# ------------------------------------------------- not implemented: anti-jamming


def test_picard_lefschetz_filter_is_reported_as_not_implemented():
    res = PicardLefschetzAntiJammingFilter.filter_jammed_waveform([(1.0, 1.0), (1.1, 0.9)], jamming_phase_intensity=3.0)
    assert res["status"] == "NOT_IMPLEMENTED" and res["input_samples"] == 2
    assert res["jamming_phase_intensity"] == "3" and res["jamming_phase_intensity_used"] is False
    for legacy in ("snr_improvement_db", "anti_jamming_recovery_status", "recovered_samples"):
        assert legacy not in res
    with pytest.raises(ValueError):
        PicardLefschetzAntiJammingFilter.filter_jammed_waveform([(1.0,)])
    with pytest.raises(ValueError):
        PicardLefschetzAntiJammingFilter.filter_jammed_waveform([(1.0, float("inf"))])
    json.dumps(res)


# ------------------------------------------- legacy "unification" module


LMFDB_53_2_A_A = {
    2: -1, 3: -3, 5: 0, 7: -4, 11: 0, 13: -3, 17: -3, 19: -5, 23: 7, 29: -7, 31: 4, 37: 5, 41: 6,
    43: -2, 47: -2, 53: -1, 59: -2, 61: -8, 67: -12, 71: 1, 73: -4, 79: -1, 83: -1, 89: -14, 97: 1,
}


def _exhaustive_count_53(p):
    return 1 + sum(1 for x in range(p) for y in range(p) if (y * y + x * y + y - x**3 + x * x) % p == 0)


def test_frobenius_traces_match_the_lmfdb_newform_53_2_a_a():
    # a_p of the weight-2 newform of level 53 (LMFDB 53.2.a.a, Hecke polynomials for p < 100).
    for p, a_p in LMFDB_53_2_A_A.items():
        res = HarmonicCohomologyBridge.compute_bsd_modular_eigenspace(p=p)
        assert res["frobenius_trace_ap"] == a_p, p
        assert res["independent_count_agrees"] is True and res["bound_satisfied"] is True
        assert res["status"] == "COMPUTED"
    assert HarmonicCohomologyBridge.compute_bsd_modular_eigenspace(p=53)["reduction_at_p"] == "multiplicative"


def test_point_count_formulas_match_exhaustive_search_on_small_fields():
    curves = [(1, -1, 1, 0, 0), (0, 0, 1, -1, 0), (1, 0, 0, 0, 1), (0, 1, 1, 1, 1), (1, 1, 1, 1, 1), (0, 0, 0, 1, 0)]
    for a1, a2, a3, a4, a6 in curves:
        for p in (2, 3, 5, 7, 11, 13):
            brute = 1 + sum(
                1
                for x in range(p)
                for y in range(p)
                if (y * y + a1 * x * y + a3 * y - (x**3 + a2 * x * x + a4 * x + a6)) % p == 0
            )
            assert mu.count_points((a1, a2, a3, a4, a6), p) == brute, (a1, a2, a3, a4, a6, p)


def test_point_count_at_257_matches_an_exhaustive_count():
    res = HarmonicCohomologyBridge.compute_bsd_modular_eigenspace(p=257)
    assert res["point_count"] == _exhaustive_count_53(257)
    assert res["frobenius_trace_ap"] == 258 - res["point_count"]
    assert res["frobenius_trace_ap"] ** 2 <= 4 * 257
    assert (res["discriminant"], res["conductor"]) == (-53, 53)
    assert res["identity_1728_disc_equals_c4_cubed_minus_c6_squared"] is True
    for legacy in ("hecke_eigenvalue_ap", "weil_bound_2sqrt_p", "tate_shafarevich_obstruction"):
        assert legacy not in res
    with pytest.raises(ValueError):
        HarmonicCohomologyBridge.compute_bsd_modular_eigenspace(p=255)


def test_spectral_certificate_is_the_paley_certificate():
    res = SpectralDualityBridge.verify_spectral_mass_gap(degree=6, prime_p=257)
    cert = expander.certify_paley(257)
    assert res["degree_used"] == cert["degree"] == 128 and res["requested_degree_available"] is False
    assert res["is_ramanujan"] is True and cert["is_ramanujan"] is True
    assert res["certificate"]["srg_parameters"] == [257, 128, 63, 64]
    # independent check: sqrt(257) < 17, so (1 + sqrt(257)) / 2 < 9 and 9^2 <= 4 * (128 - 1)
    assert 16**2 < 257 < 17**2 and 9**2 <= 4 * 127
    for legacy in ("yang_mills_mass_gap_strictly_positive", "ihara_zeta_riemann_hypothesis_satisfied"):
        assert legacy not in res
    json.dumps(res)
    with pytest.raises(ValueError):
        SpectralDualityBridge.verify_spectral_mass_gap(prime_p=7)


def test_pair_correlation_is_not_implemented_but_spacings_are_exact():
    res = SpectralDualityBridge.compute_gue_pair_correlation([4.5, 1.0, 2.0, 3.0])
    assert res["status"] == "NOT_IMPLEMENTED"
    assert res["normalised_spacings"] == ["6/7", "6/7", "9/7"]


def test_sheaf_consistency_check_carries_no_complexity_labels():
    agree = HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction([(1, 0, 0, 0)] * 3)
    disagree = HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction([(1, 0, 0, 0), (99, 0, 0, 0)])
    assert agree["consistent"] is True and agree["status"] == "CONSISTENT"
    assert disagree["consistent"] is False and disagree["coboundary_max_edge_norm_sq"] == str(98**2)
    for res in (agree, disagree):
        assert "tractability_class" not in res and "h1_obstruction_norm" not in res
        json.dumps(res)
    assert HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction([])["status"] == "NO_STATE_SUPPLIED"


def test_flow_model_is_not_implemented():
    res = ParabolicFlowSingularityBridge.verify_vorticity_dissipation_and_surgery(
        initial_enstrophy=150.0, viscosity_nu=0.1, timesteps=10
    )
    assert res["status"] == "NOT_IMPLEMENTED"
    assert "final_enstrophy" not in res and "bkm_finite_time_blowup_prevented" not in res


def test_unification_is_not_implemented_and_self_checks_pass():
    res = GrandMillenniumUnificationNexus.verify_grand_millennium_unification()
    assert res["status"] == "NOT_IMPLEMENTED"
    assert res["computed_checks_passed"] is True and all(res["computed_checks"].values())
    assert res["check_details"]["elliptic_curve"]["point_count"] == _exhaustive_count_53(257)
    for legacy in ("the_seven_problems_status", "unification_invariance_verified", "motto"):
        assert legacy not in res
    json.dumps(res)


def test_unification_self_checks_fail_when_a_point_count_is_wrong(monkeypatch):
    real = mu.count_points
    monkeypatch.setattr(mu, "count_points", lambda a, p: real(a, p) + 1)
    res = GrandMillenniumUnificationNexus.verify_grand_millennium_unification()
    assert res["computed_checks"]["curve_point_counts_agree_at_257"] is False
    assert res["computed_checks_passed"] is False


# ------------------------------------------------- purity, claims and labels


THEATRE_LABELS = (
    "IMPOSSIBLE", "GUARANTEE", "NULLIFIED", "RESTORED", "MAXIMAL_ENTROPY", "SATISFIED_VIA",
    "VERIFIED_VIA", "SURGERY_COMPLETED", "MATH_IS_MATH", "PERELMAN", "SPECTRE", "NANOSECOND",
)


def test_router_shaped_outputs_are_json_and_carry_no_theatre_labels():
    ricci = RicciCurvatureDeCloaker(curvature_threshold=-0.4)
    for source, target, weight in (
        ("node_A", "node_B", 1.0), ("node_B", "node_C", 2.0), ("node_A", "node_C", 1.5), ("node_C", "stealth_c2_node", 95.0)
    ):
        ricci.add_edge(source, target, weight)
    sandbox = UltrametricMemorySandbox(prime_p=257)
    sandbox.register_enclave("kernel_process_secure", 0x1000)
    sandbox.register_enclave("untrusted_speculative_workload", 0x5000)
    outputs = [
        ricci.execute_perelman_surgery(),
        HodgeCovertChannelFilter.sanitize_side_channels([1.2, 3.4, 1.1, 8.9, 1.3, 3.5, 1.2, 8.8]),
        sandbox.verify_non_overlapping_isolation("kernel_process_secure", "untrusted_speculative_workload"),
        AnosovColdBootScrambler.emergency_ram_purge(bytes.fromhex("414c5f48415241535f534f5645524549474e5f4b4559")),
        PicardLefschetzAntiJammingFilter.filter_jammed_waveform([(1.0, 0.5), (0.8, -0.3), (-0.4, 0.9)], 2.5),
        GrandMillenniumUnificationNexus.verify_grand_millennium_unification(),
    ]
    for out in outputs:
        text = json.dumps(out).upper()
        assert [label for label in THEATRE_LABELS if label in text] == []
        assert "status" in out


def test_modules_pass_the_purity_gate_and_import_no_float_math():
    spec = importlib.util.spec_from_file_location("purity_gate_for_tests", REPO_ROOT / "scripts/ci/purity_gate.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    for path in MODULES:
        assert gate.scan_file(path) == []
        text = path.read_text(encoding="utf-8")
        assert "from math import" not in text and "import math" not in text


def test_edited_files_carry_no_forbidden_claim_tokens():
    tokens = [bytes(t).lower() for t in json.loads((REPO_ROOT / "scripts/ci/claim_token_bytes.json").read_text())]
    for path in MODULES + [Path(__file__), REPO_ROOT / "tests/test_millennium_security.py"]:
        data = path.read_bytes().lower()
        assert [t for t in tokens if t in data] == [], path
