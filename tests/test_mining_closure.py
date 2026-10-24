"""Closure tests for the review findings on the mining workflow.

Covers the P0/P1/P2 contract list:
  * sha256_compress arbitrary-state correctness (was: IV-add bug)
  * midstate <-> full SHA-256d equivalence, parity with the live hasher
  * precompute-cache HIT/MISS/truth-label/atomic behaviour
  * deterministic replay of a mined job (no time/uuid/random inputs)
  * AST boundary: expected_/projected fields cannot reach submit params
  * integration chain: job -> header -> grind -> validate -> submit gate
"""

import ast
import hashlib
import json
import os
import re
import struct

import pytest

# Exercise canonical modules through the normal importer. Loading every mining
# file with spec_from_file_location polluted sys.modules without binding the
# children on their parent package, breaking unrelated protocol tests.
from python_backend.pythia_mining import midstate as ms
from python_backend.pythia_mining import precompute_cache as pc
from mining.bitcoin_hasher import sha256_midstate
from mining import stratum_bridge as sb
from mining.hash_pipeline import HashPipeline, double_sha256


# ---------------------------------------------------------------------------
# P0 — midstate / compression correctness
# ---------------------------------------------------------------------------


def test_sha256_compress_arbitrary_state_matches_hashlib():
    """Chained compression of a two-block message must equal hashlib.

    An 80-byte message pads to exactly two 64-byte compression blocks, so
    compress(b1, IV) then compress(b2, s1) must reproduce sha256(msg).  The
    old code added the working variables to IV unconditionally — this is the
    regression test for that bug.
    """
    msg = bytes(range(80))
    tail = bytearray(msg[64:])
    tail.append(0x80)
    while (len(tail) + 8) % 64 != 0:
        tail.append(0)
    tail += (len(msg) * 8).to_bytes(8, "big")
    assert len(tail) == 64

    s1 = ms.sha256_compress(msg[:64])  # IV path
    s2 = ms.sha256_compress(bytes(tail), state=s1)  # arbitrary-state path
    digest = b"".join(w.to_bytes(4, "big") for w in s2)
    assert digest == hashlib.sha256(msg).digest()


def test_sha256_compress_state_dependence():
    """Different input states must produce different output states."""
    block = bytes(range(64))
    s_iv = ms.sha256_compress(block)
    s_other = (0x12345678,) * 8
    assert ms.sha256_compress(block, state=s_iv) != ms.sha256_compress(block)
    assert ms.sha256_compress(block, state=s_other) != ms.sha256_compress(block)


def test_midstate_matches_full_sha256d():
    """The review's required test: midstate path == full double-SHA256."""
    header = bytearray(range(80))
    nonce = 12345678
    header[76:80] = nonce.to_bytes(4, "little")

    prefix = bytes(header[:64])
    tail = bytes(header[64:80])  # includes nonce bytes

    mid = ms.compute_midstate(prefix)
    accelerated = ms.double_sha256_from_midstate(mid, tail)
    reference = hashlib.sha256(hashlib.sha256(bytes(header)).digest()).digest()
    assert accelerated == reference


def test_midstate_equivalence_randomized():
    """20 random headers: midstate continuation == hashlib sha256d."""
    for _ in range(20):
        header = os.urandom(80)
        mid = ms.compute_midstate(header[:64])
        assert ms.double_sha256_from_midstate(mid, header[64:]) == double_sha256(header)


def test_midstate_parity_with_live_hasher():
    """python_backend midstate and mining.bitcoin_hasher midstate agree."""
    for i in range(4):
        prefix = bytes(range(i * 64, i * 64 + 64))
        py_words = ms.compute_midstate(prefix)
        py_bytes = b"".join(w.to_bytes(4, "big") for w in py_words)
        assert py_bytes == sha256_midstate(prefix)


# ---------------------------------------------------------------------------
# P0/P1 — precompute cache behaviour
# ---------------------------------------------------------------------------


