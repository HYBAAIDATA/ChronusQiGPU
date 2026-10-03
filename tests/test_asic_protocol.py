"""ASIC wire-protocol contract: the endpoint must receive the real header.

A dispatch that never carries the block header leaves the remote channel
hashing nothing — a returned share could verify, but an exhausted window
would prove nothing. These tests drive the real JSON-lines socket
protocol against a local bridge stub: the bridge's share is computed
FROM THE RECEIVED ``header_prefix_hex`` — exactly the work commitment
the wire must carry — so a missing or wrong binding fails the host
re-verification boundary end to end.
"""

import json
import socketserver
import sys
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from hyba.hybrid.asic_solver import ASICSolver
from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
from hyba.hybrid.gpu_solver import GPUSolver
from hyba.hybrid.nonce_scheduler import (
    ASICNotPresent,
    AttestationRegistry,
    NonceWindow,
    double_sha256,
    verify_share,
)
from hyba.hybrid.super_asic import AsicHasherAdapter


class _BridgeHandler(socketserver.StreamRequestHandler):
    """A stratum-to-ASIC bridge stub on the real JSON-lines wire.

    Replies to ``capability`` with a sha256d_scan advertisement; on
    ``dispatch`` it records the request and grinds the window over the
    header prefix THE MESSAGE CARRIED (or a deliberate override for the
    wrong-header negative test) — the bridge cannot win by lying, and
    the fixture cannot answer for a header it was never sent.
    """

    def handle(self) -> None:
        while True:
            try:
                line = self.rfile.readline()
            except (ConnectionResetError, OSError):
                return
            if not line:
                return
            try:
                msg = json.loads(line.decode("utf-8", "replace"))
            except Exception:
                return
            if msg.get("cmd") == "capability":
                self.wfile.write(
                    json.dumps(
                        {
                            "device_id": "asic-bridge-stub",
                            "kernels": ["sha256d_scan"],
                            "measured_hashes_per_sec": 9.0e9,
                            "protocol_version": "stub-v2",
                        }
                    ).encode()
                    + b"\n"
                )
                self.wfile.flush()
            elif msg.get("cmd") == "dispatch":
                self.server.received.append(msg)
                if getattr(self.server, "drop_dispatch", False):
                    return  # hang up mid-window: a channel failure, not a reply
                self.wfile.write(json.dumps(self._grind(msg)).encode() + b"\n")
                self.wfile.flush()

    def _grind(self, msg: dict) -> dict:
        window = msg["window"]
        prefix_hex = msg.get("header_prefix_hex")
        override = self.server.header_override
        prefix = (
            override if override is not None else (bytes.fromhex(prefix_hex) if prefix_hex else b"")
        )
        if len(prefix) != 76:
            return {"type": "exhausted", "nonces_tried": 0}
        target = bytes.fromhex(window["target_hex"])
        base, span = int(window["base_nonce"]), int(window["span"])
        for nonce in range(base, base + span):
            digest = double_sha256(prefix + nonce.to_bytes(4, "little"))
            if digest[::-1] <= target:
                return {
                    "type": "share",
                    "nonce": nonce,
                    "digest": digest.hex(),
                    "nonces_tried": nonce - base + 1,
                }
        if self.server.short_exhaust is not None:
            return {"type": "exhausted", "nonces_tried": self.server.short_exhaust}
        return {"type": "exhausted", "nonces_tried": span}


class _Bridge(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, header_override=None, drop_dispatch=False, short_exhaust=None):
        super().__init__(("127.0.0.1", 0), _BridgeHandler)
        self.received = []
        self.header_override = header_override
        self.drop_dispatch = drop_dispatch
        # When set, an exhausted window declares this many nonces instead of the
        # assigned span, simulating a channel that stopped short and tried to
        # claim full coverage.
        self.short_exhaust = short_exhaust
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    @property
    def endpoint(self) -> str:
        return f"{self.server_address[0]}:{self.server_address[1]}"


@pytest.fixture
def bridge():
    server = _Bridge()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _clean_asic_env(monkeypatch):
    for var in (
        "HYBRID_ASIC_ENDPOINT",
        "HYBRID_ASIC_SERIAL",
        "HYBRID_ASIC_PCIE",
        "MLA1517_REMOTE_GPU_ENDPOINT",
        "HYBA_REMOTE_OPENCL_ENDPOINTS",
    ):
        monkeypatch.delenv(var, raising=False)
    AttestationRegistry.reset()
    yield
    AttestationRegistry.reset()


def _window(job_id: str, base: int, span: int, target: bytes) -> NonceWindow:
    return NonceWindow(
        job_id=job_id,
        session_epoch=0,
        job_epoch=0,
        base_nonce=base,
        span=span,
        target=target,
    )


