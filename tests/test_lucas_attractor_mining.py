"""Test suite for Lucas 15 Attractor, Search Database, Pathfinder, Mining Bridge, and Engine.

Verifies:
1. LucasAttractor exact invariants (L_15 = 1364, drift, Zeckendorf, Cassini = -1)
2. SearchDatabase storage, retrieval, Cassini verification, prime-exponent healing
3. Pathfinder 32-face frame resultant, discrete gradient, convergence
4. MiningBridge structured vs unstructured decision
5. OntologyMiningEngine end-to-end mine and benchmark
6. GeodesicNavigator geodesic query upgrade
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from Intelligence.lucas_attractor import LucasAttractor, PHI
from Intelligence.pathfinder import Pathfinder
from Intelligence.search_database import SearchDatabase
from Intelligence.mining_bridge_ontology import MiningBridge
from Intelligence.ontology_mining_engine import OntologyMiningEngine
from Intelligence.hardened_unified_substrate import (
    ManifoldCurvature,
    PrimeStorageManifold,
    TensorCoreGPU_Context,
)


@pytest.fixture()
def manifold():
    gpu = TensorCoreGPU_Context()
    m = PrimeStorageManifold(gpu, n_primes=25)
    yield m
    gpu.shutdown()


# -- Lucas Attractor ---------------------------------------------------------


def test_lucas_15_attractor_invariants():
    att = LucasAttractor(n=15)
    assert att.n == 15
    assert att.L_n == 1364
    assert att.cassini == -1  # F_14 * F_16 - F_15^2 = (-1)^15
    assert abs(att.drift - 0.000733137) < 1e-5
    # Zeckendorf of 1364 is unique: 987 + 377 = 1364
    assert sum(att.zeckendorf) == 1364
    assert len(att.zeckendorf) >= 1


def test_lucas_attractor_scores():
    att = LucasAttractor(n=15)
    exact = att.attractor_score(1364.0)
    assert exact == 1.0
    near = att.attractor_score(1365.0)
    far = att.attractor_score(2000.0)
    assert 0.0 < far < near < exact
    tot = att.total_score(1364.0)
    assert 0.0 <= tot <= 1.0
    state = att.state()
    assert state["L_n"] == 1364
    assert state["theorem_proven"] is False


# -- Search Database ----------------------------------------------------------


def test_search_database_store_and_query():
    db = SearchDatabase(n_anchors=90)
    node = db.store(1364.0, b"attractor_payload")
    assert node.payload == b"attractor_payload"
    assert node.lucas_score > 0.5
    queried = db.query(1364.0)
    assert queried is not None
    assert queried.payload == b"attractor_payload"


def test_search_database_healing():
    db = SearchDatabase(n_anchors=90)
    node = db.store(1364.0, b"resilient_payload")
    node.cassini_ok = False
    healed_count = db.heal()
    assert healed_count == 1
    assert db.nodes[node.anchor].cassini_ok is True
    assert len(db.heal_log) == 1
    assert db.heal_log[0]["kind"] == "prime_exponent_restore"


def test_search_database_collision_preserves_both():
    """Regression: values 1.0 and 1.1 shared home anchor 2 and the second
    silently overwrote the first. Linear probing must retain both."""
    db = SearchDatabase(n_anchors=90)
    n1 = db.store(1.0, b"first")
    n2 = db.store(1.1, b"second")
    assert len(db.nodes) == 2
    assert db.nodes[n1.anchor].payload == b"first"
    assert db.nodes[n2.anchor].payload == b"second"
    assert db.query(1.0).payload == b"first"


def test_search_database_restore_same_value_updates():
    """Re-storing the same value updates in place, not a new slot."""
    db = SearchDatabase(n_anchors=90)
    n1 = db.store(1.0, b"v1")
    n2 = db.store(1.0, b"v2")
    assert len(db.nodes) == 1
    assert n2.anchor == n1.anchor
    assert db.nodes[n1.anchor].payload == b"v2"


def test_search_database_heal_repairs_corrupted_payload():
    """Digest mismatch -> restore from the verified replica."""
    db = SearchDatabase(n_anchors=90)
    node = db.store(1364.0, b"original_payload")
    node.payload = b"CORRUPTED"
    assert db.heal() == 1
    assert db.nodes[node.anchor].payload == b"original_payload"
    assert db.heal_log[0]["kind"] == "digest_restore"


def test_search_database_heal_evicts_unrecoverable():
    """Payload and replica both corrupt -> evict, log, don't pretend."""
    db = SearchDatabase(n_anchors=90)
    node = db.store(1364.0, b"original_payload")
    node.payload = b"CORRUPTED"
    db._replicas[node.anchor] = b"ALSO_CORRUPT"
    assert db.heal() == 0
    assert node.anchor not in db.nodes
    assert db.heal_log[0]["kind"] == "evicted_unrecoverable"


# -- Pathfinder ---------------------------------------------------------------


def test_pathfinder_32_faces_and_metric():
    pf = Pathfinder(n_faces=32)
    assert len(pf.faces) == 32
    assert pf.metric.shape == (11, 11)
    for i in range(11):
        assert abs(pf.metric[i, i] - (PHI ** (i / 11.0))) < 1e-12


def test_pathfinder_convergence():
    pf = Pathfinder(n_faces=32)
    r0 = pf._anchor_to_vector(1)
    res = pf.navigate(r0, 47.0, max_iter=20, tol=1e-8)
    assert res["converged"] is True
    assert res["iterations"] <= 20


# -- Mining Bridge ------------------------------------------------------------


def test_mining_bridge_decision():
    bridge = MiningBridge()
    dec_res = bridge.decide(1364)
    assert dec_res.strategy == "structured"
    assert dec_res.confidence > 0.0
    assert dec_res.theorem_proven is False
    dec_unif = bridge.decide(987654)
    assert dec_unif.strategy == "unstructured"
    assert dec_unif.theorem_proven is False


def test_mining_bridge_mine():
    bridge = MiningBridge()
    out_struct = bridge.mine([1364], target=55.0)
    assert out_struct["strategy"] == "structured"
    assert "iterations" in out_struct
    assert out_struct["theorem_proven"] is False
    out_unstruct = bridge.mine([987654], target=55.0)
    assert out_unstruct["strategy"] == "unstructured"
    assert out_unstruct["theorem_proven"] is False


# -- Ontology Mining Engine ---------------------------------------------------


def test_ontology_mining_engine():
    engine = OntologyMiningEngine()
    out = engine.mine([1364], target=47.0)
    assert "attractor" in out
    assert out["attractor"]["L_n"] == 1364
    assert out["theorem_proven"] is False


def test_ontology_mining_benchmark():
    engine = OntologyMiningEngine()
    bench = engine.benchmark(n_trials=10)
    assert bench["n_trials"] == 10
    assert bench["structured_count"] + bench["unstructured_count"] == 10
    assert bench["theorem_proven"] is False


# -- GeodesicNavigator --------------------------------------------------------


def test_geodesic_navigator_query_geodesic(manifold):
    payload = b"geodesic_attractor_attested_bytes"
    uid = manifold.ingest_sync(payload, ManifoldCurvature.GOLDEN_DENSE)
    tensor = manifold.tensors[uid]
    anchor = tensor.integer_anchor
    nav = manifold.geodesic
    search_vec = np.zeros(11)
    search_vec[0] = float(anchor) * math.sqrt(PHI)
    recovered = nav.query_geodesic(search_vec)
    assert recovered == payload