def test_precompute_cache_hit_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "DEFAULT_DIR", str(tmp_path))
    calls = []

    def build():
        calls.append(1)
        return {"eigenvalues": [1.0, 2.0, 3.0], "dim": 32}

    vh = pc.geometry_version_hash(1.6180339887, 1364, {"gram_threshold": 0.75})
    tables, status = pc.load_or_build(vh, build)
    assert status == "MISS" and len(calls) == 1

    tables2, status2 = pc.load_or_build(vh, build)
    assert status2 == "HIT" and len(calls) == 1  # not rebuilt
    assert tables2 == tables


def test_precompute_cache_rejects_wrong_truth_label(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "DEFAULT_DIR", str(tmp_path))
    calls = []
    vh = pc.geometry_version_hash(1.0, 1364, {})

    def build():
        calls.append(1)
        return {"x": 1}

    pc.load_or_build(vh, build)
    path = pc._cache_path_for_version(vh)
    with open(path, "r", encoding="utf-8") as f:
        blob = json.load(f)
    blob["truth_label"] = "tampered"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f)

    _, status = pc.load_or_build(vh, build)
    assert status == "MISS" and len(calls) == 2


def test_policy_prior_roundtrip_and_label(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "DEFAULT_DIR", str(tmp_path))
    assert pc.load_policy_prior() == {"truth_label": "supposition-prior", "priors": {}}
    pc.persist_policy_prior(
        {"priors": {"m32_structured": {"observed_outcomes": [True, False, True]}}}
    )
    blob = pc.load_policy_prior()
    assert blob["truth_label"] == "supposition-prior"
    assert blob["priors"]["m32_structured"]["observed_outcomes"] == [True, False, True]


def test_resonance_table_hit_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "DEFAULT_DIR", str(tmp_path))
    _, status = pc.load_resonance_table("k1")
    assert status == "MISS"
    pc.persist_resonance_table("k1", {"table": [1, 2]})
    blob, status = pc.load_resonance_table("k1")
    assert status == "HIT"
    assert blob["truth_label"] == "precomputed-resonance"
    assert blob["table"] == [1, 2]


# ---------------------------------------------------------------------------
# P1 — deterministic replay of the live mining path
# ---------------------------------------------------------------------------


def _synthetic_job() -> sb.LiveJob:
    return sb.LiveJob(
        job_id="closure_job_1",
        prev_hash="00" * 32,
        coinb1="01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff",
        coinb2="ffffffff0100f2052a010000004341",
        merkle_branch=[],
        version="20000000",
        nbits="1d00ffff",
        ntime="66" + "00" * 7,
        clean_jobs=True,
        difficulty=1.0,
    )


def test_mine_job_deterministic_replay():
    """Identical job + window must produce byte-identical results."""
    job = _synthetic_job()
    pipe = HashPipeline(host=None, hasher_backend="cpu")
    out1 = sb.mine_job(job, "aa", 4, pipeline=pipe, nonce_window=512, base_nonce=0)
    out2 = sb.mine_job(job, "aa", 4, pipeline=pipe, nonce_window=512, base_nonce=0)
    assert out1["header"] == out2["header"]
    assert out1["target"] == out2["target"]
    r1, r2 = out1["result"], out2["result"]
    assert r1.hashes_computed == r2.hashes_computed == 512
    assert r1.winning_nonce == r2.winning_nonce
    assert r1.winning_hash == r2.winning_hash


