"""Unit coverage of transport bounds, configuration precedence and correlation cleanup."""

import asyncio
import json
import sys
from unittest.mock import Mock

import pytest

from Intelligence.lucas_scales import ladder_capacity
from manifold_pool_coordinator import PoolEndpoint, StratumClient, StratumProtocolError
from chronus.mla1517.mining.production_transport import ProductionStratumClient, _positive_env

TIMEOUT_FIELDS = (
    ("connect_timeout", "PYTHIA_STRATUM_CONNECT_TIMEOUT_S"),
    ("request_timeout", "PYTHIA_STRATUM_REQUEST_TIMEOUT_S"),
    ("write_timeout", "PYTHIA_STRATUM_WRITE_TIMEOUT_S"),
    ("enqueue_timeout", "PYTHIA_STRATUM_ENQUEUE_TIMEOUT_S"),
)
QUEUE_ENV = "PYTHIA_STRATUM_OUTBOUND_QUEUE"
INVALID_EXTRA_BOUNDS = [
    pytest.param(False, id="false"),
    pytest.param("0.25", id="numeric-string"),
    pytest.param([], id="list"),
    pytest.param(1 + 0j, id="complex"),
    pytest.param(10**1000, id="integer-overflow"),
]


@pytest.fixture
def client_factory(monkeypatch):
    for _, name in TIMEOUT_FIELDS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(QUEUE_ENV, raising=False)

    def create(**kwargs):
        return ProductionStratumClient(
            PoolEndpoint("pool.example.invalid", 3333, "unit-test"),
            username="unit-worker",
            password="test-only",
            **kwargs,
        )

    return create


@pytest.mark.parametrize("field,env_name", TIMEOUT_FIELDS)
@pytest.mark.parametrize("value", INVALID_EXTRA_BOUNDS)
def test_invalid_explicit_bound_is_rejected_before_base_initialization(
    client_factory, monkeypatch, field, env_name, value
):
    base_init = Mock(side_effect=AssertionError("base initialized before validation"))
    monkeypatch.setattr(StratumClient, "__init__", base_init)
    published = Mock()
    with pytest.raises(ValueError, match=field):
        client_factory(**{field: value}, status_sink=published)
    base_init.assert_not_called()
    published.assert_not_called()


@pytest.mark.parametrize("value", [False, 1.0, "3", [], {}])
def test_invalid_queue_capacity_is_rejected_before_base_initialization(
    client_factory, monkeypatch, value
):
    base_init = Mock(side_effect=AssertionError("base initialized before validation"))
    monkeypatch.setattr(StratumClient, "__init__", base_init)
    with pytest.raises(ValueError, match="outbound_queue_size"):
        client_factory(outbound_queue_size=value)
    base_init.assert_not_called()


@pytest.mark.parametrize("raw", ["0", "-1", "1.5", "true", "nan", "invalid"])
def test_invalid_environment_queue_capacity_has_no_status_side_effect(
    client_factory, monkeypatch, raw
):
    monkeypatch.setenv(QUEUE_ENV, raw)
    published = Mock()
    with pytest.raises(ValueError, match=QUEUE_ENV):
        client_factory(status_sink=published)
    published.assert_not_called()


@pytest.mark.parametrize("raw", [None, "", " \t "])
def test_absent_or_blank_environment_preserves_documented_defaults(
    client_factory, monkeypatch, raw
):
    if raw is not None:
        for _, name in TIMEOUT_FIELDS:
            monkeypatch.setenv(name, raw)
        monkeypatch.setenv(QUEUE_ENV, raw)
    client = client_factory()
    assert client.connect_timeout == 0.75
    assert client.request_timeout == 30.0
    assert client.write_timeout == 0.75
    assert client.enqueue_timeout == 0.25
    assert client._outbound.maxsize == ladder_capacity(256)
    assert client.writer is None


def test_environment_settings_are_preserved_without_rounding(client_factory, monkeypatch):
    for (_, name), raw in zip(TIMEOUT_FIELDS, [" 1.25 ", "2e1", "0.0625", "0.03125"]):
        monkeypatch.setenv(name, raw)
    monkeypatch.setenv(QUEUE_ENV, " 3 ")
    client = client_factory()
    assert (client.connect_timeout, client.request_timeout) == (1.25, 20.0)
    assert (client.write_timeout, client.enqueue_timeout) == (0.0625, 0.03125)
    assert client._outbound.maxsize == 3


