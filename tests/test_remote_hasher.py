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
                    "protocol": "remote_opencl_v1",
                    "devices": [{"name": "Stub iGPU-0", "vendor": "Intel", "type": "igpu"}],
                    "error": None,
                },
            )
        if self.path == "/v1/health":
            endpoints = ["sha256d"] if type(self).advertise_sha256d else ["ladder"]
            return self._reply(
                200,
                {
                    "status": "ok",
                    "protocol": "remote_opencl_v1",
                    "device_count": 1,
                    "opencl_error": None,
                    "endpoints": endpoints,
                },
            )
        return self._reply(404, {"error": "unknown"})

    def do_POST(self):
        if self.path != "/v1/sha256d":
            return self._reply(404, {"error": "unknown"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
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
        return self._reply(
            200,
            {
                "device": {"name": "Stub iGPU-0", "vendor": "Intel"},
                "execution_backend": "opencl:gpu",
                "order": order,
                "hashes": len(window),
                "window": len(window),
                "measured_ns": 999,
                "winner": winner,
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
    server.shutdown()


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
    assert hashes == 8
    blob = bytes(76) + nonce.to_bytes(4, "little")
    assert digest == hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def test_grind_m32_runs_the_remote_window(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    lanes = list(range(32))
    nonce, digest, hashes = hasher.grind_target_m32(bytes(80), b"\xff" * 32, 0, lanes, 64)
    assert nonce == 0
    assert hashes == 64
    assert hasher.last_execution_backend == "opencl:gpu"


def test_grind_batch_executes_the_given_nonces(stub_agent):
    hasher = RemoteOpenCLHasher.from_env()
    nonce, digest, hashes = hasher.grind_target_batch(bytes(80), b"\xff" * 32, [5, 9, 12])
    assert nonce == 5
    assert hashes == 3


def test_tampered_winner_never_reaches_the_pipeline(stub_agent):
    _StubAgent.tamper = True
    hasher = RemoteOpenCLHasher.from_env()
    from mla1517.remote_gpu import RemoteGPUVerificationError

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
    from mla1517.mining.search_plan import PlanSource, SearchPlan

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
    from mla1517.mining.execution_router import ExecutionRouter

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
    from mla1517.mining.search_plan import FallbackReason

    hasher = RemoteOpenCLHasher.from_env()
    decision = _router(hasher).decide_route(_plan("opencl_gold"))
    assert decision.executed_route.value == "cpu_reference"
    assert decision.fallback_reason == FallbackReason.KERNEL_UNAVAILABLE


def test_unadvertised_sha256d_has_no_route_arms(stub_agent):
    _StubAgent.advertise_sha256d = False
    hasher = RemoteOpenCLHasher.from_env()
    assert getattr(hasher, "k_range", None) is None
    assert getattr(hasher, "k_m32", None) is None
    from mla1517.mining.search_plan import FallbackReason

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
