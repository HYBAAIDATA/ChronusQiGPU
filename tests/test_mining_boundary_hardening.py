"""Real planning/transport methods with isolated dependencies; no live pool writes."""

import asyncio
from types import SimpleNamespace

import pytest

from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.production_transport import (
    ProductionStratumClient,
    _positive_env,
)
from chronus.mla1517.mining.search_plan import WorkIdentity


@pytest.mark.parametrize("builder", ["_baseline_plan", "_build_plan"])
@pytest.mark.parametrize(
    "nonce_order",
    ["hendrix_coprime_stride", "m32_turing_complete", "poincare_cassini_11d"],
)
@pytest.mark.parametrize(
    "advice", [None, {}, {"status": "UNAVAILABLE"}, {"path": "solve"}]
)
def test_advisory_evidence_cannot_replace_configured_order(
    builder, nonce_order, advice
):
    identity = WorkIdentity("session", 1, "job", "f" * 64, 1, True, 1.0)
    lease = SimpleNamespace(start=0, count=64, extranonce2="00000000", lease_id="lease")
    lane_order = tuple(reversed(range(32)))
    coordinator = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    coordinator._nonce_order = nonce_order
    coordinator._dispatch_breadth = 32
    coordinator._lane_order_for = lambda *args: (lane_order, "fixture", advice)
    coordinator._execution_route = lambda: "cpu_reference"
    coordinator._next_window = lambda: 64
    coordinator._toe_advice_reason = lambda: None
    coordinator.production_integration = SimpleNamespace(plan_evidence=lambda *args: {})
    coordinator.solver = SimpleNamespace(get_lane_start_offset=lambda: 0)
    coordinator.last_toe_frame = None
    coordinator.last_toe_signal = None
    coordinator.last_mining_decision = None
    coordinator.tuning = SimpleNamespace(last_decision=None)
    coordinator.client = SimpleNamespace(
        proof_adapter=SimpleNamespace(next_extranonce2=lambda: "00000000")
    )
    coordinator.agentic = SimpleNamespace(
        reserve_lease=lambda *args: lease,
        release_lease=lambda *args: pytest.fail("valid plan unexpectedly refused"),
        lookahead=1,
    )
    if builder == "_baseline_plan":
        plan = coordinator._baseline_plan(identity, lease, 64, "queue_empty")
    else:
        plan = coordinator._build_plan(identity)
    assert plan.nonce_order == nonce_order
    assert plan.lane_order == lane_order
    assert plan.evidence_refs["solve_first"] == advice
    assert plan.evidence_refs["lane_order_source"] == "fixture"
    assert plan.window == 64 and plan.base_step == 0


@pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "+inf", "-inf", "0", "-1"])
def test_timeout_environment_is_finite_and_positive(monkeypatch, raw):
    monkeypatch.setenv("TEST_STRATUM_TIMEOUT", raw)
    with pytest.raises(ValueError):
        _positive_env("TEST_STRATUM_TIMEOUT", 1.0)


@pytest.mark.parametrize(
    "field", ["connect_timeout", "request_timeout", "write_timeout", "enqueue_timeout"]
)
@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), 0, -1, True]
)
def test_explicit_timeouts_cannot_disable_transport_deadlines(field, value):
    with pytest.raises(ValueError):
        ProductionStratumClient(
            PoolEndpoint("localhost", 3333, "test-only"),
            username="test-worker",
            password="test-only",
            **{field: value}
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1.5, True, 0, -1])
def test_queue_bound_is_a_positive_integer(value):
    with pytest.raises(ValueError):
        ProductionStratumClient(
            PoolEndpoint("localhost", 3333, "test-only"),
            username="test-worker",
            password="test-only",
            outbound_queue_size=value,
        )


def test_valid_transport_configuration_does_not_connect(monkeypatch):
    monkeypatch.setenv("TEST_STRATUM_TIMEOUT", "0.125")
    assert _positive_env("TEST_STRATUM_TIMEOUT", 1.0) == 0.125
    client = ProductionStratumClient(
        PoolEndpoint("localhost", 3333, "test-only"),
        username="worker",
        password="test-only",
        connect_timeout=1,
        request_timeout=2,
        write_timeout=0.5,
        enqueue_timeout=0.25,
        outbound_queue_size=3,
    )
    assert client.connect_timeout == 1 and client.request_timeout == 2
    assert client.write_timeout == 0.5 and client.enqueue_timeout == 0.25
    assert client._outbound.maxsize == 3
    assert client.writer is None and not client.connected


@pytest.mark.parametrize(
    "name",
    [
        "PYTHIA_STRATUM_CONNECT_TIMEOUT_S",
        "PYTHIA_STRATUM_REQUEST_TIMEOUT_S",
        "PYTHIA_STRATUM_WRITE_TIMEOUT_S",
        "PYTHIA_STRATUM_ENQUEUE_TIMEOUT_S",
    ],
)
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_runtime_environment_cannot_disable_transport_deadlines(
    monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    published = []
    with pytest.raises(ValueError):
        ProductionStratumClient(
            PoolEndpoint("localhost", 3333, "test-only"),
            username="worker",
            password="test-only",
            status_sink=published.append,
        )
    assert published == []


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), 0, -1, True]
)
def test_request_override_refuses_before_pending_or_write(value):
    async def run():
        client = ProductionStratumClient(
            PoolEndpoint("localhost", 3333, "test-only"),
            username="worker",
            password="x",
        )
        client.writer = object()  # Explicit IO seam; no socket is opened.
        writes = []

        async def send(payload, *, method):
            writes.append(method)
            # Avoid a hanging test even against the unfixed implementation.
            next(iter(client._pending.values())).set_result(True)

        client._send_payload = send
        with pytest.raises(ValueError):
            await client.request("mining.submit", [], timeout=value)
        assert writes == [] and client._pending == {} and client._next_id == 1

    asyncio.run(run())


def test_cancelled_request_releases_pending_correlation_without_retry():
    async def run():
        client = ProductionStratumClient(
            PoolEndpoint("localhost", 3333, "test-only"),
            username="worker",
            password="x",
        )
        client.writer = object()  # Explicit IO seam; no pool outcome is invented.
        sent = asyncio.Event()
        writes = []

        async def send(payload, *, method):
            writes.append(method)
            sent.set()

        client._send_payload = send
        task = asyncio.create_task(client.request("mining.submit", [], timeout=10))
        await sent.wait()
        assert len(client._pending) == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client._pending == {} and writes == ["mining.submit"]
        assert (
            client.wire_writes_for("mining.submit") == 0
        )  # The seam never wrote bytes.

    asyncio.run(run())
