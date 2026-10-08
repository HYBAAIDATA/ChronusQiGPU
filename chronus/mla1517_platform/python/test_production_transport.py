"""Production Stratum transport regression tests."""

from __future__ import annotations

import asyncio
import json
import socket
import unittest

from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.causal import CausalLedger
from chronus.mla1517.mining.cycle_fsm import MiningCycleLedger
from chronus.mla1517.mining.production_transport import (
    ProductionMiningCoordinator,
    ProductionStratumClient,
)


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


class _HandshakePool:
    def __init__(self) -> None:
        self.connections = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        try:
            subscribe = json.loads(await reader.readline())
            writer.write(
                _line(
                    {
                        "id": subscribe["id"],
                        "result": [[["mining.notify", "session"]], "01020304", 4],
                        "error": None,
                    }
                )
            )
            await writer.drain()
            authorize = json.loads(await reader.readline())
            writer.write(_line({"id": authorize["id"], "result": True, "error": None}))
            await writer.drain()
            # Keep the session alive until the client closes it.
            await reader.read()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


class _HangingWriter:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.payloads.append(payload)

    async def drain(self) -> None:
        await asyncio.sleep(10)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class ProductionTransportTests(unittest.TestCase):
    def test_defaults_are_bounded_and_sub_second(self) -> None:
        client = ProductionStratumClient(
            PoolEndpoint("127.0.0.1", 1, "test"),
            username="worker",
            password="x",
        )
        self.assertLess(client.connect_timeout, 1.0)
        self.assertLessEqual(client.write_timeout, 1.0)
        self.assertGreater(client._outbound.maxsize, 0)

    def test_writer_stall_fails_inside_bounded_budget(self) -> None:
        asyncio.run(self._writer_stall())

    async def _writer_stall(self) -> None:
        client = ProductionStratumClient(
            PoolEndpoint("127.0.0.1", 1, "test"),
            username="worker",
            password="x",
            write_timeout=0.01,
            enqueue_timeout=0.01,
            request_timeout=0.1,
        )
        client.writer = _HangingWriter()
        client._closed = False
        client._reader_task = asyncio.create_task(asyncio.sleep(10))
        try:
            with self.assertRaises((TimeoutError, ConnectionError)):
                await client.request("mining.submit", ["worker", "job", "00", "00", "00"])
            # writer.write accepted the request bytes even though drain wedged;
            # the transport must classify this boundary as non-retryable.
            self.assertEqual(client.wire_writes_for("mining.submit"), 1)
            self.assertFalse(client.connected)
        finally:
            await client.close()

    def test_disconnected_request_has_zero_wire_write_receipt(self) -> None:
        async def voyage() -> None:
            client = ProductionStratumClient(
                PoolEndpoint("127.0.0.1", 1, "test"),
                username="worker",
                password="x",
            )
            with self.assertRaises(ConnectionError):
                await client.request("mining.submit", ["worker", "job", "00", "00", "00"])
            self.assertEqual(client.wire_writes_for("mining.submit"), 0)

        asyncio.run(voyage())

    def test_telemetry_does_not_invent_stale_or_effective_hashrate(self) -> None:
        client = ProductionStratumClient(
            PoolEndpoint("127.0.0.1", 1, "test"),
            username="worker",
            password="x",
        )
        client.runtime_state.submitted = 4
        client.runtime_state.accepted = 3
        client.runtime_state.rejected = 1
        client._submit_rtt_ms.extend([1.0, 2.0, 3.0, 4.0])
        snapshot = client.status_snapshot()
        self.assertEqual(snapshot["outcomes"]["accepted_ratio"], 0.75)
        self.assertEqual(snapshot["outcomes"]["rejected_ratio"], 0.25)
        self.assertIsNone(snapshot["outcomes"]["stale_ratio"])
        self.assertIsNone(snapshot["effective_stratum_hashrate_hs"])
        self.assertEqual(snapshot["submission"]["rtt_ms"]["samples"], 4)
        self.assertEqual(snapshot["submission"]["rtt_ms"]["mean"], 2.5)

    def test_primary_failure_advances_to_secondary(self) -> None:
        asyncio.run(self._failover())

    async def _failover(self) -> None:
        pool = _HandshakePool()
        server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
        live_port = server.sockets[0].getsockname()[1]
        # Reserve, then release, a local port so the first endpoint has no
        # listener and fails immediately without external network access.
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
        probe.close()

        coord = ProductionMiningCoordinator.__new__(ProductionMiningCoordinator)
        coord.endpoints = (
            PoolEndpoint("127.0.0.1", dead_port, "primary"),
            PoolEndpoint("127.0.0.1", live_port, "secondary"),
        )
        coord.username = "worker"
        coord.password = "x"
        coord.endpoint_index = 0
        coord.client = None
        coord.stratum_status_sink = None
        coord.production_connect_timeout = 0.05
        coord.production_request_timeout = 1.0
        coord.production_write_timeout = 0.1
        coord.production_outbound_queue_size = 8
        coord._refresh_work_identity = lambda: None
        coord._precompute_wake = asyncio.Event()
        # This fixture bypasses __init__ via __new__, so the two collaborators the
        # failover path records into must be supplied the way
        # IntelligentPoolCoordinator.__init__ builds them (coordinator.py:416,419).
        # Without them connect_with_failover raises AttributeError on self.causal
        # once the secondary endpoint succeeds.
        coord.causal = CausalLedger()
        coord.cycle = MiningCycleLedger(on_event=coord._mirror_cycle_event)
        try:
            client = await coord.connect_with_failover()
            self.assertEqual(client.endpoint.name, "secondary")
            self.assertEqual(coord.endpoint_index, 1)
            self.assertEqual(pool.connections, 1)

            # Failover evidence must come from the canonical causal mechanism, and
            # must record the real refusal of the configured primary -- not a
            # synthesised success, and not a substituted default pool.
            events = coord.causal.events()
            kinds = [event.kind for event in events]
            self.assertIn("pool_endpoint_refused", kinds)
            self.assertIn("pool_endpoint_selected", kinds)
            refused = [e for e in events if e.kind == "pool_endpoint_refused"]
            self.assertTrue(
                any(e.detail.get("pool") == "primary" for e in refused),
                "primary endpoint failure was not recorded",
            )
            selected = [e for e in events if e.kind == "pool_endpoint_selected"]
            self.assertTrue(
                any(e.detail.get("pool") == "secondary" for e in selected),
                "secondary endpoint selection was not recorded",
            )
            # The rotation off the primary must leave a HEAL transition as evidence.
            self.assertIn("cycle_transition", kinds)
            self.assertEqual(pool.connections, 1)
        finally:
            if coord.client is not None:
                await coord.client.close()
            server.close()
            await server.wait_closed()

    def test_unavailable_sv2_security_provider_fails_over_without_downgrade(self) -> None:
        asyncio.run(self._sv2_configuration_failover())

    async def _sv2_configuration_failover(self) -> None:
        pool = _HandshakePool()
        server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
        live_port = server.sockets[0].getsockname()[1]

        coord = ProductionMiningCoordinator.__new__(ProductionMiningCoordinator)
        coord.endpoints = (
            PoolEndpoint(
                "sv2.example.invalid",
                34254,
                "sv2-primary",
                protocol="v2",
            ),
            PoolEndpoint("127.0.0.1", live_port, "v1-secondary"),
        )
        coord.username = "worker"
        coord.password = "x"
        coord.endpoint_index = 0
        coord.client = None
        coord.stratum_status_sink = None
        coord.production_connect_timeout = 0.05
        coord.production_request_timeout = 1.0
        coord.production_write_timeout = 0.1
        coord.production_outbound_queue_size = 8
        coord.sv2_channel_factory = None
        coord._refresh_work_identity = lambda: None
        coord._precompute_wake = asyncio.Event()
        coord.causal = CausalLedger()
        coord.cycle = MiningCycleLedger(on_event=coord._mirror_cycle_event)

        import os
        previous = os.environ.pop("PYTHIA_SV2_CHANNEL_FACTORY", None)
        try:
            client = await coord.connect_with_failover()
            self.assertEqual(client.endpoint.name, "v1-secondary")
            self.assertEqual(client.endpoint.protocol, "v1")
            self.assertEqual(coord.endpoint_index, 1)
            self.assertEqual(pool.connections, 1)

            refused = [
                event
                for event in coord.causal.events()
                if event.kind == "pool_endpoint_refused"
            ]
            self.assertTrue(
                any(
                    event.detail.get("pool") == "sv2-primary"
                    and event.detail.get("stage") == "sv2_configuration"
                    and event.detail.get("protocol") == "v2"
                    for event in refused
                ),
                "unavailable SV2 provider was not recorded as an SV2 refusal",
            )
            selected = [
                event
                for event in coord.causal.events()
                if event.kind == "pool_endpoint_selected"
            ]
            self.assertTrue(
                any(
                    event.detail.get("pool") == "v1-secondary"
                    and event.detail.get("protocol") == "v1"
                    for event in selected
                )
            )
        finally:
            if previous is not None:
                os.environ["PYTHIA_SV2_CHANNEL_FACTORY"] = previous
            if coord.client is not None:
                await coord.client.close()
            server.close()
            await server.wait_closed()

    def test_failover_records_refusal_and_selection_evidence(self) -> None:
        asyncio.run(self._failover_evidence())

    async def _failover_evidence(self) -> None:
        pool = _HandshakePool()
        server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
        live_port = server.sockets[0].getsockname()[1]
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
        probe.close()

        coord = ProductionMiningCoordinator.__new__(ProductionMiningCoordinator)
        coord.endpoints = (
            PoolEndpoint("127.0.0.1", dead_port, "primary"),
            PoolEndpoint("127.0.0.1", live_port, "secondary"),
        )
        coord.username = "worker"
        coord.password = "x"
        coord.endpoint_index = 0
        coord.client = None
        coord.stratum_status_sink = None
        coord.production_connect_timeout = 0.05
        coord.production_request_timeout = 1.0
        coord.production_write_timeout = 0.1
        coord.production_outbound_queue_size = 8
        coord._refresh_work_identity = lambda: None
        coord._precompute_wake = asyncio.Event()
        try:
            client = await coord.connect_with_failover()
            # The failover path self-heals its evidence machinery: the
            # primary refusal and the committed selection are both recorded
            # in a real causal ledger, and the coordinator is left fully
            # bound to the live secondary — not partially initialized.
            events = coord.causal.events()
            kinds = [event.kind for event in events]
            self.assertIn("pool_endpoint_refused", kinds)
            self.assertIn("pool_endpoint_selected", kinds)
            refused = next(e for e in events if e.kind == "pool_endpoint_refused")
            self.assertEqual(refused.detail["pool"], "primary")
            self.assertEqual(refused.detail["stage"], "connect")
            selected = next(e for e in events if e.kind == "pool_endpoint_selected")
            self.assertEqual(selected.detail["pool"], "secondary")
            self.assertEqual(selected.detail["attempt"], 2)
            self.assertEqual(len(selected.detail["previous_failures"]), 1)
            self.assertIs(coord.client, client)
            self.assertTrue(coord.client.connected)
            # Only configured endpoints were attempted: one dead port, one
            # live pool, one pool connection.
            self.assertEqual(pool.connections, 1)
        finally:
            if coord.client is not None:
                await coord.client.close()
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