def test_dispatch_sends_bound_header_and_share_verifies(bridge):
    """The endpoint receives the exact requested header; its share proves it."""
    solver = ASICSolver(endpoint=bridge.endpoint)
    header = bytes(range(80))
    target = b"\xff" * 32  # first nonce always meets it
    solver.prepare("j-bind", header)
    handle = solver.dispatch(_window("j-bind", base=0, span=16, target=target))
    share = solver.poll(handle)
    assert share is not None
    sent = bridge.received[-1]
    assert sent["header_prefix_hex"] == header[:76].hex()
    # The share was ground over the received prefix — host verify agrees.
    assert verify_share(share, header[:76], target)


def test_dispatch_without_prepare_raises(bridge):
    """A supported channel still refuses a window with no bound header."""
    solver = ASICSolver(endpoint=bridge.endpoint)
    assert solver.capability().supported is True
    with pytest.raises(ASICNotPresent, match="no bound header"):
        solver.dispatch(_window("j-unbound", base=0, span=8, target=b"\xff" * 32))


def test_prepare_rejects_wrong_sized_header(bridge):
    solver = ASICSolver(endpoint=bridge.endpoint)
    with pytest.raises(ValueError):
        solver.prepare("j", bytes(79))


def test_wrong_header_share_fails_host_verification():
    """An endpoint hashing the wrong header cannot produce a valid share."""
    server = _Bridge(header_override=bytes(76))  # hashes zeros, not the job
    try:
        solver = ASICSolver(endpoint=server.endpoint)
        from hyba.hybrid.super_asic import AsicHasherAdapter

        adapter = AsicHasherAdapter(solver)
        with pytest.raises(RuntimeError, match="failing host re-verification"):
            adapter.grind_target_range(bytes(range(80)), b"\xff" * 32, 0, 16)
    finally:
        server.shutdown()
        server.server_close()


def test_exhausted_window_reports_full_span(bridge):
    """An exhausted ASIC window contributes its whole span to accounting."""
    solver = ASICSolver(endpoint=bridge.endpoint)
    solver.prepare("j-ex", bytes(range(80)))
    window = _window("j-ex", base=2048, span=512, target=b"\x00" * 32)
    handle = solver.dispatch(window)
    while solver.poll(handle) is None and not solver.is_done(handle):
        pass
    assert solver.is_done(handle)
    assert solver.hashed_count(handle) == 512
    kinds = {r["kind"] for r in AttestationRegistry.get().snapshot()}
    assert "exhausted" in kinds


def test_short_exhausted_declaration_is_not_promoted_to_full_coverage():
    """An exhausted declaration below the assigned span stays partial.

    The channel claims exhaustion but reports fewer nonces than the window it was
    given. Recording that as full coverage would inflate total_nonces_tried and
    fabricate hashrate, so the count is kept true and the event is flagged. The
    adapter must agree with the solver rather than assert the assigned count.

    Both halves share ONE wire stub: this module's other tests are timing
    sensitive and each extra server thread adds load across the whole file.
    """
    server = _Bridge(short_exhaust=7)
    try:
        solver = ASICSolver(endpoint=server.endpoint)
        solver.prepare("j-short", bytes(range(80)))
        window = _window("j-short", base=2048, span=512, target=b"\x00" * 32)
        handle = solver.dispatch(window)
        while solver.poll(handle) is None and not solver.is_done(handle):
            pass
        assert solver.is_done(handle)
        # True executed count, not the 512 we assigned.
        assert solver.hashed_count(handle) == 7
        records = [
            r for r in AttestationRegistry.get().snapshot() if r["kind"].startswith("exhausted")
        ]
        assert [r["kind"] for r in records] == ["exhausted_partial"]
        assert records[0]["reason"] == "window_exhausted_below_span"
        assert records[0]["nonces_tried"] == 7

        # The adapter must surface the channel's true count (7), not `count` (512).
        adapter = AsicHasherAdapter(ASICSolver(endpoint=server.endpoint))
        nonce, digest, executed = adapter._grind_window(bytes(range(80)), b"\x00" * 32, 2048, 512)
        assert nonce is None and digest is None
        assert executed == 7
    finally:
        server.shutdown()
        server.server_close()


