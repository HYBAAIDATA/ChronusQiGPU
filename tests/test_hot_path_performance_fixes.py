"""Hot-path fixes found by the end-to-end stack smoke (2026-10-12).

1. exact_vertex_itinerary / exact_face_order recomputed ~1 s of exact
   rational geometry for every nonce lease of one job, on the mining event
   loop. They are memoised on (header[:76], geometry) with identical output.
2. OntologyStore.verify_attestation recursed once per chain link (crash past
   the interpreter recursion limit) and bulk verification re-walked to the
   root per record (quadratic). Iterative, with an optional per-pass memo.
"""

from __future__ import annotations

import dataclasses
import os
import sys

import pytest

from chronus.mla1517.mining import exact_search as es


@pytest.fixture(scope="module")
def state():
    return es.precompute_exact_search()


def test_itinerary_memo_is_exact_and_nonce_independent(state):
    header = os.urandom(80)
    es._exact_memo.clear()
    first = es.exact_vertex_itinerary(header, state)
    again = es.exact_vertex_itinerary(header[:76] + os.urandom(4), state)
    reference = es._exact_vertex_itinerary(header, state, es._exact_face_order(header, state), True)
    assert first == again == reference
    assert es.exact_face_order(header, state) == es._exact_face_order(header, state)
    assert len(set(first)) == 600


def test_memo_distinguishes_headers_and_hilbert_flag(state):
    a, b = os.urandom(80), os.urandom(80)
    assert es.exact_vertex_itinerary(a, state) != es.exact_vertex_itinerary(b, state)
    assert es.exact_vertex_itinerary(a, state, use_hilbert=False) == es._exact_vertex_itinerary(
        a, state, es._exact_face_order(a, state), False
    )


def test_memo_is_bounded(state):
    es._exact_memo.clear()
    for _ in range(es._EXACT_MEMO_SIZE + 10):
        es.exact_face_order(os.urandom(80), state)
    assert len(es._exact_memo) <= es._EXACT_MEMO_SIZE


def test_lookalike_state_never_reuses_a_cached_result(state):
    header = os.urandom(80)
    es.exact_face_order(header, state)
    frames = list(state.coarse_frames_11d)
    frames[0], frames[1] = frames[1], frames[0]
    forged = dataclasses.replace(state, coarse_frames_11d=tuple(frames))  # same claimed digest
    assert forged.digest == state.digest
    assert es.exact_face_order(header, forged) == es._exact_face_order(header, forged)


def test_validation_still_runs_on_cache_hits(state):
    header = os.urandom(80)
    es.exact_vertex_itinerary(header, state)
    with pytest.raises(ValueError):
        es.exact_vertex_itinerary(header[:79], state)
    wrong = (es.exact_face_order(header, state)[0] + 1) % 32
    with pytest.raises(ValueError, match="advisory face"):
        es.exact_vertex_itinerary(header, state, preferred_face=wrong)


def _store(tmp_path):
    from hyba_db import OntologyStore, Quota

    store = OntologyStore(tmp_path / "o.db", b"k" * 32)
    tenant = store.provision_client("perf", Quota(100_000, 10**9))
    return store, tenant.tenant_id


def test_attestation_chain_longer_than_recursion_limit(tmp_path):
    store, tid = _store(tmp_path)
    depth = sys.getrecursionlimit() + 200
    last = None
    for i in range(depth):
        last = store.attest(tid, f"s{i}", {"i": i})
    assert store.verify_attestation(tid, last.id)
    store.close()


def test_bulk_memo_proves_each_attestation_once_and_still_detects_tamper(tmp_path):
    store, tid = _store(tmp_path)
    ids = [store.attest(tid, f"s{i}", {"i": i}).id for i in range(50)]
    proved: set[str] = set()
    for aid in ids:
        assert store.verify_attestation(tid, aid, verified=proved)
    assert set(ids) <= proved
    store._db.execute(
        "UPDATE attestations SET details_json=? WHERE tenant_id=? AND id=?", ('{"i": -1}', tid, ids[10])
    )
    store._db.commit()
    from hyba_db.models import IntegrityFailure

    with pytest.raises(IntegrityFailure):
        store.verify_attestation(tid, ids[-1])  # fresh call: full walk, sees the edit
    report = store.verify_database(tid)
    passed = report["passed"] if isinstance(report, dict) else report.passed
    assert not passed
    store.close()
