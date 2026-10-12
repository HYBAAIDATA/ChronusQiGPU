"""Executable contract test for ``chronus.first-workload/1``.

Runs the real executor end-to-end (submit → verify → ledger → custody →
replay) and pins the declared outcome. A regression anywhere in the
pipeline fails here, not silently in a doc.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "chronus" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from chronus_first_workload import (  # noqa: E402
    EXPECTED,
    WORKLOAD_ID,
    run_workload,
)


@pytest.fixture(scope="module")
def verdict(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return run_workload(tmp_path_factory.mktemp("fw1"))


def test_contract_declared(verdict: dict) -> None:
    assert verdict["schema"] == "chronus.first-workload-verdict/1"
    assert verdict["workload_id"] == WORKLOAD_ID
    assert "delegated" in verdict["owner_approval"]
    assert len(verdict["git_head"]) == 40


def test_every_stage_passes(verdict: dict) -> None:
    assert verdict["verdict"] == "pass"
    assert all(s["verdict"] == "pass" for s in verdict["stages"].values())


def test_genesis_hit_pinned(verdict: dict) -> None:
    stage = verdict["stages"]["submit_execute"]
    assert stage["hit_nonce"] == EXPECTED["hit_nonce"] == 2083236893
    assert stage["checked"] == EXPECTED["checked"] == 257


def test_verification_recomputed_and_matched(verdict: dict) -> None:
    stage = verdict["stages"]["independent_verification"]
    assert stage["recomputed"] is True
    assert stage["verdict"] == "pass"
    assert "sha256d_scan" in stage["verifier"]


def test_replay_digest_identical(verdict: dict) -> None:
    stage = verdict["stages"]["replay"]
    assert stage["output_identical"] is True
    assert stage["input_digest"] == stage["replayed_input_digest"]
    assert stage["chain_continued"] is True
    assert stage["ledger_records"] >= 2


# --- regression: slashed / unsafe workload ids must not break artifact +
# custody paths (found by this contract run on Windows) --------------------


def test_artifact_store_handles_slashed_workload_id(tmp_path) -> None:
    from chronus.virtual_igpu.memory import VirtualMemoryPlane

    mem = VirtualMemoryPlane(tmp_path / "mem")
    wid = "chronus.first-workload/1"
    mem.store_artifact(tenant="t", workload_id=wid, artifact={"ok": True})
    assert mem.retrieve("t", wid) == {"ok": True}


def test_artifact_id_cannot_escape_tenant_dir(tmp_path) -> None:
    from chronus.virtual_igpu.memory import VirtualMemoryPlane

    mem = VirtualMemoryPlane(tmp_path / "mem")
    mem.store_artifact(tenant="t", workload_id="../evil", artifact={"x": 1})
    tenant_dir = tmp_path / "mem" / "artifacts" / "t"
    written = list(tenant_dir.iterdir())
    assert len(written) == 1 and written[0].parent == tenant_dir
    assert not (tmp_path / "mem" / "artifacts" / "evil.json").exists()


def test_custody_commit_handles_slashed_workload_id(tmp_path) -> None:
    from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
    from chronus.virtual_igpu.runtime import RuntimeDaemon
    from hyba_db.theseus_custody import TheseusFileCustody

    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=b"k" * 32)
    daemon = RuntimeDaemon(store_dir=tmp_path / "vigpu", custody=custody)
    result = daemon.submit(
        Workload(
            id="chronus.first-workload/1",
            kind=WorkloadKind.LUCAS_TRANSFORM,
            tenant="t",
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"n": 10},
            constraints={"custody": "required"},
        )
    )
    assert result.status == "ok"
    assert result.metrics["custody"]["state"] == "committed"
    assert custody.verify("t", result.metrics["custody"]["record_id"])