def test_share_probe_index_is_contiguous_depth(bridge):
    """probe_index = the share's position in the contiguous traversal."""
    solver = ASICSolver(endpoint=bridge.endpoint)
    header = bytes(range(80))
    solver.prepare("j-probe", header)
    # Find a depth>1 share: tight-but-loose target that wins mid-window.
    prefix = header[:76]
    winner = None
    for nonce in range(4096, 4096 + 256):
        digest = double_sha256(prefix + nonce.to_bytes(4, "little"))
        if digest[::-1] <= b"\xff" * 32:  # guaranteed; first nonce wins
            winner = nonce
            break
    handle = solver.dispatch(_window("j-probe", base=4096, span=256, target=b"\xff" * 32))
    share = solver.poll(handle)
    assert share is not None
    assert share.nonce == winner
    assert share.probe_index == winner - 4096 + 1


def test_mixed_asic_and_cpu_job_reports_exact_sum(bridge):
    """hybrid job: exhausted ASIC windows + CPU windows sum exactly."""
    solver = ASICSolver(endpoint=bridge.endpoint)
    gpu = GPUSolver(backend="cpu")
    coord = HybridCoordinator(gpu, solver)
    assert coord.mode == "hybrid"
    job = StratumJob(
        job_id="j-mixed",
        header80=bytes(range(80)),
        target=b"\x00" * 32,  # impossible: every window exhausts
        nonce_space=512,
    )
    result = coord.run_job(job)
    assert result.share is None
    # Every partitioned window fully ground: CPU span + ASIC span = job.
    assert result.total_nonces_tried == job.nonce_space
    layers = {s.layer for s in result.layer_samples}
    assert {"asic", "cpu"} <= layers


def test_serial_responsive_but_not_dispatch_capable(monkeypatch):
    """A serial device that answers the probe is still unsupported —
    `supported` means dispatch-capable, and no serial dispatch exists."""
    reply = (
        json.dumps(
            {
                "device_id": "asic-serial-stub",
                "measured_hashes_per_sec": 4.5e9,
                "serial": "STUB-9000",
            }
        ).encode()
        + b"\n"
    )

    class _FakeSerial:
        def __init__(self, port, baudrate, timeout):
            self.port = port

        def write(self, payload):
            self._written = payload

        def readline(self):
            return reply

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    fake_serial = types.SimpleNamespace(Serial=_FakeSerial)
    monkeypatch.setitem(sys.modules, "serial", fake_serial)
    solver = ASICSolver(serial_port="COM9")
    cap = solver.capability()
    assert cap.supported is False
    assert "dispatch" in cap.reason_if_unsupported
    # Presence evidence is preserved, not erased.
    serial_result = next(
        r for r in cap.detail["channel_results"] if r["detail"].get("channel") == "serial"
    )
    assert serial_result["detail"]["responsive"] is True
    assert serial_result["detail"]["serial"] == "STUB-9000"
    # And the lane cannot be dispatched to.
    solver.prepare("j-ser", bytes(range(80)))
    with pytest.raises(ASICNotPresent):
        solver.dispatch(_window("j-ser", 0, 8, b"\xff" * 32))


def test_remote_measure_failure_is_unsupported(monkeypatch):
    """A remote that advertises sha256d but errors on the probe grind
    reports unsupported — the measurement must not be softened to 0."""
    from hyba.hybrid.remote_solver import RemoteScheduler

    class _BrokenHasher:
        k_range = object()
        k_m32 = object()
        device = "remote-broken-stub"
        backend = "remote_opencl"
        fleet_size = 1
        last_execution_backend = None
        last_measured_ns = None

        def grind_target_range(self, *a, **k):
            raise RuntimeError("connection refused: agent down")

    import mining.remote_hasher

    monkeypatch.setattr(
        mining.remote_hasher,
        "hasher_for_env",
        lambda timeout=5.0: _BrokenHasher(),
    )
    scheduler = RemoteScheduler()
    cap = scheduler.capability()
    assert cap.supported is False
    assert "probe grind failed" in cap.reason_if_unsupported
    assert "connection refused" in cap.reason_if_unsupported
    with pytest.raises(Exception):
        scheduler.dispatch(_window("j-r", 0, 8, b"\xff" * 32))


def test_super_asic_configured_but_broken_remote_records_gap(monkeypatch):
    """A configured remote that fails to bind leaves visible evidence —
    it does not silently disappear into a cpu-only composition."""
    from hyba.hybrid.super_asic import SuperAsicHasher

    monkeypatch.setenv("HYBA_REMOTE_OPENCL_ENDPOINTS", "127.0.0.1:1")
    hasher = SuperAsicHasher.bind(remote_timeout=0.5)
    remote_entries = [e for e in hasher.bind_report if e["substrate"] == "remote"]
    assert remote_entries and remote_entries[0]["joined"] is False
    assert remote_entries[0]["reason"]
    gaps = [
        r
        for r in AttestationRegistry.get().snapshot()
        if r["kind"] == "gap" and r["reason"].startswith("super_asic_remote_excluded")
    ]
    assert gaps, "excluded remote member left no attestation gap"


