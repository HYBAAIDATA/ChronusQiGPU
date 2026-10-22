"""Tests: learn-to-learn — research, φ-fold memory, apply."""

from __future__ import annotations

import traceback

import numpy as np

from hyba_data.learn_to_learn import (
    FoldedMemoryStore,
    LearnToLearn,
    _array_to_text,
    _text_to_array,
    build_learn_report,
)


def test_text_array_roundtrip_via_fold():
    store = FoldedMemoryStore()
    text = "Fold never truncate. Quantum serves data. Learn by looking things up."
    arr = _text_to_array(text)
    w = store.rt.phi_fold_write(arr, mode="cf_tower", depth=2)
    assert w["passed_gate"] is True
    u = store.rt.phi_unfold_read(w["handle"]["handle_id"])
    back = _array_to_text(np.asarray(u["data"]))
    # allow minor edge padding from unfold length
    assert text in back or back.startswith(text[:40])


def test_store_and_recall_without_network():
    store = FoldedMemoryStore()
    q = "unit-test-learn-memory-local"
    rec = store.store(
        query=q,
        summary="Local seed: φ is an instruction; compress by folding.",
        sources=[{"url": "local://seed", "title": "seed", "snippet": "φ fold"}],
    )
    assert rec.handle_id or rec.summary
    got = store.recall(q)
    assert got is not None
    assert "fold" in (got.summary or "").lower() or "φ" in (got.summary or "")


def test_learn_to_learn_seed_skills():
    eng = LearnToLearn()
    assert "search_web" in eng.SEED_SKILLS
    assert "fold_store_memory" in eng.SEED_SKILLS
    assert "ask_when_unknown" in eng.SEED_SKILLS


def test_apply_uses_memory():
    eng = LearnToLearn()
    q = "hyba-fold-never-truncate-apply-test"
    eng.memory.store(
        query=q,
        summary="Apply fold to working sets; never truncate; quantum serves data.",
        sources=[{"url": "local://doctrine", "title": "doctrine", "snippet": "fold"}],
    )
    out = eng.apply(q, context="hermes_product")
    assert "APPLY" in out.get("status", "") or out.get("apply")
    assert "fold" in (out.get("apply") or {}).get("guidance", "").lower()


def test_build_learn_report_artifact():
    # may use network; must not crash
    r = build_learn_report("golden ratio mathematics")
    assert r.get("status")
    assert r.get("artifact") or r.get("memory")


def main() -> int:
    failed = 0
    for name in sorted(n for n in globals() if n.startswith("test_")):
        try:
            globals()[name]()
            print("PASS", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, type(e).__name__, e)
            traceback.print_exc()
    print(f"summary failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
