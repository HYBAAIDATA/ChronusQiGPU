"""Executable F1-F6 qualification of the integrated EUCLID v17 runtime.

One test per closure requirement from ``config/euclid-v17-integration-gates.json``:

- F1 episode-right-revocation — per-episode dispatch rights end revoked on
  normal return, solver exception and cancellation.
- F2 component-evidence-binding — the adaptive PERSISTED stage advances only
  when the durable custody write verifiably happened.
- F3 fresh-process-replay — RESTART_VERIFIED comes from a fresh interpreter
  reading durable THESEUS custody; a same-process reload proves nothing.
- F4 organ-lifetime-identity — recomposition preserves live ``task-world-*``
  identities, so later episodes never collide on duplicate organ ids.
- F5 canonical-custody — adaptive knowledge is creator-bound state persisted
  through canonical THESEUS/OVID custody, never a private JSON authority.
- F6 negative-transfer-detection — a mismatched curriculum that degrades a
  class is detected and produces an auditable remediation decision.

These tests exercise the production composition root, the governed Delegator,
the durable evidence chain and the enterprise custody plane end to end.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aethel.enterprise.custody import EnterpriseCustody
from euclid.cognition.baselines import DelegatorExecutor
from euclid.cognition.reachability import ReachabilityStage
from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
from euclid.runtime import EuclidRuntime

CUSTODY_KEY = b"v17-integration-gate-key-32b!"
CUSTODY_CHILD = Path(__file__).resolve().parent / "euclid_custody_restart_child.py"
ADAPTIVE_RECORD = "euclid-adaptive-knowledge-creator-1"


@pytest.fixture()
def custody(tmp_path):
    plane = EnterpriseCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    try:
        yield plane
    finally:
        plane.close()


def _runtime(tmp_path, name="state", creator="creator-1"):
    return EuclidRuntime(creator_id=creator, state_dir=tmp_path / name)


def _episode(seed, family="program-transformation"):
    spec, truth = generate_task(family, seed=seed, partition="evaluation")
    return spec, WorldExecutor(MechanismWorld(spec, truth, seed=seed))


def _right(rt):
    return rt.rights.permits(
        "creator-1", "task-world-1", "task-world-1.execute", "dispatch"
    )


def _assert_right_revoked(rt):
    assert not _right(rt), "per-episode dispatch right survived the episode"
    with pytest.raises(PermissionError):
        DelegatorExecutor(
            rt.delegator, "task-world-1", "task-world-1.execute"
        ).execute("probe", {"kind": "intervention", "program": []})


# -- F1 episode-right-revocation -----------------------------------------------

def test_f1_right_revoked_after_normal_return(tmp_path, custody):
    rt = _runtime(tmp_path)
    rt.compose_adaptive_intelligence(custody=custody)
    spec, executor = _episode(12)
    rt.solve_task(spec, executor, seed=1)
    _assert_right_revoked(rt)


def test_f1_right_revoked_after_solver_exception(tmp_path, custody):
    rt = _runtime(tmp_path)
    rt.compose_adaptive_intelligence(custody=custody)

    class Boom:
        def execute(self, action, payload):
            raise RuntimeError("solver failure")

    spec, _ = _episode(13)
    with pytest.raises(RuntimeError, match="solver failure"):
        rt.solve_task(spec, Boom(), seed=1)
    _assert_right_revoked(rt)


def test_f1_right_revoked_after_cancellation(tmp_path, custody):
    rt = _runtime(tmp_path)
    rt.compose_adaptive_intelligence(custody=custody)

    class Cancelled(BaseException):
        """Cancellation-style BaseException: never swallowed by except Exception."""

    class Cancel:
        def execute(self, action, payload):
            raise Cancelled()

    spec, _ = _episode(14)
    with pytest.raises(Cancelled):
        rt.solve_task(spec, Cancel(), seed=1)
    _assert_right_revoked(rt)


# -- F2 component-evidence-binding ---------------------------------------------

def test_f2_persisted_stage_requires_verified_custody_write(tmp_path, custody):
    # Without custody there is no durable write, so no PERSISTED claim.
    bare = _runtime(tmp_path, name="nocustody")
    bare.compose_adaptive_intelligence()
    spec, executor = _episode(21)
    bare.solve_task(spec, executor, seed=2)
    component = EuclidRuntime.ADAPTIVE_COMPONENTS[0]
    assert bare.reachability.stage(component) is ReachabilityStage.FEEDBACK_CLOSED
    assert any(
        r.kind == "adaptive-knowledge-not-persisted" for r in bare.evidence.records
    )

    # With custody the write actually happens and is evidenced by digest.
    rt = _runtime(tmp_path, name="withcustody")
    rt.compose_adaptive_intelligence(custody=custody)
    spec, executor = _episode(22)
    rt.solve_task(spec, executor, seed=2)
    assert rt.reachability.stage(component) is ReachabilityStage.PERSISTED
    writes = [r for r in rt.evidence.records if r.kind == "adaptive-knowledge-persisted"]
    assert writes and writes[-1].payload["content_digest"]
    # The persisted bytes are durably readable from custody — the stage claim
    # is bound to an artefact, not to an in-memory intention.
    body = json.loads(custody.get(ADAPTIVE_RECORD).decode("utf-8"))
    assert body["knowledge"]["seal"]


# -- F3 fresh-process-replay ----------------------------------------------------

def test_f3_same_process_reload_is_not_restart_verified(tmp_path):
    first = EuclidRuntime.production(
        creator_id="creator-1", state_dir=tmp_path / "state", organism=False
    )
    checkpoint = tmp_path / "checkpoint.json"
    try:
        first.save(checkpoint)
    finally:
        first.close()
    # A same-process restore against a state dir that has never seen a fresh
    # interpreter must NOT claim RESTART_VERIFIED.
    restored = EuclidRuntime.restore(checkpoint, state_dir=tmp_path / "state2")
    try:
        stage = restored.reachability.stage("euclid.runtime")
        assert stage is None or stage < ReachabilityStage.RESTART_VERIFIED
        assert not any(r.kind == "custody-restart" for r in restored.evidence.records)
        readiness = restored.startup_report()["intelligence_readiness"]
        assert readiness["restart_verified"] is False
    finally:
        restored.close()


def test_f3_fresh_process_custody_restart_verified(tmp_path):
    state_dir = tmp_path / "state"
    first = EuclidRuntime.production(creator_id="creator-1", state_dir=state_dir)
    plane = EnterpriseCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    try:
        expected_head = first.evidence.head
        checkpoint = first.save_to_custody(plane)
    finally:
        first.close()
        plane.close()

    child = subprocess.run(
        [
            sys.executable,
            str(CUSTODY_CHILD),
            str(tmp_path / "custody"),
            checkpoint["record_id"],
            CUSTODY_KEY.hex(),
            str(state_dir),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert child.returncode == 0, child.stderr[-3000:]
    report = json.loads(child.stdout.strip().splitlines()[-1])
    assert report["restored_evidence_head"] == expected_head
    assert report["restart_stage"] == "RESTART_VERIFIED"
    assert report["readiness"]["restart_verified"] is True


# -- F4 organ-lifetime-identity -------------------------------------------------

def test_f4_recomposition_preserves_live_organ_identity(tmp_path, custody):
    rt = _runtime(tmp_path)
    rt.compose_adaptive_intelligence(custody=custody)
    spec, executor = _episode(31)
    rt.solve_task(spec, executor, seed=3)
    ids = [row["organ_id"] for row in rt.registry.report()]
    assert "task-world-1" in ids
    assert len(ids) == len(set(ids))

    # Recomposition: the counter must not rewind onto the live identity.
    rt.compose_adaptive_intelligence(custody=custody)
    spec, executor = _episode(32, family="symbolic-rewriting")
    rt.solve_task(spec, executor, seed=3)  # collision here without F4
    ids = [row["organ_id"] for row in rt.registry.report()]
    assert "task-world-2" in ids, "recomposition reissued a live organ id"
    assert "task-world-1" in ids, "recomposition retired a preserved identity"
    assert len(ids) == len(set(ids)), "duplicate organ ids after recomposition"


# -- F5 canonical-custody -------------------------------------------------------

def test_f5_adaptive_knowledge_is_creator_bound_custody_state(tmp_path, custody):
    rt = _runtime(tmp_path)
    rt.compose_adaptive_intelligence(custody=custody)
    spec, executor = _episode(41)
    rt.solve_task(spec, executor, seed=4)
    episodes = rt.adaptive.knowledge.episodes
    assert episodes > 0

    # No private JSON authority anywhere under state_dir.
    assert not (tmp_path / "state" / "adaptive_knowledge.json").exists()

    # Durable, sealed, creator-bound payload in canonical custody.
    body = json.loads(custody.get(ADAPTIVE_RECORD).decode("utf-8"))
    assert body["schema"] == "euclid.adaptive-knowledge/1"
    assert body["creator_id"] == "creator-1"
    assert body["knowledge"]["seal"]
    assert any(
        r.kind == "adaptive-knowledge-persisted" for r in rt.evidence.records
    )

    # Restart resumes the same knowledge from custody.
    resumed = _runtime(tmp_path)
    resumed.compose_adaptive_intelligence(custody=custody)
    assert resumed.adaptive.knowledge.episodes == episodes
    assert any(
        r.kind == "adaptive-knowledge-restored" for r in resumed.evidence.records
    )

    # Creator isolation: another creator reads its own (fresh) namespace only.
    other = _runtime(tmp_path, name="state-other", creator="creator-2")
    other.compose_adaptive_intelligence(custody=custody)
    assert other.adaptive.knowledge.episodes == 0
    assert any(
        r.kind == "adaptive-knowledge-fresh" for r in other.evidence.records
    )

    # Fail closed on a payload whose creator binding does not match.
    mismatched = json.dumps(
        {
            "schema": "euclid.adaptive-knowledge/1",
            "creator_id": "creator-1",
            "knowledge": body["knowledge"],
        },
        sort_keys=True,
    ).encode("utf-8")
    custody.put(mismatched, record_id="euclid-adaptive-knowledge-creator-3")
    forged = _runtime(tmp_path, name="state-forged", creator="creator-3")
    with pytest.raises(ValueError, match="creator binding mismatch"):
        forged.compose_adaptive_intelligence(custody=custody)


# -- F6 negative-transfer-detection ---------------------------------------------

def test_f6_mismatched_curriculum_detected_and_remediated(tmp_path, custody):
    rt = _runtime(tmp_path)
    rt.compose_adaptive_intelligence(custody=custody)
    learner = rt.adaptive.knowledge.strategies

    # Global prior: s-global is the favourite everywhere.
    for _ in range(40):
        learner.record_episode("class-a", "s-global", 0.95)
    # Mismatched curriculum: the favourite is reliably worse in class-b.
    reports = []
    for _ in range(4):
        reports.append(learner.record_episode("class-b", "s-global", 0.1))
        reports.append(learner.record_episode("class-b", "s-local", 0.8))

    detections = [r["negative_transfer"] for r in reports if "negative_transfer" in r]
    assert detections, "mismatched curriculum degradation went undetected"
    entry = detections[0]
    assert entry["class"] == "class-b"
    assert entry["imported"] == "s-global"
    assert entry["probability_better"] >= 0.95
    assert entry["better"] == "s-local"
    assert learner.negative_transfer, "detection left no durable ledger entry"

    # Auditable remediation: the decision cites measured class evidence and
    # routes around the harmful import instead of silently retaining it.
    learner.frozen = True
    choice = learner.select_strategy("class-b", ("s-global", "s-local"))
    assert choice.strategy_id == "s-local"
    assert "class episode" in choice.basis
    learner.frozen = False

    # The decision trail survives the process boundary through custody.
    spec, executor = _episode(51)
    rt.solve_task(spec, executor, seed=5)
    body = json.loads(custody.get(ADAPTIVE_RECORD).decode("utf-8"))
    assert body["knowledge"]["strategies"]["negative_transfer"]

    resumed = _runtime(tmp_path)
    resumed.compose_adaptive_intelligence(custody=custody)
    ledger = resumed.adaptive.knowledge.strategies.negative_transfer
    assert any(e["class"] == "class-b" for e in ledger)
    persisted_writes = [
        r for r in rt.evidence.records if r.kind == "adaptive-knowledge-persisted"
    ]
    assert persisted_writes, "audit trail was not written through custody"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