def test_super_asic_unconfigured_remote_is_absent_not_broken():
    """No remote endpoints configured: plain absence, no defect gap."""
    from hyba.hybrid.super_asic import SuperAsicHasher

    hasher = SuperAsicHasher.bind()
    remote_entries = [e for e in hasher.bind_report if e["substrate"] == "remote"]
    assert remote_entries[0]["joined"] is False
    assert remote_entries[0]["reason"] == "no remote endpoints configured"
    excluded = [
        r
        for r in AttestationRegistry.get().snapshot()
        if r["kind"] == "gap" and r["reason"].startswith("super_asic_remote_excluded")
    ]
    assert not excluded


def test_adapter_grind_binds_job_header(bridge):
    """The registry adapter prepares the job before it dispatches."""
    from hyba.hybrid.super_asic import AsicHasherAdapter

    solver = ASICSolver(endpoint=bridge.endpoint)
    adapter = AsicHasherAdapter(solver)
    header = bytes(range(80))
    nonce, digest, done = adapter.grind_target_range(header, b"\xff" * 32, 0, 32)
    assert nonce is not None
    sent = bridge.received[-1]
    assert sent["header_prefix_hex"] == header[:76].hex()
    real = double_sha256(header[:76] + int(nonce).to_bytes(4, "little"))
    assert real == bytes(digest)


def test_coordinator_binds_header_on_asic(bridge):
    """run_job prepares every joined device — the ASIC wire carries it."""
    solver = ASICSolver(endpoint=bridge.endpoint)
    coord = HybridCoordinator(GPUSolver(backend="cpu"), solver)
    job = StratumJob(
        job_id="j-coord-bind",
        header80=bytes(range(80)),
        target=b"\xff" * 32,
        nonce_space=64,
    )
    result = coord.run_job(job)
    assert result.share is not None
    assert any(m.get("header_prefix_hex") == job.header80[:76].hex() for m in bridge.received)


def test_channel_eof_is_failure_not_exhaustion():
    """A channel that dies mid-window attests ``failed`` — its nonces were
    NOT covered, and the adapter refuses to report them as hashed."""
    server = _Bridge(drop_dispatch=True)
    try:
        solver = ASICSolver(endpoint=server.endpoint)
        from hyba.hybrid.super_asic import AsicHasherAdapter

        adapter = AsicHasherAdapter(solver)
        with pytest.raises(RuntimeError, match="without exhaustion"):
            adapter.grind_target_range(bytes(range(80)), b"\xff" * 32, 0, 16)
        kinds = {r["kind"] for r in AttestationRegistry.get().snapshot()}
        assert "failed" in kinds
        assert "exhausted" not in kinds
    finally:
        server.shutdown()
        server.server_close()


def test_weighted_partition_apportions_every_device():
    """``weighted`` gives each joined substrate hps-proportional work —
    the composite only combines throughput when all members receive spans."""
    from hyba.hybrid.lucas_partition import partition
    from hyba.hybrid.nonce_scheduler import DeviceCapability

    class _Dev:
        def __init__(self, dev_id, hps):
            self._cap = DeviceCapability(
                device_id=dev_id,
                device_class="asic",
                measured_hashes_per_sec=hps,
                supported=True,
            )

        def capability(self):
            return self._cap

    spans, cert = partition(1000, [_Dev("a", 9.0), _Dev("b", 1.0)], strategy="weighted")
    assert cert.verify()
    by_dev = {s.device_id: s.span for s in spans}
    assert by_dev == {"a": 900, "b": 100}

    # No measurements at all: equal apportionment, not a fabricated weight.
    spans, cert = partition(1000, [_Dev("a", 0.0), _Dev("b", 0.0)], strategy="weighted")
    assert cert.verify()
    assert sum(s.span for s in spans) == 1000
    assert {s.device_id for s in spans} == {"a", "b"}