def test_deterministic_id_helper():
    """The closure helper produces stable, input-derived identifiers."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "hm",
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "legacy",
            "papers",
            "discovery",
            "intelligence_substrate",
            "headless_miner.py",
        ),
    )
    # We cannot import the module (its python_backend layout resolves in the
    # monorepo); verify the helper exists as source and is pure.
    src = open(spec.origin, "r", encoding="utf-8").read()
    assert "def deterministic_id(prefix: str, *parts: object) -> str:" in src
    assert 'f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"' in src
    # No wall-clock identity anywhere in the session-id assignment.
    assert 'f"mining_session_{int(time.time())}"' not in src


# ---------------------------------------------------------------------------
# P1 — AST boundary: expected_/projected fields never reach submission
# ---------------------------------------------------------------------------

_BANNED = re.compile(r"expected_|effective_hashrate|projected|resonance|supposition")


def _submit_function_bodies(path: str) -> list:
    tree = ast.parse(open(path, "r", encoding="utf-8").read())
    fns = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "submit" in node.name:
            fns.append(node)
    return fns


@pytest.mark.parametrize(
    "path",
    [
        os.path.join(os.path.dirname(__file__), "..", "mining", "stratum_bridge.py"),
        os.path.join(os.path.dirname(__file__), "..", "mining", "production_miner.py"),
    ],
)
def test_submit_functions_carry_only_wire_fields(path):
    """No expected_*/projected/resonance identifier may appear inside any
    submit_* function — those fields are advisory and must stay out of the
    pool-facing payload."""
    fns = _submit_function_bodies(path)
    assert fns, f"no submit functions found in {path}"
    for fn in fns:
        for node in ast.walk(fn):
            if isinstance(node, ast.Name):
                assert not _BANNED.search(node.id), f"{node.id} in {fn.name}@{path}"
            if isinstance(node, ast.Attribute):
                assert not _BANNED.search(node.attr), f"{node.attr} in {fn.name}@{path}"
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not _BANNED.search(node.value), f"{node.value!r} in {fn.name}@{path}"


# ---------------------------------------------------------------------------
# P2 — integration chain on the live path
# ---------------------------------------------------------------------------


def test_integration_chain_job_to_submit_gate(monkeypatch):
    """job -> header -> grind -> validate -> submit gate.

    Asserts the chain on real code paths and that a candidate which was
    never hashed can never appear as found_nonce.
    """
    job = _synthetic_job()
    pipe = HashPipeline(host=None, hasher_backend="cpu")

    # 1. job received -> header built -> grind executes real hashes
    out = sb.mine_job(job, "aa", 4, pipeline=pipe, nonce_window=256, base_nonce=0)
    res = out["result"]
    assert len(bytes.fromhex(out["header"])) == 80
    assert res.hashes_computed == 256  # every digest physically computed

    # 2. at real difficulty this window almost certainly holds no winner —
    #    the point: no candidate becomes found_nonce without a target check.
    if not res.mining_success:
        assert res.winning_nonce is None
        assert res.winning_hash is None

    # 3. with an all-accepting target the first probe nonce wins — and the
    #    pipeline re-validates it independently before returning.
    header = bytes.fromhex(out["header"])
    hit = pipe.grind(header, b"\xff" * 32, [7, 8, 9])
    assert hit.winning_nonce == 7
    ref = double_sha256(header[:76] + struct.pack("<I", 7))
    assert hit.winning_hash == ref and ref[::-1] <= b"\xff" * 32

    # 4. submit gate is fail-closed: with approval env denied (and no
    #    loopback pool session), submit_share returns None, performs no I/O.
    monkeypatch.setattr(sb, "is_live_submit_approved", lambda env=None: False)
    bridge = sb.StratumBridge(host="192.0.2.1", port=3333, worker="w", password="p")
    assert bridge.submit_share(job.job_id, "aa", job.ntime, nonce=f"{7:08x}") is None
    assert bridge.submit_calls == 0

    # 5. when approval IS granted the gate opens — but a disconnected bridge
    #    still cannot submit (no silent success path either way).
    monkeypatch.setattr(sb, "is_live_submit_approved", lambda env=None: True)
    with pytest.raises(RuntimeError, match="not connected/authorized"):
        bridge.submit_share(job.job_id, "aa", job.ntime, nonce=f"{7:08x}")
    assert bridge.submit_calls == 0  # still no I/O — the wire never moved


def test_unhashed_candidate_never_becomes_found_nonce():
    """A nonce outside the scanned window cannot appear as a winner."""
    header = b"\x01" * 80
    pipe = HashPipeline(host=None, hasher_backend="cpu")
    res = pipe.grind(header, b"\xff" * 32, [0, 1, 2])
    # winner comes from the probe set only
    assert res.winning_nonce in (0, 1, 2)
    # an un-hashed nonce (e.g. 999) is never reported
    assert res.winning_nonce != 999


# ---------------------------------------------------------------------------
# Golden Quantum Framework modules — deterministic, honestly labeled
# ---------------------------------------------------------------------------


def test_mandelbrot_engine_deterministic_and_honest():
    from Intelligence.mandelbrot_resonance import (
        MandelbrotResonanceEngine,
        _escape_time,
        nonce_to_complex,
    )

    # escape-time contract: c=0 never escapes; c=2 escapes immediately
    n0, _ = _escape_time(0.0, 0.0)
    n2, _ = _escape_time(2.0, 0.0)
    assert n2 < n0
    # deterministic mapping + ordering
    assert nonce_to_complex(123) == nonce_to_complex(123)
    eng = MandelbrotResonanceEngine()
    nonces = [0, 1, 2, 3, 100, 0xFFFFFFFF]
    assert eng.order_candidates(nonces) == eng.order_candidates(nonces)
    assert sorted(eng.order_candidates(nonces)) == sorted(nonces)  # permutation only
    tel = eng.telemetry(nonces)
    assert tel["truth_label"] == "ordering-heuristic"
    assert "no SHA-256d" in tel["claim_boundary"]


def test_coherence_gate_regimes():
    from Intelligence.coherence_gate import QuantumCoherenceAnalyzer

    g = QuantumCoherenceAnalyzer()
    uniform = [1.0 / 32.0] * 32
    concentrated = [0.9] + [0.1 / 31.0] * 31

    # uniform faces + flat resonance -> fallback
    d = g.decide(face_probs=uniform, resonance_scores=[0.5, 0.5, 0.5])
    assert d.regime == "fallback"
    # concentrated structure -> solve leads
    assert g.decide(face_probs=concentrated).regime == "solve"
    # measured solve path no better than base rate -> fallback
    d2 = g.decide(
        face_probs=concentrated,
        solve_path_outcomes=[False] * 16,
        base_hit_rate=0.01,
    )
    assert d2.regime == "fallback"
    # identical inputs -> identical decision (deterministic)
    assert g.decide(face_probs=concentrated) == g.decide(face_probs=concentrated)


def test_resonance_probe_decide_rule_and_keying():
    """The audit gate: cache keys use the full header; _decide applies 3-SE."""
    import json as _json

    from legacy.mining.resonance_probe import _decide, _missing_job_ids, _ks_uniform_pvalue

    # full-header keying: the 10 captured headers share only 2 16-byte
    # prefixes — a [:32] key collides; a full key does not.
    headers = _json.load(open("experiments/resonance_headers.json", "r", encoding="utf-8"))
    assert len({r["header80"][:32] for r in headers}) < len(headers)
    assert len({r["header80"] for r in headers}) == len(headers)
    # job 06 gap disclosed
    assert "06" in _missing_job_ids(headers)

    # decide: null statistics -> no signal
    null_result = {
        "pooled": {o: {"n_hits": 39000, "mean_norm_pos": 0.5, "mean_se": 0.0015}
                   for o in ("11d", "m32", "linear")},
        "face_affinity_pooled": {"top8_hit_share_mean": 0.25,
                                 "top8_hit_share_se": 0.0018,
                                 "top8_expected_share": 0.25},
    }
    assert _decide(null_result)["signal_detected"] is False
    # 4-SE deviation -> signal
    sig = _json.loads(_json.dumps(null_result))
    sig["pooled"]["11d"]["mean_norm_pos"] = 0.5 + 4 * 0.0015
    assert _decide(sig)["signal_detected"] is True

    # KS sanity: uniform data -> p~1; skewed -> ~0
    import numpy as np

    assert _ks_uniform_pvalue(np.linspace(0, 1, 1000)) > 0.9
    assert _ks_uniform_pvalue(np.linspace(0, 0.01, 1000)) < 0.01


# ---------------------------------------------------------------------------
# PULVINI runtime — the spec's solve-first hierarchy, end to end
# ---------------------------------------------------------------------------


def test_pulvini_golden_transform_lossless():
    from Intelligence.pulvini_runtime import GoldenTransform

    gt = GoldenTransform()
    for n in range(1, 100):
        code = gt._fib_code(n)
        m, nxt = gt._fib_decode(code, 0)
        assert m == n and nxt == len(code)
    for seed in range(50):
        data = bytes(((seed * 37 + i * 13) & 0xFF) for i in range(1 + seed))
        assert gt.inverse(gt.transform(data)) == data


def test_pulvini_fold_unfold_persist_reload(tmp_path):
    from Intelligence.pulvini_runtime import DataFoldingEngine

    state = b"worker-state:" + bytes(range(64))
    dfe = DataFoldingEngine()
    dfe.fold(state, key="w")
    assert dfe.unfold("w") == state
    path = str(tmp_path / "ckpt.json")
    dfe.persist(path, "w")
    dfe2 = DataFoldingEngine()
    dfe2.reload(path)
    assert dfe2.unfold("w") == state  # restart continuity


def test_pulvini_transfinite_memory_roundtrip():
    from Intelligence.pulvini_runtime import TransfiniteMemoryMapper

    tmm = TransfiniteMemoryMapper()
    payload = b"best-known-position:0x00a4f2"
    addr = tmm.store_checkpoint("jobA", payload, {"pos": 42000})
    assert addr.composite != 0
    restored, meta = tmm.restore_checkpoint("jobA")
    assert restored == payload and meta["pos"] == 42000
    assert tmm.prime_gap_index(0) == 1  # 3 - 2


def test_pulvini_infinity_fold_and_chronos():
    from Intelligence.pulvini_runtime import (
        GoldenQuantumInfinityFold,
        ChronosSolver,
    )

    fold = GoldenQuantumInfinityFold(max_level=3)
    levels = fold.fold_levels(b"state-vector")
    assert len(levels) == 3
    cands = fold.collapse(b"state-vector", window=10000, per_level=4)
    assert len(cands) == 12 and all(0 <= c < 10000 for c in cands)
    assert fold.collapse(b"state-vector", window=10000) == cands  # deterministic
    ranked = ChronosSolver().solve(cands, [7, 7, 9], window=10000, top_k=5)
    assert len(ranked) == 5 and len(set(ranked)) == len(ranked)


def test_pulvini_fallback_engines_deterministic():
    from Intelligence.pulvini_runtime import (
        GoldenQuantumComputer,
        GoldenRatioMining,
    )

    f1 = GoldenQuantumComputer()
    a, b = f1.search(0, 512, top_k=8), f1.search(0, 512, top_k=8)
    assert a == b and len(a) == 8
    f2 = GoldenRatioMining()
    x, y = f2.select(42, count=8), f2.select(42, count=8)
    assert x == y and len(x) == 8
    assert GoldenRatioMining.GOLDEN_STEP == 0x9E3779B9  # floor(phi*2^32)


def test_pulvini_runtime_solve_and_fallback():
    from Intelligence.pulvini_runtime import PulviniRuntime

    rt = PulviniRuntime()
    state = b"job-context" + bytes(range(32))
    res = rt.solve("job1", state, window=50000, top_k=16)
    # solve path leads by default (spec: solve first)
    assert res.path_used == "solve" and res.regime == "solve"
    assert res.candidates and all(0 <= c < 50000 for c in res.candidates)
    assert {"S1_fold", "S2_checkpoint", "S3_gate", "S4_regions",
            "S5_fold_levels", "S6_ranked"} <= set(res.stage_outputs)
    # deterministic replay
    res2 = rt.solve("job1", state, window=50000, top_k=16)
    assert res2.candidates == res.candidates
    # measured failure history forces the fallback chain -> F1
    res3 = rt.solve("job2", state, window=50000, top_k=8,
                    solve_path_outcomes=[False] * 16, base_hit_rate=0.01)
    assert res3.path_used == "F1" and res3.regime == "fallback"
    assert res3.candidates


def test_pulvini_runtime_has_no_papers_discovery_imports():
    import inspect
    import Intelligence.pulvini_runtime as pulvini_runtime

    assert "papers.discovery" not in inspect.getsource(pulvini_runtime)


def test_golden_constants_registry():
    from python_backend.pythia_mining.golden_constants import GOLDEN_CONSTANTS
    import math

    gc = GOLDEN_CONSTANTS
    assert abs(gc.PHI - (1 + math.sqrt(5)) / 2) < 1e-15
    assert gc.lucas(15) == 1364 and gc.LUCAS_15 == 1364
    assert gc.lucas(20) == 15127 == gc.LUCAS_20
    assert gc.PISOT_DRIFT_15 == abs(gc.PHI_15 - gc.LUCAS_15)
    # frozen: constants cannot be mutated silently
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        gc.PHI = 3.14