@pytest.mark.parametrize("raw", ["nan", "invalid"])
def test_explicit_configuration_takes_precedence_over_invalid_environment(
    client_factory, monkeypatch, raw
):
    for _, name in TIMEOUT_FIELDS:
        monkeypatch.setenv(name, raw)
    monkeypatch.setenv(QUEUE_ENV, raw)
    client = client_factory(
        connect_timeout=1,
        request_timeout=2,
        write_timeout=0.125,
        enqueue_timeout=0.0625,
        outbound_queue_size=1,
    )
    assert (client.connect_timeout, client.request_timeout) == (1, 2)
    assert (client.write_timeout, client.enqueue_timeout) == (0.125, 0.0625)
    assert client._outbound.maxsize == 1


@pytest.mark.parametrize("field,env_name", TIMEOUT_FIELDS)
@pytest.mark.parametrize("value", [sys.float_info.min * sys.float_info.epsilon, sys.float_info.max])
def test_positive_finite_float_extremes_are_valid_configuration(
    client_factory, field, env_name, value
):
    client = client_factory(**{field: value})
    assert getattr(client, field) == value


@pytest.mark.parametrize("raw", [None, "", " \t "])
@pytest.mark.parametrize("default", [float("nan"), float("inf"), 0, -1, True, 10**1000])
def test_missing_environment_still_validates_default(monkeypatch, raw, default):
    name = "TEST_STRATUM_UNIT_TIMEOUT"
    monkeypatch.delenv(name, raising=False)
    if raw is not None:
        monkeypatch.setenv(name, raw)
    with pytest.raises(ValueError, match=name):
        _positive_env(name, default)


@pytest.mark.parametrize("raw", ["1e309", "1e-999", " \tNaN ", "not-a-number"])
def test_environment_overflow_underflow_and_malformed_values_are_rejected(monkeypatch, raw):
    monkeypatch.setenv("TEST_STRATUM_UNIT_TIMEOUT", raw)
    with pytest.raises(ValueError, match="TEST_STRATUM_UNIT_TIMEOUT"):
        _positive_env("TEST_STRATUM_UNIT_TIMEOUT", 1.0)


@pytest.mark.parametrize("use_default", [False, True], ids=["override", "default"])
@pytest.mark.parametrize("value", INVALID_EXTRA_BOUNDS + [pytest.param(float("nan"), id="nan")])
def test_invalid_request_deadline_preserves_existing_correlation(
    client_factory, use_default, value
):
    async def run():
        client = client_factory()
        client.writer = object()
        client._send_payload = Mock(side_effect=AssertionError("invalid request reached send"))
        sentinel = asyncio.get_running_loop().create_future()
        client._pending[99] = sentinel
        if use_default:
            client.request_timeout = value
        try:
            with pytest.raises(ValueError, match="request timeout"):
                await client.request("mining.submit", [], timeout=None if use_default else value)
            assert client._pending == {99: sentinel}
            assert not sentinel.done()
            assert client._next_id == 1
            assert client.wire_writes_for("mining.submit") == 0
            client._send_payload.assert_not_called()
        finally:
            sentinel.cancel()

    asyncio.run(run())


