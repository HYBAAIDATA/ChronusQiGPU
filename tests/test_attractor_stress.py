"""Deliverable A: attractor stress tests (exact integers / Fractions, real OVID + THESEUS)."""
from __future__ import annotations

import ast
import json
import pathlib
from fractions import Fraction

import pytest

from chronus.kernels.gl2_transform import FoldedRegisterN, hensellift_m15
from chronus.ovid.folded_custody import (
    OvidAdapter, OvidFoldedAdapter, TheseusAdapter, verify_attested,
)
from chronus.ovid.transform import OvidTransformService
from chronus.quantum import attractor_stress as A
from chronus.quantum.triad_grover import EVENT_EXHAUSTED, EVENT_VERIFIED, run_triad_exact_grover_search
from chronus.storage.durable import DurableTheseusService

pytestmark = pytest.mark.real

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADERS = ROOT / "tests" / "vectors" / "mainnet_975565_976064.json"
GENESIS = bytes.fromhex(
    "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27a"
    "c72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c")
STRUCTURED = (A.orbit_dlog, A.trace_fibre, A.order_finding, A.triangular_linear,
              A.simple_quadratic, A.square_root)
KS = (16, 32, 64)


def _adapter(path, tenant="t"):
    custody = DurableTheseusService(str(path / "theseus.sqlite3"))
    store = TheseusAdapter(custody, tenant)
    return custody, store, OvidFoldedAdapter(OvidAdapter(OvidTransformService()), store)


# ---------------------------------------------------------------- algebra
@pytest.mark.parametrize("k", KS)
def test_m_k_is_identity_mod_2_and_2_power_continuity(k):
    mask = (1 << k) - 1
    M = hensellift_m15(k)
    assert tuple(x & 1 for row in M for x in row) == (1, 0, 0, 1)
    # M^(2^t) = I (mod 2^(t+1)): the source of the continuity shift s = 1 in Test 1
    for t in range(k - 1):
        P = A.mat_pow(M, 1 << t, mask)
        m = (1 << (t + 1)) - 1
        assert (P[0][0] & m, P[0][1] & m, P[1][0] & m, P[1][1] & m) == (1, 0, 0, 1)
    assert A.mat_pow(M, 1 << (k - 1), mask) == ((1, 0), (0, 1))
    assert A.mat_pow(M, 1 << (k - 2), mask) != ((1, 0), (0, 1))     # order exactly 2^(k-1)


@pytest.mark.parametrize("k", KS)
def test_orbit_lengths_exact(k):
    p = A.orbit_dlog(k, 8)
    assert p.notes["orbit_length"] == 1 << (k - 1)
    o = A.order_finding(k, 12)
    assert o.notes["order"] == 1 << 10            # W/4 => exactly 4 marked exponents in [1, W]


# ---------------------------------------------------------------- continuity census
@pytest.mark.parametrize("fam", STRUCTURED)
@pytest.mark.parametrize("k", KS)
def test_structured_families_are_2adically_continuous(fam, k):
    p = fam(k, 8)
    gt = A.ground_truth(p)
    agree, total = A.continuity_census(p, gt.observables)
    assert agree == total == sum(256 - (1 << t) for t in range(1, 8))


@pytest.mark.parametrize("k", KS)
def test_generic_subset_sum_is_not_continuous(k):
    p = A.generic_subset_sum(k, 8)
    agree, total = A.continuity_census(p, A.ground_truth(p).observables)
    assert agree < total


def test_sha256d_point_target_is_not_continuous():
    p = A.sha256d_point(GENESIS, 8)
    agree, total = A.continuity_census(p, A.ground_truth(p).observables)
    assert agree < total // 2


# ---------------------------------------------------------------- classical structured methods
@pytest.mark.parametrize("fam", STRUCTURED)
@pytest.mark.parametrize("k", KS)
@pytest.mark.parametrize("n", (8, 12))
def test_hensel_tree_recovers_exactly_the_marked_set(fam, k, n):
    p = fam(k, n)
    gt = A.ground_truth(p)
    assert p.planted_index in gt.marked
    ch = A.classical_hensel(p)
    assert ch["found"] == gt.marked
    assert ch["evaluations"] < p.W
    cb = A.classical_best(p, gt)
    assert sorted(cb["found"]) == gt.marked
    assert cb["evaluations"] <= ch["evaluations"]


