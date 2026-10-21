"""Local-only Stratum/socket and executor regressions; not live pool qualification."""
import asyncio
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from mining.production_miner import (
    ExecutionResult, MAX_UINT256, PoolEndpoint, ProductionMiner,
    StratumV1Client, parse_notify,
)


def notify():
    return ['local-job', '00' * 32, '00', '00', [], '00000001',
            '207fffff', '65000000', True]


def client():
    return StratumV1Client(PoolEndpoint('127.0.0.1', 1, False), 'fixture', 'fixture', timeout=1)


@pytest.mark.parametrize('method,value', [('mining.set_target', '00'*31+'01'), ('mining.set_difficulty', 2)])
def test_changed_target_invalidates_old_generation(method, value):
    async def scenario():
        c = client()
        c.target = MAX_UINT256
        c.generation = 1
        c.job = parse_notify(notify(), 1, MAX_UINT256)
        old = c.job
        await c._notification({'method': method, 'params': [value]})
        assert c.job.generation > old.generation
        assert c.job.target != old.target
        c.authorized = True
        # Stale candidate must be rejected before any network request.
        assert await c.submit(old, '', 0) is False
    asyncio.run(scenario())


def test_same_target_does_not_invalidate_work():
    c = client()
    c.target = MAX_UINT256
    c.generation = 1
    c.job = parse_notify(notify(), 1, MAX_UINT256)
    c._update_target(MAX_UINT256)
    assert c.generation == 1


def test_stratum_reader_progresses_during_native_window(tmp_path):
    async def scenario():
        started = threading.Event()
        finished = threading.Event()
        server_tasks = set()
        observations = []
        worker_observed_notification = []
        stop = tmp_path / 'drain'

        class SlowExecutor:
            def execute(self, header, target, base, count):
                started.set()
                # Worker waits for socket notification to be processed. If this
                # blocks the event loop the original implementation times out.
                deadline = time.monotonic() + 0.8
                while not finished.is_set() and time.monotonic() < deadline:
                    time.sleep(0.002)
                worker_observed_notification.append(finished.is_set())
                digest = hashlib.sha256(hashlib.sha256(header[:76] + b'\0'*4).digest()).digest()
                return ExecutionResult(0, digest, count, {'backend': 'fixture-cpu'})

        async def serve(reader, writer):
            server_tasks.add(asyncio.current_task())
            try:
                for method, result in [('mining.subscribe', [[], 'aa', 0]), ('mining.authorize', True)]:
                    req = json.loads(await reader.readline())
                    assert req['method'] == method
                    writer.write((json.dumps({'id': req['id'], 'result': result, 'error': None})+'\n').encode())
                    await writer.drain()
                for method, params in [('mining.set_target', ['ff'*32]), ('mining.notify', notify())]:
                    writer.write((json.dumps({'method': method, 'params': params})+'\n').encode())
                await writer.drain()
                while not started.is_set():
                    await asyncio.sleep(0.002)
                writer.write((json.dumps({'method': 'mining.set_target', 'params': ['00'*31+'01']})+'\n').encode())
                await writer.drain()
                deadline = time.monotonic()+1
                while c.target != 1 and time.monotonic() < deadline:
                    await asyncio.sleep(0.002)
                observations.append(c.target)
                stop.touch()
                finished.set()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                server_tasks.discard(asyncio.current_task())

        server = await asyncio.start_server(serve, '127.0.0.1', 0)
        c = StratumV1Client(PoolEndpoint('127.0.0.1', server.sockets[0].getsockname()[1], False), 'fixture', 'fixture', timeout=2)
        try:
            await c.connect_and_authorize()
            m = ProductionMiner(c, SlowExecutor(), window=32, submit_enabled=True)
            m.stop_file = stop
            assert await asyncio.wait_for(m.run_session(), 3) is False
            assert observations == [1]
            assert worker_observed_notification == [True]
            assert c.accepted == 0 and c.rejected == 0
            assert m.total_hashes == 32
        finally:
            finished.set()
            await c.close()
            server.close()
            await server.wait_closed()
            await asyncio.gather(*list(server_tasks))
    asyncio.run(scenario())


def test_cancel_drains_one_window_without_blocking_event_loop():
    async def scenario():
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def execute(*args):
            started.set()
            release.wait(2)
            finished.set()
            return ExecutionResult(None, None, 1, {})
        m = ProductionMiner(client(), SimpleNamespace(execute=execute), window=1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            m._window_pool = pool
            task = asyncio.create_task(m._execute_window(b'\0'*80, 1, 0, 1))
            while not started.is_set():
                await asyncio.sleep(0.002)
            task.cancel()
            await asyncio.sleep(0.02)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert finished.is_set()
    asyncio.run(scenario())


def test_local_socket_kill_clears_identity_on_reconnect():
    async def scenario():
        sessions = 0
        handlers = set()
        async def serve(reader, writer):
            nonlocal sessions
            handlers.add(asyncio.current_task())
            sessions += 1
            try:
                for result in [[[], 'aa', 0], True]:
                    req = json.loads(await reader.readline())
                    writer.write((json.dumps({'id': req['id'], 'result': result, 'error': None})+'\n').encode())
                    await writer.drain()
                if sessions == 1:
                    writer.write((json.dumps({'method': 'mining.notify', 'params': notify()})+'\n').encode())
                    await writer.drain()
                else:
                    await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(asyncio.current_task())
        server = await asyncio.start_server(serve, '127.0.0.1', 0)
        c = StratumV1Client(PoolEndpoint('127.0.0.1', server.sockets[0].getsockname()[1], False), 'fixture', 'fixture', timeout=1)
        try:
            await c.connect_and_authorize()
            while c.connected:
                await asyncio.sleep(0.002)
            t = time.monotonic()
            await c.connect_and_authorize()
            assert time.monotonic() - t < 30
            assert c.authorized and c.job is None
            assert sessions == 2
        finally:
            await c.close()
            server.close()
            await server.wait_closed()
            await asyncio.gather(*list(handlers))
    asyncio.run(scenario())
