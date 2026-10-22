"""Fail-closed contract for the canonical Virtual iGPU execution plane (software evidence)."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from chronus.mining_bridge import submit_via_virtual_igpu
from chronus.virtual_igpu.abi import AdapterKind, ExecutionPolicy, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import (
    AdapterUnavailable,
    CPUEmulatorAdapter,
    OpenCLUhdAdapter,
)
from chronus.virtual_igpu.client import ChronusClient, ChronusClientError
from chronus.virtual_igpu.evidence import BINDABLE_RECEIPT_FIELDS, EvidenceLedger, validate_receipt
from chronus.virtual_igpu.memory import VirtualMemoryPlane
from chronus.virtual_igpu.runtime import AdmissionDenied, RuntimeDaemon, RuntimeInvariantError
from chronus.virtual_igpu.wire import serve

HEADER = bytes(range(76)) + bytes(4)
EASY = "ff" * 32


def _daemon(tmp_path, adapters=None, **kw):
    return RuntimeDaemon(
        adapters=adapters or [CPUEmulatorAdapter()], store_dir=tmp_path / "rt", **kw
    )


def _probe(wid="w", **kw):
    return Workload(id=wid, kind=WorkloadKind.PROBE, **kw)


# --- unknown workload / policy / schema ------------------------------------------------------


@pytest.mark.parametrize("kind", ["sha256d_scna", "typo", "", "CUSTOMM", "SHA256D_SCAN "])
def test_unknown_workload_kind_is_rejected_not_custom(kind) -> None:
    with pytest.raises(ValueError, match="unsupported workload kind"):
        Workload(id="w", kind=kind)


def test_explicit_custom_is_still_allowed() -> None:
    assert Workload(id="w", kind="custom").kind is WorkloadKind.CUSTOM


@pytest.mark.parametrize(
    "payload, match",
    [
        ({"id": "w"}, "missing 'kind'"),
        ({"kind": "probe"}, "missing 'id'"),
        ({"id": "w", "kind": "probe", "abi_version": "virtual_igpu_v0"}, "ABI version"),
        ({"id": "w", "kind": "nonsense"}, "unsupported workload kind"),
        ({"id": "w", "kind": "probe", "execution_policy": "nonsense"}, "unsupported execution"),
        ({"id": "w", "kind": "probe", "delivery_mode": "cloud_instance"}, "delivery mode"),
    ],
)
def test_malformed_serialized_workload_is_rejected(payload, match) -> None:
    with pytest.raises(ValueError, match=match):
        Workload.from_dict(payload)
    with pytest.raises(ValueError, match="mapping"):
        Workload.from_dict("not-a-mapping")  # type: ignore[arg-type]


def test_tampered_workload_hash_is_rejected() -> None:
    good = Workload(id="w", kind=WorkloadKind.PROBE).as_dict()
    good["input"] = {"tampered": True}
    with pytest.raises(ValueError, match="content_hash"):
        Workload.from_dict(good)


@pytest.mark.parametrize("policy", ["", "Standalone_Software", "PREFERRED_ACCELERATOR", "x"])
def test_invalid_policy_strings_rejected(policy) -> None:
    with pytest.raises(ValueError, match="unsupported execution policy"):
        Workload(id="w", kind=WorkloadKind.PROBE, execution_policy=policy)


@pytest.mark.parametrize(
    "policy",
    [p.value for p in ExecutionPolicy if p.value.startswith(("standalone", "preferred"))],
)
def test_valid_policies_execute(tmp_path, policy) -> None:
    assert _daemon(tmp_path).submit(_probe(execution_policy=policy)).status == "ok"


# --- required adapter / device / fallback ---------------------------------------------------


def test_required_adapter_and_device_unavailable_fail_closed(tmp_path) -> None:
    d = _daemon(tmp_path)
    with pytest.raises(AdapterUnavailable, match="required adapter unavailable"):
        d.submit(_probe("a", execution_policy="required_adapter", required_adapter_id="cuda-0"))
    with pytest.raises(AdapterUnavailable, match="required device unavailable"):
        d.submit(_probe("b", execution_policy="required_device", required_device_id="gpu-9"))
    assert d.in_flight.get("default", 0) == 0


def test_fallback_disabled_fails_closed_and_enabled_records_provenance(tmp_path) -> None:
    d = _daemon(tmp_path)
    with pytest.raises(AdapterUnavailable, match="fallback is disabled"):
        d.submit(_probe("nf", allow_software_fallback=False))
    ok = d.submit(_probe("f"))
    assert ok.requested_policy == "preferred_accelerator"
    assert ok.actual_adapter_id == "cpu-emulator"
    assert ok.route_reason == "policy:preferred_accelerator:software_fallback"
    assert ok.receipt["requested_policy"] == "preferred_accelerator"
    assert ok.receipt["actual_backend"] == "cpu-emulator"


class _TensorOnlyAccelerator(CPUEmulatorAdapter):
    """Available physical-shaped adapter that cannot run a SHA256d scan."""

    id = "stub-accelerator"
    kind = AdapterKind.OPENCL

    def capabilities(self):
        return dataclasses.replace(
            super().capabilities(),
            adapter_id=self.id,
            kind=self.kind.value,
            operations=(WorkloadKind.TENSOR_OP.value,),
        )


class _UhdPresent(OpenCLUhdAdapter):
    """UHD adapter whose probe reports the device as present."""

    def probe(self):
        self.available = True
        return self._attestation(True, {"probe": "stub: device present"})


def _scan(wid, **kw):
    return Workload(
        id=wid,
        kind=WorkloadKind.SHA256D_SCAN,
        input={"header80_hex": HEADER.hex(), "target_hex": EASY, "nonces": [5, 6, 7]},
        **kw,
    )


def test_physical_adapter_that_cannot_run_the_kind_does_not_block_software_fallback(
    tmp_path,
) -> None:
    d = _daemon(tmp_path, adapters=[_TensorOnlyAccelerator(), CPUEmulatorAdapter()])
    ok = d.submit(_scan("sw"))
    assert ok.status == "ok"
    assert ok.actual_adapter_id == "cpu-emulator"
    assert ok.route_reason == "policy:preferred_accelerator:software_fallback"
    assert ok.output["hits"][0]["nonce"] == 5
    with pytest.raises(AdapterUnavailable, match="fallback is disabled"):
        d.submit(_scan("nf", allow_software_fallback=False))
    physical = d.submit(Workload(id="pr", kind=WorkloadKind.PROBE))
    assert physical.actual_adapter_id == "stub-accelerator"
    assert physical.route_reason == "policy:preferred_accelerator:physical"


def test_uhd_adapter_never_advertises_what_it_cannot_execute(tmp_path) -> None:
    uhd = _UhdPresent()
    uhd.probe()
    assert uhd.available
    assert uhd.capabilities().operations == ()
    for kind in (WorkloadKind.SHA256D_SCAN, WorkloadKind.TENSOR_OP, WorkloadKind.PROBE):
        assert not uhd.supports(kind)
    d = _daemon(tmp_path, adapters=[uhd, CPUEmulatorAdapter()])
    ok = d.submit(_scan("uhd-present"))
    assert ok.status == "ok"
    assert ok.actual_adapter_id == "cpu-emulator"
    assert ok.receipt["actual_backend"] == "cpu-emulator"
    assert ok.output["hits"][0]["nonce"] == 5


def test_default_store_root_is_absolute_so_a_later_chdir_cannot_break_the_ledger(
    tmp_path, monkeypatch
) -> None:
    first, other = tmp_path / "first", tmp_path / "other"
    first.mkdir()
    other.mkdir()
    monkeypatch.delenv("CHRONUS_VIGPU_STORE", raising=False)
    monkeypatch.chdir(first)
    d = RuntimeDaemon(adapters=[CPUEmulatorAdapter()])
    assert d.root.is_absolute()
    assert d.root == (first / ".chronus-virtual-igpu").resolve()
    monkeypatch.chdir(other)
    assert d.submit(_probe("after-chdir")).status == "ok"
    assert not (other / ".chronus-virtual-igpu").exists()


def test_daemon_denies_cross_tenant_retrieve_and_isolates_identical_bytes(tmp_path) -> None:
    d = _daemon(tmp_path)
    payload = {"data": "tenant-a secret"}
    stored = d.submit(Workload(id="s-a", kind=WorkloadKind.STORE, tenant="tenant-a", input=payload))
    assert stored.status == "ok" and stored.object_id
    own = d.submit(
        Workload(
            id="r-a",
            kind=WorkloadKind.RETRIEVE,
            tenant="tenant-a",
            input={"object_id": stored.object_id},
        )
    )
    assert own.status == "ok" and own.output["payload"] == payload
    with pytest.raises(PermissionError, match="not authori[sz]ed"):
        d.submit(
            Workload(
                id="r-b",
                kind=WorkloadKind.RETRIEVE,
                tenant="tenant-b",
                input={"object_id": stored.object_id},
            )
        )
    assert d.in_flight.get("tenant-b", 0) == 0
    other = d.submit(Workload(id="s-b", kind=WorkloadKind.STORE, tenant="tenant-b", input=payload))
    assert other.object_id != stored.object_id


# --- lying adapter / bridge verification -----------------------------------------------------


class _Liar(CPUEmulatorAdapter):
    def _sha256d_scan(self, workload, value, started):
        start = int(value.get("start_nonce", 0))
        return self._result(
            workload,
            {
                "hits": [{"nonce": start, "hash_hex": "00" * 32, "digest_int": 0}],
                "checked": 1,
                "start_nonce": start,
                "engine": "forged",
            },
            started,
        )


def test_bridge_rejects_lying_adapter(tmp_path, monkeypatch) -> None:
    import chronus.virtual_igpu.client as client_mod

    daemon = _daemon(tmp_path, [_Liar()])
    monkeypatch.setattr(client_mod, "get_embedded_daemon", lambda **_: daemon)
    # Two independent boundaries: the runtime's recompute verifier, then the host verifier.
    with pytest.raises(RuntimeError, match="verification_failed|candidate digest mismatch"):
        submit_via_virtual_igpu(
            {"windows": [{"start": 0, "count": 4}]},
            header80=HEADER,
            target_hex=EASY,
            execution_policy="standalone_software",
        )


def test_bridge_rejects_out_of_range_candidate(tmp_path, monkeypatch) -> None:
    import hashlib
    import chronus.virtual_igpu.client as client_mod

    class OutOfRange(CPUEmulatorAdapter):
        def _sha256d_scan(self, workload, value, started):
            nonce = 99
            digest = hashlib.sha256(
                hashlib.sha256(HEADER[:76] + nonce.to_bytes(4, "little")).digest()
            ).hexdigest()
            return self._result(
                workload,
                {"hits": [{"nonce": nonce, "hash_hex": digest}], "checked": 1},
                started,
            )

    daemon = _daemon(tmp_path, [OutOfRange()])
    monkeypatch.setattr(client_mod, "get_embedded_daemon", lambda **_: daemon)

    with pytest.raises(RuntimeError, match="verification_failed|outside the admitted range"):
        submit_via_virtual_igpu(
            {"windows": [{"start": 0, "count": 4}]},
            header80=HEADER,
            target_hex=EASY,
            execution_policy="standalone_software",
        )


# --- tenant isolation -----------------------------------------------------------------------


def test_cross_tenant_handles_are_isolated(tmp_path) -> None:
    mem = VirtualMemoryPlane(tmp_path / "m")
    a = mem.store({"x": 1}, tenant="A")
    b = mem.store({"x": 1}, tenant="B")
    assert a.object_id != b.object_id
    assert mem.retrieve(a.object_id, tenant="A") == {"x": 1}
    assert mem.retrieve(b.object_id, tenant="B") == {"x": 1}
    with pytest.raises(PermissionError):
        mem.retrieve(b.object_id, tenant="A")
    with pytest.raises(PermissionError):
        mem.retrieve(a.object_id, tenant="B")
    # Possession of the shared content identity never authorises access.
    with pytest.raises(Exception):
        mem.retrieve(a.content_id, tenant="B")


# --- evidence ledger corruption -------------------------------------------------------------


def _ledger_with_three(tmp_path):
    ledger = EvidenceLedger(tmp_path)
    for i in range(3):
        ledger.append(
            workload_id=f"w{i}",
            adapter_id="cpu-emulator",
            kind="probe",
            result_dict={"status": "ok", "n": i},
            receipt_dict={},
        )
    return tmp_path / "evidence_ledger.jsonl"


def test_ledger_rejects_every_corruption_class(tmp_path) -> None:
    path = _ledger_with_three(tmp_path)
    good = path.read_text().splitlines()
    assert len(EvidenceLedger(tmp_path).list_records()) == 3

    cases = {
        "truncated_entry": good[:2] + [good[2][: len(good[2]) // 2]],
        "malformed_json": good[:2] + ["{not json"],
        "missing_middle_entry": [good[0], good[2]],
        "reordered": [good[1], good[0], good[2]],
    }
    altered = json.loads(good[1])
    altered["chain_digest"] = "0" * 64
    cases["altered_digest"] = [good[0], json.dumps(altered), good[2]]
    for name, lines in cases.items():
        path.write_text("\n".join(lines) + "\n")
        with pytest.raises(ValueError, match="evidence"):
            EvidenceLedger(tmp_path)
        assert name


def test_ledger_holders_sharing_a_store_extend_the_on_disk_head(tmp_path) -> None:
    """A holder that loaded the ledger before another holder appended must
    chain from the on-disk head; chaining from its stale head forks the ledger."""
    first, second = EvidenceLedger(tmp_path), EvidenceLedger(tmp_path)
    for holder, wid in ((first, "a"), (second, "b"), (first, "c")):
        holder.append(workload_id=wid, adapter_id="cpu-emulator", kind="probe", result_dict={})
    records = EvidenceLedger(tmp_path).list_records()
    assert [r.workload_id for r in records] == ["a", "b", "c"]
    assert [r.chain_prev for r in records[1:]] == [r.chain_digest for r in records[:-1]]


_LEDGER_WRITER = """
import sys
from chronus.virtual_igpu.evidence import EvidenceLedger
root, tag, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
ledger = EvidenceLedger(root)
for i in range(count):
    ledger.append(workload_id=f"{tag}-{i}", adapter_id="cpu-emulator", kind="probe",
                  result_dict={"i": i})
