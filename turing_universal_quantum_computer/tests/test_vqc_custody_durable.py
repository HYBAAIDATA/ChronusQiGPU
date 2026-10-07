"""Durable TURING custody — the readiness audit's restart evidence test.

Commit → close → fresh-process open → recover → replay.  Durable receipts
must carry a non-None ``durable_index`` and the replayed artefact must
verify from the on-disk THESEUS store, not from live objects.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from turing_universal_quantum_computer import Program
from turing_universal_quantum_computer.custody import (
    CustodyError,
    open_custody,
)
from turing_universal_quantum_computer.pipeline import VQCRequest, run_pipeline

CHILD = Path(__file__).resolve().with_name("turing_custody_restart_child.py")


def _bell() -> Program:
    return Program(2).then("h", 0).then("cx", 0, 1)


def test_pipeline_durable_custody_recovers_and_replays(tmp_path) -> None:
    request = VQCRequest(
        program=_bell(),
        custody=True,
        replay=True,
        custody_dir=str(tmp_path / "custody"),
    )
    report = run_pipeline(request)
    assert report.verdict == "PASS", report.to_json()

    custody_stage = next(s for s in report.stages if s.stage == "custody")
    assert custody_stage.state == "PASS"
    assert {r["kind"] for r in report.custody} == {
        "program",
        "result",
        "witness",
        "certificate",
    }
    for receipt in report.custody:
        assert receipt["durable_index"] is not None

    # Replay ran against a re-attached store, not the live adapter.
    replay_stage = next(s for s in report.stages if s.stage == "replay")
    assert replay_stage.state == "PASS"
    for replay in report.replay:
        assert replay["state"] == "PASS"
        assert replay["digest_verified"] is True
        assert replay["recovered"] is True

    # Durability is on disk, not in process state.
    assert (tmp_path / "custody" / "theseus_index.json").is_file()


def test_fresh_process_open_theseus_recovers_and_replays(tmp_path) -> None:
    custody_dir = tmp_path / "custody"
    custody = open_custody(durable_dir=str(custody_dir))
    receipt = custody.commit("program", _bell().to_dict())
    assert receipt.durable_index is not None
    del custody  # the committing adapter is gone; only the dir survives

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [os.fspath(Path(__file__).resolve().parent.parent), *sys.path]
    )
    proc = subprocess.run(
        [sys.executable, str(CHILD), str(custody_dir), receipt.uid],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert report["state"] == "PASS"
    assert report["uid"] == receipt.uid
    assert report["digest_verified"] is True
    assert report["theseus_verify"] is True
    assert report["recovered"] is True


def test_in_process_custody_stays_honest_about_scope() -> None:
    custody = open_custody()
    receipt = custody.commit("program", _bell().to_dict())
    assert receipt.durable_index is None
    assert custody.durable_dir is None
    with pytest.raises(CustodyError, match="durable_dir"):
        custody.reopen()
