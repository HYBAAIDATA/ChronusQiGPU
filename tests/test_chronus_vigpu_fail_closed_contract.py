"""Fail-closed contract for the canonical Virtual iGPU execution plane (software evidence)."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from chronus.mining_bridge import submit_via_virtual_igpu
from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import AdapterUnavailable, CPUEmulatorAdapter
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
    # The daemon's independent-recompute gate (verifier.py) demotes the lie
    # to status="verification_failed" before the bridge's own host-side
    # digest check ("candidate rejected") ever runs — either rejection path
    # satisfies the fail-closed contract.
    with pytest.raises(RuntimeError, match="verification_failed|candidate rejected"):
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
    # Daemon-side recompute rejects as verification_failed before the
    # bridge's own range check runs — either rejection satisfies the gate.
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