def test_remote_dispatches_run_one_at_a_time(monkeypatch):
    """A multi-window job queues remote windows: one in-flight call per
    scheduler, never a pile of concurrent requests on one agent."""
    import time as _time

    from hyba.hybrid.remote_solver import RemoteScheduler

    inflight = {"cur": 0, "max": 0}
    lock = threading.Lock()

    class _SerialHasher:
        k_range = object()
        k_m32 = None
        device = "remote-serial-stub"
        backend = "remote_opencl"
        fleet_size = 1
        last_execution_backend = "remote_opencl"
        last_measured_ns = 10**7

        def grind_target_range(self, header, target, base, count):
            with lock:
                inflight["cur"] += 1
                inflight["max"] = max(inflight["max"], inflight["cur"])
            try:
                _time.sleep(0.02)
                return None, None, count
            finally:
                with lock:
                    inflight["cur"] -= 1

    import mining.remote_hasher

    monkeypatch.setattr(mining.remote_hasher, "hasher_for_env", lambda timeout=5.0: _SerialHasher())
    sched = RemoteScheduler()
    assert sched.capability().supported
    sched.prepare("j-seq", bytes(80))
    handles = [sched.dispatch(_window("j-seq", i * 16, 16, b"\x00" * 32)) for i in range(3)]
    deadline = _time.time() + 10
    while not all(sched.is_done(h) for h in handles) and _time.time() < deadline:
        for h in handles:
            sched.poll(h)
    assert all(sched.is_done(h) for h in handles)
    assert inflight["max"] == 1, inflight


def test_remote_dispatch_error_is_failed_not_exhausted(monkeypatch):
    """A mid-job transport error attests ``failed`` — the skipped nonce
    range is a visible defect in the record, not fake coverage."""
    import time as _time

    from hyba.hybrid.remote_solver import RemoteScheduler

    class _FailAfterProbe:
        k_range = object()
        k_m32 = None
        device = "remote-fail-stub"
        backend = "remote_opencl"
        fleet_size = 1
        last_execution_backend = "remote_opencl"
        last_measured_ns = 10**7

        def __init__(self):
            self._calls = 0

        def grind_target_range(self, header, target, base, count):
            self._calls += 1
            if self._calls == 1:
                return None, None, count  # capability probe succeeds
            raise RuntimeError("connection reset by agent")

    import mining.remote_hasher

    monkeypatch.setattr(
        mining.remote_hasher, "hasher_for_env", lambda timeout=5.0: _FailAfterProbe()
    )
    sched = RemoteScheduler()
    assert sched.capability().supported
    sched.prepare("j-fail", bytes(80))
    handle = sched.dispatch(_window("j-fail", 0, 16, b"\x00" * 32))
    deadline = _time.time() + 10
    while not sched.is_done(handle) and _time.time() < deadline:
        sched.poll(handle)
    assert sched.is_done(handle)
    kinds = [r.kind for r in sched.attestation()]
    assert "failed" in kinds
    assert "exhausted" not in kinds
    failed = [r for r in sched.attestation() if r.kind == "failed"]
    assert "remote_dispatch_failed" in failed[-1].reason


def test_lanes_route_through_opencl_range_not_cpu_reference():
    """Selecting asic/super_asic must execute the lane: the coordinator
    picks the contiguous-range route and the router binds the lane's
    ``k_range`` arm — never a silent cpu_reference plan."""
    from chronus.mla1517.mining.execution_router import ExecutionRoute, ExecutionRouter
    from manifold_pool_coordinator import PoolEndpoint
    from test_governance_causality import _plan
    from test_pool_only_mining import _pool_only_coordinator

    class _LaneHasher:
        backend = "super_asic:cpu"
        device = "hybrid[cpu]"
        vendor = None
        k_range = object()
        k_m32 = k_gold = None
        grind_batch = 1 << 20
        launches = 0
        kernel_ms = 0.0

        def __init__(self):
            self.calls = []

        def grind_target_range(self, header, target_be, base, count):
            self.calls.append((base, count))
            self.launches += 1
            return None, None, count

    hasher = _LaneHasher()
    coord = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")], execution_hasher=hasher)
    assert coord._execution_route() == "opencl_range"

    router = ExecutionRouter(hasher, lambda *a: (None, None, 0))
    plan = _plan("opencl_range", base_step=0, window=64, dispatch_breadth=64)
    record, candidate = router.execute_plan(plan, bytes(range(80)), bytes(32))
    assert record.executed_route == ExecutionRoute.opencl_range.value
    assert record.device_backend == "super_asic:cpu"
    assert hasher.calls, "the bound lane was never invoked"
    assert sum(c for _, c in hasher.calls) == 64


class _OpenclHasher:
    backend = "opencl:gpu"
    k_m32 = object()
    k_range = None


def test_opencl_route_unchanged():
    """The lane routing addition must not disturb the existing m32 route."""
    from manifold_pool_coordinator import PoolEndpoint
    from test_pool_only_mining import _pool_only_coordinator

    coord = _pool_only_coordinator(
        [PoolEndpoint("h", 1, "braiins")], execution_hasher=_OpenclHasher()
    )
    assert coord._execution_route() == "opencl_m32"
