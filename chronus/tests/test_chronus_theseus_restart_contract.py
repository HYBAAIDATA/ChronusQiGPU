"""THESEUS custody for verified CHRONUS execution, including fresh-process recovery."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import CustodyError, RuntimeDaemon

KEY = bytes(range(32))
REPO = Path(__file__).resolve().parents[2]
HEADER = bytes(range(76)) + bytes(4)

CHILD = """
import hashlib, json, sys
from hyba_db.theseus_custody import TheseusFileCustody
root, tenant, record_id, key_hex, digest = sys.argv[1:6]
custody = TheseusFileCustody(root=root, hmac_key=bytes.fromhex(key_hex))
assert custody.verify(tenant, record_id), "custody record did not authenticate after restart"
record = custody.open_tenant(tenant).get_record(record_id)
assert record.producer == "chronus" and record.kind == "vigpu_execution_evidence"
assert hashlib.sha256(record.payload).hexdigest() == digest, "payload digest mismatch"
body = json.loads(record.payload)
print(json.dumps({"status": body["status"], "checked": body["output"]["checked"],
                  "state": record.evidence_state}))
custody.close()
"""


def _custody(root: Path):
    from hyba_db.theseus_custody import TheseusFileCustody

    return TheseusFileCustody(root=root, hmac_key=KEY)


def _scan(wid: str, **kw) -> Workload:
    return Workload(
        id=wid,
        kind=WorkloadKind.SHA256D_SCAN,
        tenant="mining",
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        constraints={"custody": "required"},
        input={
            "header80_hex": HEADER.hex(),
            "target_hex": "ff" * 32,
            "start_nonce": 0,
            "count": 4,
        },
        **kw,
    )


def test_verified_result_is_committed_then_recovered_by_a_new_process(tmp_path) -> None:
    custody_root = tmp_path / "custody"
    custody = _custody(custody_root)
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "rt", custody=custody
    )
    result = daemon.submit(_scan("custodied"))
    assert result.status == "ok"
    info = result.metrics["custody"]
    assert info["authority"] == "theseus" and info["state"] == "committed"
    evidence_path = tmp_path / "rt" / "evidence" / f"{result.evidence_digest}.json"
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == result.evidence_digest
    custody.close()
    del daemon, custody  # process A drops every live handle

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            CHILD,
            str(custody_root),
            "mining",
            info["record_id"],
            KEY.hex(),
            result.evidence_digest,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        check=False,
        env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    assert completed.returncode == 0, completed.stderr
    recovered = json.loads(completed.stdout.strip().splitlines()[-1])
    assert recovered == {"status": "ok", "checked": 1, "state": "PASS"}


def test_required_custody_without_custody_fails_closed(tmp_path) -> None:
    daemon = RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "rt")
    with pytest.raises(CustodyError, match="no THESEUS custody"):
        daemon.submit(_scan("nocustody"))
    assert daemon.poll("nocustody") is None
    assert daemon.in_flight.get("mining", 0) == 0


def test_custody_failure_is_not_swallowed_and_withholds_the_result(tmp_path) -> None:
    class Broken:
        def put_record(self, tenant, record):
            raise OSError("disk full")

        def verify(self, tenant, record_id):
            return True

    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "rt", custody=Broken()
    )
    with pytest.raises(CustodyError, match="commit failed: disk full"):
        daemon.submit(_scan("brokencustody"))
    assert daemon.poll("brokencustody") is None


def test_unverifiable_commit_fails_closed(tmp_path) -> None:
    class Lying:
        def put_record(self, tenant, record):
            return "rid"

        def verify(self, tenant, record_id):
            return False

    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "rt", custody=Lying()
    )
    with pytest.raises(CustodyError, match="did not verify"):
        daemon.submit(_scan("lyingcustody"))


def test_workloads_without_custody_requirement_do_not_touch_it(tmp_path) -> None:
    class Exploding:
        def put_record(self, *a, **k):
            raise AssertionError("custody must not be called")

    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "rt", custody=Exploding()
    )
    result = daemon.submit(Workload(id="plain", kind=WorkloadKind.PROBE))
    assert result.status == "ok" and "custody" not in result.metrics