@pytest.mark.parametrize("timeout", [None, 2, 0.125])
@pytest.mark.parametrize("result", [True, False, None, {"result": "literal"}])
def test_valid_request_uses_selected_deadline_and_cleans_completed_future(
    client_factory, monkeypatch, timeout, result
):
    async def run():
        client = client_factory(request_timeout=3.5)
        client.writer = object()
        sent = []
        limits = []
        real_wait_for = asyncio.wait_for

        async def wait_for(awaitable, timeout):
            limits.append(timeout)
            return await real_wait_for(awaitable, timeout)

        async def send(payload, *, method):
            message = json.loads(payload)
            sent.append((message, method))
            assert payload.endswith(b"\n")
            client._pending[message["id"]].set_result(result)

        monkeypatch.setattr(asyncio, "wait_for", wait_for)
        client._send_payload = send
        assert (
            await client.request("mining.authorize", ["unit-worker", "test-only"], timeout=timeout)
            == result
        )
        assert limits == [3.5 if timeout is None else timeout]
        assert sent == [
            (
                {"id": 1, "method": "mining.authorize", "params": ["unit-worker", "test-only"]},
                "mining.authorize",
            )
        ]
        assert client._pending == {}
        assert client._next_id == 2

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["send", "response"])
def test_cancellation_cleans_future_at_each_await_without_pool_outcome(client_factory, stage):
    async def run():
        client = client_factory()
        client.writer = object()
        sent = asyncio.Event()
        futures = []
        writes = []
        before = client.status_snapshot()

        async def send(payload, *, method):
            writes.append(method)
            futures.append(client._pending[json.loads(payload)["id"]])
            sent.set()
            if stage == "send":
                await asyncio.get_running_loop().create_future()

        client._send_payload = send
        task = asyncio.create_task(client.request("mining.submit", [], timeout=10))
        try:
            await asyncio.wait_for(sent.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
            assert futures[0].cancelled()
            assert client._pending == {}
            assert writes == ["mining.submit"]
            assert client.status_snapshot() == before
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure", [ConnectionError("reader failed"), StratumProtocolError("bad reply")]
)
def test_response_failure_removes_correlation_and_propagates_without_retry(client_factory, failure):
    async def run():
        client = client_factory()
        client.writer = object()
        writes = []

        async def send(payload, *, method):
            writes.append(method)
            client._pending[json.loads(payload)["id"]].set_exception(failure)

        client._send_payload = send
        with pytest.raises(type(failure)) as caught:
            await client.request("mining.submit", [], timeout=1)
        assert caught.value is failure
        assert client._pending == {}
        assert writes == ["mining.submit"]

    asyncio.run(run())


@pytest.mark.parametrize("failure", [ConnectionError("send failed"), TimeoutError("queue full")])
def test_send_failure_cancels_unresolved_future_without_retry(client_factory, failure):
    async def run():
        client = client_factory()
        client.writer = object()
        futures = []

        async def send(payload, *, method):
            futures.append(client._pending[json.loads(payload)["id"]])
            raise failure

        client._send_payload = send
        with pytest.raises(type(failure)) as caught:
            await client.request("mining.submit", [], timeout=1)
        assert caught.value is failure
        assert len(futures) == 1
        assert futures[0].cancelled()
        assert client._pending == {}
        assert client.wire_writes_for("mining.submit") == 0

    asyncio.run(run())


@pytest.mark.parametrize("use_default", [False, True], ids=["override", "default"])
def test_response_deadline_cancels_future_without_retry_or_pool_outcome(
    client_factory, use_default
):
    async def run():
        client = client_factory(request_timeout=0.001)
        client.writer = object()
        futures = []
        before = client.status_snapshot()

        async def send(payload, *, method):
            futures.append(client._pending[json.loads(payload)["id"]])

        client._send_payload = send
        with pytest.raises(TimeoutError, match="mining.submit.*timed out"):
            await asyncio.wait_for(
                client.request("mining.submit", [], timeout=None if use_default else 0.001),
                1,
            )
        assert len(futures) == 1
        assert futures[0].cancelled()
        assert client._pending == {}
        assert client.status_snapshot() == before

    asyncio.run(run())


def test_cancelling_one_request_preserves_other_request_and_allows_next_request(client_factory):
    async def run():
        client = client_factory()
        client.writer = object()
        sent = asyncio.Queue()
        writes = []

        async def send(payload, *, method):
            request_id = json.loads(payload)["id"]
            writes.append(request_id)
            sent.put_nowait(request_id)

        client._send_payload = send
        tasks = []
        try:
            first = asyncio.create_task(client.request("mining.submit", [], timeout=10))
            tasks.append(first)
            first_id = await asyncio.wait_for(sent.get(), 1)
            second = asyncio.create_task(client.request("mining.authorize", [], timeout=10))
            tasks.append(second)
            second_id = await asyncio.wait_for(sent.get(), 1)
            remaining = client._pending[second_id]
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(first, 1)
            assert first_id not in client._pending
            assert client._pending == {second_id: remaining}
            assert not remaining.done()
            remaining.set_result(False)
            assert await asyncio.wait_for(second, 1) is False
            assert client._pending == {}

            third = asyncio.create_task(client.request("mining.authorize", [], timeout=10))
            tasks.append(third)
            third_id = await asyncio.wait_for(sent.get(), 1)
            client._pending[third_id].set_result(True)
            assert await asyncio.wait_for(third, 1) is True
            assert writes == [1, 2, 3]
            assert client._next_id == 4
            assert client._pending == {}
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(run())
