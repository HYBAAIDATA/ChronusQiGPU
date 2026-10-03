"""Remote OpenCL hasher — the mining pipeline reaches a GPU anywhere.

The stub agent answers /v1/sha256d with honest hashlib-computed results
(an ``opencl:gpu`` label is part of the wire contract being faked — what
matters is that every returned winner is real and client-verified).
"""

import hashlib
import json
import threading

import pytest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mining.hash_pipeline import HashPipeline
from mining.remote_hasher import RemoteHasherError, RemoteOpenCLHasher


class _StubAgent(BaseHTTPRequestHandler):
    """A remote agent serving one iGPU and honest sha256d windows."""

    protocol_version = "HTTP/1.1"
    tamper = False
    advertise_sha256d = True
    telemetry_measured = False

    def log_message(self, *args):
        return

    def _reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/devices":
            return self._reply(
                200,
                {
                    "protocol": "remote_opencl_v2",
                    "devices": [
                        {
                            "id": "stub-igpu-0",
                            "name": "Stub iGPU-0",
                            "vendor": "Intel",
                            "type": "igpu",
                        }
                    ],
                    "error": None,
                },
            )
        if self.path == "/v1/health":
            endpoints = ["sha256d"] if type(self).advertise_sha256d else ["ladder"]
            return self._reply(
                200,
                {
                    "status": "ok",
                    "protocol": "remote_opencl_v2",
                    "device_count": 1,
                    "opencl_error": None,
                    "endpoints": endpoints,
                },
            )
        if self.path == "/v1/telemetry":
            measured = type(self).telemetry_measured
            return self._reply(
                200,
                {
                    "protocol": "remote_opencl_v2",
                    "devices": [
                        {
                            "name": "Stub iGPU-0",
                            "vendor": "Intel",
                            "temperature_c": 55.0 if measured else None,
                            "power_w": 20.5 if measured else None,
                            "utilization_pct": 88.0 if measured else None,
                        }
                    ],
                    "sources": [
                        {
                            "tool": "nvidia-smi",
                            "status": "measured" if measured else "unavailable",
                        }
                    ],
                },
            )
        return self._reply(404, {"error": "unknown"})

    def do_POST(self):
        if self.path != "/v1/sha256d":
            return self._reply(404, {"error": "unknown"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen = getattr(self.server, "seen", None)
        if seen is not None:
            seen.append(
                {
                    "order": body.get("order"),
                    "base": int(body.get("base_nonce", 0)),
                    "count": int(body.get("count", 0)),
                    "nonces": len(body["nonces"]) if body.get("nonces") else None,
                }
            )
        header = bytes.fromhex(body["header"])
        target = bytes.fromhex(body["target"])
        order = body.get("order", "contiguous")
        nonces = body.get("nonces")
        base = int(body.get("base_nonce", 0))
        count = int(body.get("count", 0))
        if nonces is not None:
            window = [int(n) & 0xFFFFFFFF for n in nonces]
        elif order == "m32":
            lanes = [int(l) for l in body.get("lane_order", [])]
            window = [(base + lanes[i % 32] + 32 * (i // 32)) & 0xFFFFFFFF for i in range(count)]
        else:
            window = [(base + i) & 0xFFFFFFFF for i in range(count)]
        blob = bytearray(header)
        winner = None
        for nonce in window:
            blob[76:80] = nonce.to_bytes(4, "little")
            digest = hashlib.sha256(hashlib.sha256(bytes(blob)).digest()).digest()
            if digest[::-1] <= target:
                winner = {
                    "nonce": nonce,
                    "digest": "00" * 32 if type(self).tamper else digest.hex(),
                }
                break
        from chronus.mla1517.remote_gpu import (
            _attestation_key,
            _window_commitment,
            sha256d_share_attestation,
        )

        device_name = "Stub iGPU-0"
        device_id = "stub-igpu-0"
        measured_ns = 999
        hashes = len(window) if winner is None else window.index(winner["nonce"]) + 1
        commitment = _window_commitment(order, window)
        attestation = sha256d_share_attestation(
            header_hex=header.hex(),
            target_hex=target.hex(),
            base_nonce=base,
            count=len(window),
            hashes=hashes,
            nonce=None if winner is None else winner["nonce"],
            digest_hex=None if winner is None else winner["digest"],
            device=device_name,
            device_id=device_id,
            execution_backend="opencl:gpu",
            measured_ns=measured_ns,
            order=order,
            window_commitment=commitment,
            key=_attestation_key() or None,
        )
        return self._reply(
            200,
            {
                "protocol": "remote_opencl_v2",
                "device": {"id": device_id, "name": device_name},
                "execution_backend": "opencl:gpu",
                "measured_ns": measured_ns,
                "window": {"base_nonce": base, "count": len(window)},
                "order": order,
                "window_commitment": commitment,
                "hashes": hashes,
                "share": (
                    None if winner is None else {"nonce": winner["nonce"], "hash": winner["digest"]}
                ),
                "attestation": attestation,
            },
        )


@pytest.fixture()
def stub_agent(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubAgent)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("MLA1517_REMOTE_GPU_ENDPOINT", endpoint)
    monkeypatch.delenv("HYBA_REMOTE_OPENCL_ENDPOINTS", raising=False)
    yield endpoint
    _StubAgent.tamper = False
    _StubAgent.advertise_sha256d = True
    _StubAgent.telemetry_measured = False
    server.shutdown()


@pytest.fixture()
def stub_fleet(monkeypatch):
    """Two independent stub agents bound as one fleet."""
    servers = []
    endpoints = []
    for _ in range(2):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubAgent)
        srv.seen = []
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        endpoints.append(f"http://127.0.0.1:{srv.server_address[1]}")
    monkeypatch.delenv("MLA1517_REMOTE_GPU_ENDPOINT", raising=False)
    monkeypatch.setenv("HYBA_REMOTE_OPENCL_ENDPOINTS", ",".join(endpoints))
    yield endpoints, servers
    _StubAgent.tamper = False
    _StubAgent.advertise_sha256d = True
    _StubAgent.telemetry_measured = False
    for srv in servers:
        srv.shutdown()


def test_from_env_fails_closed_without_endpoint(monkeypatch):
    monkeypatch.delenv("MLA1517_REMOTE_GPU_ENDPOINT", raising=False)
    monkeypatch.delenv("HYBA_REMOTE_OPENCL_ENDPOINTS", raising=False)
    with pytest.raises(RemoteHasherError):
        RemoteOpenCLHasher.from_env()


def test_from_env_binds_stub_device(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    assert hasher.backend == "remote_opencl"
    assert hasher.device == "Stub iGPU-0"
    assert hasher.endpoint == stub_agent


def test_grind_range_returns_verified_triple(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    nonce, digest, hashes = hasher.grind_target_range(bytes(80), b"\xff" * 32, 0, 8)
    assert nonce == 0
    assert hashes == 1
    blob = bytes(76) + nonce.to_bytes(4, "little")
    assert digest == hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def test_grind_m32_runs_the_remote_window(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    lanes = list(range(32))
    nonce, digest, hashes = hasher.grind_target_m32(bytes(80), b"\xff" * 32, 0, lanes, 64)
    assert nonce == 0
    assert hashes == 1
    assert hasher.last_execution_backend == "opencl:gpu"


def test_grind_batch_executes_the_given_nonces(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    nonce, digest, hashes = hasher.grind_target_batch(bytes(80), b"\xff" * 32, [5, 9, 12])
    assert nonce == 5
    assert hashes == 1


def test_tampered_winner_never_reaches_the_pipeline(stub_agent):
    _StubAgent.tamper = True
    hasher = RemoteOpenCLHasher.from_env()
    from chronus.mla1517.remote_gpu import RemoteGPUVerificationError

    with pytest.raises(RemoteGPUVerificationError):
        hasher.grind_target_range(bytes(80), b"\xff" * 32, 0, 4)


def test_pipeline_grinds_through_the_remote_hasher(stub_agent):
    pipe = HashPipeline(threshold=0.0, hasher_backend="remote")
    result = pipe.grind(bytes(80), b"\xff" * 32, list(range(64)))
    assert result.mining_success
    assert result.backend == "remote_opencl"
    assert result.device == "Stub iGPU-0"
    blob = bytes(76) + result.winning_nonce.to_bytes(4, "little")
    assert hashlib.sha256(hashlib.sha256(blob).digest()).digest() == result.winning_hash


def _plan(route, window=64):
    from chronus.mla1517.mining.search_plan import PlanSource, SearchPlan

    return SearchPlan(
        job_fingerprint="fp-1",
        pool_session_id="sess-1",
        generation=1,
        base_step=0,
        window=window,
        extranonce2="00000001",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=32,
        executor_route=route,
        policy_id="test",
        evidence_refs={},
        created_at=1.0,
        source=PlanSource.AGENTIC_PRECOMPUTED,
    )


def _cpu_sweep(header, target, start, count):
    return None, None, count


def _router(hasher):
    from chronus.mla1517.mining.execution_router import ExecutionRouter

    return ExecutionRouter(hasher, _cpu_sweep)


def test_router_decides_opencl_routes_on_the_remote_hasher(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    router = _router(hasher)
    for route in ("opencl_m32", "opencl_range"):
        decision = router.decide_route(_plan(route))
        assert decision.executed_route.value == route
        assert decision.device_backend == "remote_opencl"
        assert decision.kernel_build_status == "compiled"


def test_router_executes_an_m32_window_remotely(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    router = _router(hasher)
    record, candidate = router.execute_plan(_plan("opencl_m32"), bytes(80), b"\xff" * 32)
    assert record.device_backend == "remote_opencl"
    assert record.hash_count > 0
    # Target maxed: first m32-traversed nonce (base + lane 0 = 0) wins.
    assert candidate is not None and candidate["nonce"] == 0
    assert candidate["independently_rechecked"]


def test_router_refuses_gold_stride_honestly(stub_agent):
    # k_gold is absent on the remote hasher — hendrix is not implemented
    # over the wire, so the route falls back with KERNEL_UNAVAILABLE,
    # never silently executing a different traversal.
    from chronus.mla1517.mining.search_plan import FallbackReason

    hasher = RemoteOpenCLHasher.from_env()
    decision = _router(hasher).decide_route(_plan("opencl_gold"))
    assert decision.executed_route.value == "cpu_reference"
    assert decision.fallback_reason == FallbackReason.KERNEL_UNAVAILABLE


def test_unadvertised_sha256d_has_no_route_arms(stub_agent):
    _StubAgent.advertise_sha256d = False
    hasher = RemoteOpenCLHasher.from_env()
    assert getattr(hasher, "k_range", None) is None
    assert getattr(hasher, "k_m32", None) is None
    from chronus.mla1517.mining.search_plan import FallbackReason

    decision = _router(hasher).decide_route(_plan("opencl_m32"))
    assert decision.fallback_reason == FallbackReason.KERNEL_UNAVAILABLE


def test_execution_device_accepts_remote(monkeypatch):
    import mining_runtime

    monkeypatch.setenv("PYTHIA_EXECUTION_DEVICE", "remote")
    assert mining_runtime.execution_device() == "remote"


def test_execution_hasher_binds_remote(stub_agent):
    import mining_runtime

    hasher = mining_runtime._execution_hasher("remote")
    assert hasher.backend == "remote_opencl"
    assert hasher.device == "Stub iGPU-0"


def test_telemetry_stays_unmeasured_without_probes(stub_agent):
    # The stub reports null telemetry — the hasher must carry None, never
    # a substituted number.
    hasher = RemoteOpenCLHasher.from_env()
    assert hasher.last_temperature_c is None
    assert hasher.last_power_w is None


def test_measured_telemetry_binds_to_the_hasher(stub_agent):
    _StubAgent.telemetry_measured = True
    hasher = RemoteOpenCLHasher.from_env()
    assert hasher.last_temperature_c == 55.0
    assert hasher.last_power_w == 20.5


def test_hasher_for_env_binds_one_agent(stub_agent):
    from mining.remote_hasher import hasher_for_env

    hasher = hasher_for_env()
    assert type(hasher) is RemoteOpenCLHasher


def test_fleet_slices_a_window_across_every_agent(stub_fleet):
    from mining.remote_hasher import RemoteFleetHasher, hasher_for_env

    endpoints, servers = stub_fleet
    hasher = hasher_for_env()
    assert type(hasher) is RemoteFleetHasher
    assert hasher.fleet_size == 2

    nonce, digest, hashes = hasher.grind_target_range(bytes(80), b"\xff" * 32, 0, 8)
    # Each slice stops at its first winner — merged hashes is the true
    # executed count, not the window size.
    assert nonce == 0 and hashes == 2
    assert hasher.remote_calls == 2
    # Disjoint coverage: [0,4) on agent 0, [4,8) on agent 1 — the union
    # is the whole window, no overlap, no gap.
    slices = [
        (servers[0].seen[0]["base"], servers[0].seen[0]["count"]),
        (servers[1].seen[0]["base"], servers[1].seen[0]["count"]),
    ]
    assert sorted(slices) == [(0, 4), (4, 4)]


def test_fleet_m32_slices_stay_whole_lane_sweeps(stub_fleet):
    from mining.remote_hasher import hasher_for_env

    endpoints, servers = stub_fleet
    hasher = hasher_for_env()
    lanes = list(range(32))
    nonce, digest, hashes = hasher.grind_target_m32(bytes(80), b"\xff" * 32, 0, lanes, 64)
    assert hashes == 2  # one executed hash per slice before its winner
    for srv in servers:
        assert srv.seen[0]["order"] == "m32"
        assert srv.seen[0]["count"] % 32 == 0
    counts = sorted(srv.seen[0]["count"] for srv in servers)
    assert counts == [32, 32]


def test_fleet_winner_is_the_earliest_slice(stub_fleet):
    # Both slices hold winners under a maxed target; the merged result
    # must be the earliest-slice winner, matching serial traversal.
    from mining.remote_hasher import hasher_for_env

    hasher = hasher_for_env()
    nonce, digest, hashes = hasher.grind_target_range(bytes(80), b"\xff" * 32, 0, 8)
    assert nonce == 0  # agent-0 slice [0,4) — never the later slice's 4


def test_fleet_reports_partial_coverage_never(stub_fleet):
    # One member dies after bind: the window is not fully covered, so
    # the call fails — a partially-executed window is never claimed.
    from chronus.mla1517.remote_gpu import RemoteGPUUnavailable
    from mining.remote_hasher import hasher_for_env

    endpoints, servers = stub_fleet
    hasher = hasher_for_env()
    servers[1].shutdown()
    with pytest.raises(RemoteGPUUnavailable):
        hasher.grind_target_range(bytes(80), b"\xff" * 32, 0, 8)


def test_fleet_skips_non_sha256d_agents(stub_fleet):
    # An endpoint that never advertised sha256d is excluded and named in
    # skipped_endpoints — the fleet never silently pretends to be whole.
    from mining.remote_hasher import RemoteFleetHasher

    endpoints, servers = stub_fleet

    class _NoSha(_StubAgent):
        advertise_sha256d = False

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _NoSha)
    srv.seen = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ep = f"http://127.0.0.1:{srv.server_address[1]}"
        hasher = RemoteFleetHasher([endpoints[0], ep])
        assert hasher.fleet_size == 1
        assert len(hasher.skipped_endpoints) == 1
        assert "sha256d" in hasher.skipped_endpoints[0]
    finally:
        srv.shutdown()