"""


def test_concurrent_writer_processes_never_fork_the_ledger(tmp_path) -> None:
    repo = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(repo), os.environ.get("PYTHONPATH")]))}
    writers = [
        subprocess.Popen(
            [sys.executable, "-c", _LEDGER_WRITER, str(tmp_path / "store"), f"p{n}", "25"],
            cwd=str(tmp_path),
            env=env,
            stderr=subprocess.PIPE,
            text=True,
        )
        for n in range(4)
    ]
    errors = [w.communicate(timeout=180)[1] for w in writers]
    assert [w.returncode for w in writers] == [0, 0, 0, 0], errors
    records = EvidenceLedger(tmp_path / "store").list_records()
    assert len(records) == 100
    assert sorted(r.workload_id for r in records) == sorted(
        f"p{n}-{i}" for n in range(4) for i in range(25)
    )


# --- receipt identity binding ---------------------------------------------------------------


def test_receipt_binds_every_identity_field(tmp_path) -> None:
    result = _daemon(tmp_path).submit(_probe("rb"))
    receipt = dict(result.receipt)
    bindable = {k: receipt[k] for k in BINDABLE_RECEIPT_FIELDS if k in receipt}
    assert set(bindable) >= {
        "protocol_version",
        "package_version",
        "runtime_identity",
        "build_identity",
        "kernel_identity",
        "workload_id",
        "attempt_id",
        "requested_policy",
        "actual_backend",
        "actual_device",
        "input_digest",
        "output_digest",
        "verified_work_count",
        "delivery_mode",
    }
    assert validate_receipt(receipt, expect=bindable)["ok"] is True
    for name, value in bindable.items():
        wrong = (value + 1) if isinstance(value, int) else f"{value}-mutated"
        report = validate_receipt(receipt, expect={**bindable, name: wrong})
        assert report["ok"] is False, name
        assert f"{name} mismatch" in report["errors"]
        stripped = {k: v for k, v in receipt.items() if k != name}
        assert validate_receipt(stripped, expect={name: value})["ok"] is False
    with pytest.raises(ValueError, match="unsupported receipt binding"):
        validate_receipt(receipt, expect={"not_a_field": 1})


# --- remote / sidecar delivery ----------------------------------------------------------------


def test_delivery_contract_is_explicit() -> None:
    with pytest.raises(ChronusClientError, match="endpoint cannot be supplied"):
        ChronusClient(delivery_mode="embedded", endpoint="http://127.0.0.1:1")
    with pytest.raises(ChronusClientError, match="requires endpoint"):
        ChronusClient(delivery_mode="remote_service")
    with pytest.raises(ChronusClientError, match="unsupported delivery mode"):
        ChronusClient(delivery_mode="cloud_instance")
    with pytest.raises(ChronusClientError, match="requires an authentication token"):
        ChronusClient(delivery_mode="remote_service", endpoint="https://chronus.example.com")
    with pytest.raises(ChronusClientError, match="loopback"):
        ChronusClient(delivery_mode="local_sidecar", endpoint="http://10.0.0.5:9")
    with pytest.raises(ValueError):
        submit_via_virtual_igpu({}, delivery_mode="cloud_instance")
    with pytest.raises(ChronusClientError, match="endpoint cannot be supplied"):
        submit_via_virtual_igpu({}, endpoint="http://127.0.0.1:9")


def test_remote_delivery_takes_its_endpoint_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("CHRONUS_VIGPU_ENDPOINT", "http://127.0.0.1:8765")
    assert ChronusClient(delivery_mode="remote_service").endpoint == "http://127.0.0.1:8765"
    assert ChronusClient(delivery_mode="local_sidecar").endpoint == "http://127.0.0.1:8765"


def _serve(tmp_path, **kw):
    server = serve("127.0.0.1", 0, store=str(tmp_path / "srv"), **kw)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_local_sidecar_roundtrip_records_mode(tmp_path) -> None:
    server, url = _serve(tmp_path)
    try:
        client = ChronusClient(delivery_mode="local_sidecar", endpoint=url)
        result = client.submit(_probe("sc"))
        assert result.status == "ok"
        assert result.delivery_mode == "local_sidecar"
        assert result.receipt["delivery_mode"] == "local_sidecar"
    finally:
        server.shutdown()


def test_remote_unavailable_never_falls_back_to_local() -> None:
    client = ChronusClient(
        delivery_mode="remote_service", endpoint="http://127.0.0.1:9", timeout_s=1.0
    )
    with pytest.raises(ChronusClientError, match="no local fallback"):
        client.submit(_probe("down"))


def test_production_service_requires_token_tls_ack_and_hides_errors(tmp_path) -> None:
    with pytest.raises(ValueError, match="transport security"):
        serve("127.0.0.1", 0, store=str(tmp_path / "a"), production=True, auth_token="t")
    with pytest.raises(ValueError, match="authentication token"):
        serve(
            "127.0.0.1",
            0,
            store=str(tmp_path / "b"),
            production=True,
            tls_terminated_externally=True,
        )
    server, url = _serve(
        tmp_path, production=True, tls_terminated_externally=True, auth_token="s3cret"
    )
    try:
        anonymous = ChronusClient(delivery_mode="local_sidecar", endpoint=url)
        with pytest.raises(ChronusClientError, match="HTTP 401"):
            anonymous.submit(_probe("anon"))
        bad = ChronusClient(delivery_mode="local_sidecar", endpoint=url, auth_token="wrong")
        with pytest.raises(ChronusClientError, match="HTTP 401"):
            bad.submit(_probe("bad"))
        req = urllib.request.Request(
            url + "/submit",
            data=json.dumps({"id": "w", "kind": "nonsense"}).encode(),
            headers={"Authorization": "Bearer s3cret", "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req)
        body = json.loads(err.value.read())
        assert body == {"error": "ValueError"}  # no detail / traceback leakage
        good = ChronusClient(delivery_mode="local_sidecar", endpoint=url, auth_token="s3cret")
        assert good.submit(_probe("ok")).status == "ok"
    finally:
        server.shutdown()


def test_authorizer_hook_is_enforced(tmp_path) -> None:
    seen = []

    def authorizer(method, path, headers):
        seen.append((method, path))
        return path != "/submit"

    server, url = _serve(tmp_path, authorizer=authorizer)
    try:
        client = ChronusClient(delivery_mode="local_sidecar", endpoint=url)
        with pytest.raises(ChronusClientError, match="HTTP 401"):
            client.submit(_probe("denied"))
        assert ("POST", "/submit") in seen
    finally:
        server.shutdown()


def test_admission_policy_hook_denies_before_execution(tmp_path) -> None:
    d = _daemon(tmp_path, admission_policy=lambda w: w.tenant != "blocked")
    assert d.submit(_probe("ok", tenant="fine")).status == "ok"
    with pytest.raises(AdmissionDenied):
        d.submit(_probe("no", tenant="blocked"))
    assert d.in_flight.get("blocked", 0) == 0


# --- deadline / reservation lifecycle ---------------------------------------------------------


class _Slow(CPUEmulatorAdapter):
    gate = threading.Event()

    def execute(self, workload):
        self.gate.wait(5)
        return super().execute(workload)


def test_reservation_is_held_until_timed_out_worker_terminates(tmp_path) -> None:
    _Slow.gate = threading.Event()
    d = _daemon(tmp_path, [_Slow()], max_per_tenant=1)
    result = d.submit(_probe("slow", tenant="t", deadline_ms=50))
    assert result.status == "timeout"
    assert result.output["execution_state"] == "TIMED_OUT_BUT_EXECUTION_DRAINING"
    # The worker is still executing: its reservation must still be held.
    assert d.in_flight["t"] == 1
    assert d.health()["draining"] == ["slow"]
    with pytest.raises(RuntimeInvariantError, match="oversubscribed"):
        d.submit(_probe("second", tenant="t"))
    _Slow.gate.set()
    deadline = time.time() + 5
    while d.in_flight.get("t", 0) and time.time() < deadline:
        time.sleep(0.01)
    assert d.in_flight.get("t", 0) == 0
    assert d.health()["draining"] == []
    assert d.submit(_probe("third", tenant="t")).status == "ok"


def test_fast_workload_with_deadline_releases_immediately(tmp_path) -> None:
    d = _daemon(tmp_path)
    assert d.submit(_probe("quick", tenant="t", deadline_ms=5000)).status == "ok"
    assert d.in_flight["t"] == 0
    assert d.health()["draining"] == []


# --- control-plane verifier understands explicit ordered nonce batches ------------------------


def test_runtime_verifier_checks_explicit_nonce_batches(tmp_path) -> None:
    import hashlib

    daemon = _daemon(tmp_path)
    nonces = [41, 7, 99]
    result = daemon.submit(
        Workload(
            id="explicit-ok",
            kind=WorkloadKind.SHA256D_SCAN,
            execution_policy="standalone_software",
            input={"header80_hex": HEADER.hex(), "target_hex": EASY, "nonces": nonces},
        )
    )
    assert result.status == "ok"
    assert result.receipt["verification"]["verdict"] == "match"
    assert result.output["hits"][0]["nonce"] == 41  # first in submitted order, not smallest
    digest = hashlib.sha256(hashlib.sha256(HEADER[:76] + (41).to_bytes(4, "little")).digest())
    assert result.output["hits"][0]["hash_hex"] == digest.hexdigest()


def test_runtime_verifier_rejects_wrong_probe_order(tmp_path) -> None:
    class Reordering(CPUEmulatorAdapter):
        def _sha256d_scan(self, workload, value, started):
            reordered = dict(value, nonces=sorted(value["nonces"]))
            return super()._sha256d_scan(workload, reordered, started)

    daemon = _daemon(tmp_path, [Reordering()])
    result = daemon.submit(
        Workload(
            id="explicit-reordered",
            kind=WorkloadKind.SHA256D_SCAN,
            execution_policy="standalone_software",
            input={"header80_hex": HEADER.hex(), "target_hex": EASY, "nonces": [41, 7, 99]},
        )
    )
    assert result.status == "verification_failed"