@pytest.mark.parametrize("k", KS)
def test_mitm_solves_generic_subset_sum_where_hensel_cannot(k):
    p = A.generic_subset_sum(k, 12)
    gt = A.ground_truth(p)
    assert A.classical_hensel(p)["found"] != gt.marked
    cb = A.classical_best(p, gt)
    assert cb["found"] == gt.marked and cb["evaluations"] == 2 * 64


# ---------------------------------------------------------------- triad pipelines (real OVID / THESEUS)
@pytest.mark.parametrize("fam", STRUCTURED + (A.generic_subset_sum,))
def test_triad_as_built_evaluates_every_state(tmp_path, fam):
    custody, store, ad = _adapter(tmp_path)
    p = fam(32, 8)
    gt = A.ground_truth(p)
    r = A.triad_as_built(p, ad, "b")
    assert r["evaluations"] == p.W and r["marked_count"] == len(gt.marked)
    assert r["winner_index"] in gt.marked
    assert r["iterations"] == A.ideal_grover(p.W, len(gt.marked))["iterations"]
    assert custody.verify_journal_continuity("t")
    recs = store.journal_receipts((EVENT_VERIFIED,))
    assert len(recs) == 1 and verify_attested(recs[0][1])["winner_index"] == r["winner_index"]


@pytest.mark.parametrize("fam", STRUCTURED)
@pytest.mark.parametrize("k", KS)
def test_triad_structured_variant_prunes_and_finds(tmp_path, fam, k):
    custody, store, ad = _adapter(tmp_path)
    p = fam(k, 12)
    gt = A.ground_truth(p)
    s = A.triad_structured(p, ad, "s")
    assert s["found"] and set(s["found"]) <= set(gt.marked)
    assert s["evaluations"] < p.W // 4
    assert custody.verify_journal_continuity("t")
    for ev, body in store.journal_receipts((EVENT_VERIFIED, EVENT_EXHAUSTED)):
        verify_attested(body)
    # every branch handle is restorable from THESEUS after a restart
    _, _, ad2 = _adapter(tmp_path)
    for _e, body in store.journal_receipts((EVENT_VERIFIED,)):
        h = ad2.restore_from_theseus(body["artifact_id"])
        assert h.register.active_dimension == 0


def test_triad_structured_cannot_use_collapse_on_sha256d(tmp_path):
    _, _, ad = _adapter(tmp_path)
    p = A.sha256d_point(GENESIS, 8)
    s = A.triad_structured(p, ad, "x")
    gt = A.ground_truth(p)
    assert gt.marked == [p.planted_index]
    assert p.planted_index not in s["found"]          # graded lift is not admissible: target lost


def test_sha256d_ensemble_hit_rate_is_chance_level():
    H = json.loads(HEADERS.read_text(encoding="utf-8"))["blocks"][:100]
    hits = sum(A.hensel_residual_counts(A.sha256d_point(bytes.fromhex(h["header_hex"]), 12))["hit"] for h in H)
    assert hits <= 2


# ---------------------------------------------------------------- triad_grover residual fix
def test_residual_search_after_prior_collapse_reports_full_index(tmp_path):
    """Regression for triad_grover.py: generators collapsed before the search must be
    part of the reported winner index (they were dropped, failing the read-out check)."""
    _, _, ad = _adapter(tmp_path)
    reg = FoldedRegisterN.from_domain_offset(1000, num_generators=6, k=32)
    h = ad.commit_collapse_step(ad.commit_collapse_step(ad.stage_domain("r", reg), 0, 1), 1, 1)
    r = run_triad_exact_grover_search(adapter=ad, handle=h, oracle_predicate=lambda v: (v & 0xFFFFFFFF) == 1000 + 0b110111)
    assert r.found and r.winner_index == 0b110111 and (r.winner_value & 0xFFFFFFFF) == 1000 + 0b110111
    assert r.oracle_evaluations == 16 and r.iterations == 3


# ---------------------------------------------------------------- quantum reference + audit
@pytest.mark.parametrize("w,m,t", [(4096, 1, 50), (65536, 1, 201), (4096, 4, 25), (65536, 4, 100), (16, 1, 3)])
def test_ideal_grover_reference(w, m, t):
    q = A.ideal_grover(w, m)
    assert q["iterations"] == t and isinstance(q["probability"], Fraction)


def test_attractor_module_has_no_floats_or_rng():
    src = (ROOT / "src/chronus/quantum/attractor_stress.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("float", "complex")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert not any(n.split(".")[0] in ("random", "numpy", "math", "unittest") for n in names)
