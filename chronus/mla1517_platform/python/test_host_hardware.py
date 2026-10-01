import asyncio
import contextlib
import json
import mmap
import os
import struct
import tempfile
import unittest
from pathlib import Path

from chronus.mla1517.hardware import MMIOBridge
from manifold_pool_coordinator import (
    ManifoldPoolCoordinator,
    PoolEndpoint,
    StratumClient,
    StratumTranslationError,
    format_mla1517_hot_state_candidate,
    format_mla1517_submission_params,
    format_mla1517_to_stratum_share,
    parse_endpoint,
)

ROOT = Path(__file__).parents[1]
LIBRARY = ROOT / "host" / "libmla1517_mmio.so"
VAULT_BASE = 0x1000
VAULT_STRIDE = 0x80
STATE_OFFSET = 0x08


class HardwareBridgeTests(unittest.TestCase):
    @unittest.skipUnless(LIBRARY.exists(), "build host/libmla1517_mmio.so first")
    def test_register_write_and_64_byte_vault_read(self):
        with tempfile.NamedTemporaryFile() as backing:
            with MMIOBridge(backing.name, library_path=LIBRARY) as bridge:
                bridge.set_difficulty_mask(0x3F)
                bridge.set_base_step(15)
                bridge.start()

                with open(backing.name, "r+b") as raw:
                    mapped = mmap.mmap(raw.fileno(), 0x2000)
                    state = bytes(range(64))
                    node = 7
                    base = VAULT_BASE + node * VAULT_STRIDE
                    struct.pack_into("<Q", mapped, base, 2)
                    mapped[base + STATE_OFFSET : base + STATE_OFFSET + 64] = state
                    mapped.flush()

                    record = bridge.poll_vault(timeout_ms=0)
                    self.assertIsNotNone(record)
                    assert record is not None
                    self.assertEqual(record.node_id, node)
                    self.assertEqual(record.sequence, 2)
                    self.assertEqual(record.state, state)
                    mapped.close()

    @unittest.skipUnless(LIBRARY.exists(), "build host/libmla1517_mmio.so first")
    def test_dual_output_publishes_path_a_and_path_b(self):
        with tempfile.NamedTemporaryFile() as backing:
            with tempfile.NamedTemporaryFile() as ring_file:
                ring_path = ring_file.name
                with MMIOBridge(backing.name, library_path=LIBRARY) as bridge:
                    with open(backing.name, "r+b") as raw:
                        mapped = mmap.mmap(raw.fileno(), 0x2000)
                        state = bytes(range(64))
                        base = VAULT_BASE + 2 * VAULT_STRIDE
                        struct.pack_into("<Q", mapped, base, 2)
                        mapped[base + STATE_OFFSET : base + STATE_OFFSET + 64] = state
                        mapped.flush()
                        record = bridge.poll_vault_to_ring(ring_path, timeout_ms=0, capacity=8)
                        self.assertIsNotNone(record)
                        self.assertEqual(record.state, state)
                        mapped.close()
                with open(ring_path, "rb") as raw:
                    ring = mmap.mmap(raw.fileno(), 192 + (8 * 64), access=mmap.ACCESS_READ)
                    self.assertEqual(struct.unpack_from("<Q", ring, 64)[0], 1)
                    ring.close()

    @unittest.skipUnless(LIBRARY.exists(), "build host/libmla1517_mmio.so first")
    def test_supervisor_register_controls(self):
        with tempfile.NamedTemporaryFile() as backing:
            with MMIOBridge(backing.name, library_path=LIBRARY) as bridge:
                bridge.update_polyhedral_mask(0x12345678)
                bridge.quarantine_lane(4)
                bridge.quarantine_lane(4, False)
                bridge.quarantine_lane(4)
                with open(backing.name, "rb") as raw:
                    mapped = mmap.mmap(raw.fileno(), 0x2000, access=mmap.ACCESS_READ)
                    self.assertEqual(struct.unpack_from("<I", mapped, 0x28)[0], 0x12345678)
                    self.assertEqual(struct.unpack_from("<I", mapped, 0x2C)[0], 0xFFFFFFEF)
                    mapped.close()


class StratumCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        async def handler(reader, writer):
            try:
                while line := await reader.readline():
                    request = json.loads(line)
                    self.requests.append(request)
                    if request["method"] == "mining.subscribe":
                        response = {
                            "id": request["id"],
                            "result": [[], "00", 4],
                            "error": None,
                        }
                        writer.write((json.dumps(response) + "\n").encode())
                        await writer.drain()
                        notify = {
                            "id": None,
                            "method": "mining.notify",
                            "params": [
                                "job-1",
                                "ab" * 32,
                                "aa",
                                "bb",
                                [],
                                "00000001",
                                "1a0bb4f4",
                                "5f3f2a1e",
                                True,
                            ],
                        }
                        writer.write((json.dumps(notify) + "\n").encode())
                        await writer.drain()
                    elif request["method"] == "mining.authorize":
                        response = {
                            "id": request["id"],
                            "result": True,
                            "error": None,
                        }
                        writer.write((json.dumps(response) + "\n").encode())
                        await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        self.server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.endpoint = PoolEndpoint("127.0.0.1", port, "local")

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_connection_job_receive_and_safe_translation_boundary(self):
        client = StratumClient(self.endpoint, username="worker", password="x")
        await client.connect()
        try:
            await asyncio.sleep(0.01)
            job = client.latest_job()
            self.assertIsNotNone(job)
            with self.assertRaises(StratumTranslationError):
                format_mla1517_submission_params(bytes(64), worker_name="worker", job=job)
        finally:
            await client.close()

    async def test_failover_selects_second_endpoint(self):
        bad = PoolEndpoint("127.0.0.1", 1, "bad")
        coordinator = ManifoldPoolCoordinator(
            [bad, self.endpoint],
            username="worker",
            password="x",
        )
        client = await coordinator.connect_with_failover()
        self.assertEqual(client.endpoint.name, "local")
        await client.close()

    @unittest.skipIf(os.name == "nt", "AF_UNIX control socket requires a POSIX host")
    async def test_salamander_failover_ipc_is_acknowledged(self):
        socket_path = str(Path(tempfile.mkdtemp()) / "coordinator.sock")
        coordinator = ManifoldPoolCoordinator(
            [self.endpoint, self.endpoint],
            username="worker",
            password="x",
        )
        coordinator.control_socket_path = socket_path
        await coordinator._start_control_server()
        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            writer.write(
                b'{"op":"failover","target":"secondary","reason":"salamander","dwell_ms":10000}\n'
            )
            await writer.drain()
            reply = json.loads((await reader.readline()).decode())
            self.assertEqual(reply["status"], "ok")
            self.assertEqual(coordinator.endpoint_index, 1)
            writer.close()
            await writer.wait_closed()
        finally:
            coordinator._control_server.close()
            await coordinator._control_server.wait_closed()
            with contextlib.suppress(FileNotFoundError):
                os.unlink(socket_path)


class PureProtocolTests(unittest.TestCase):
    def test_endpoint_parser(self):
        self.assertEqual(parse_endpoint("pool.example:3333", "x").port, 3333)
        self.assertEqual(parse_endpoint("[::1]:3333", "x").host, "::1")
        self.assertEqual(parse_endpoint("[::1]:3333", "x").port, 3333)
        with self.assertRaises(ValueError):
            parse_endpoint("pool.example", "x")
        with self.assertRaises(ValueError):
            parse_endpoint("2001:db8::1:3333", "x")

    def test_endpoint_parser_schemes(self):
        # TLS schemes force TLS; tcp schemes force plaintext; bare endpoints
        # keep the caller's default; unknown schemes are rejected.
        self.assertTrue(parse_endpoint("stratum+ssl://pool.example:3333", "x").tls)
        self.assertTrue(parse_endpoint("stratum+tls://pool.example:3333", "x").tls)
        self.assertTrue(parse_endpoint("stratum+ssl://pool.example:3333", "x", tls=False).tls)
        self.assertFalse(parse_endpoint("stratum+tcp://pool.example:3333", "x").tls)
        self.assertFalse(parse_endpoint("stratum+tcp://pool.example:3333", "x", tls=True).tls)
        self.assertEqual(
            parse_endpoint("stratum+ssl://pool.example:3333", "x").host, "pool.example"
        )
        self.assertEqual(parse_endpoint("stratum+ssl://pool.example:3333", "x").port, 3333)
        self.assertTrue(parse_endpoint("pool.example:3333", "x", tls=True).tls)
        self.assertFalse(parse_endpoint("pool.example:3333", "x").tls)
        with self.assertRaises(ValueError):
            parse_endpoint("http://pool.example:3333", "x")
        with self.assertRaises(ValueError):
            parse_endpoint("stratum+ssl://pool.example", "x")

    def test_requested_legacy_struct_translation(self):
        # D1 nonce=0x01020304, D10=-1, D11 time=0x11223344.
        raw = struct.pack(
            "<IffIIfIIfiII",
            0x01020304,
            0.0,
            0.0,
            0,
            0,
            0.0,
            0,
            0,
            0.0,
            -1,
            0x11223344,
            0,
        ) + bytes(16)
        payload = json.loads(
            format_mla1517_to_stratum_share(
                raw,
                "worker",
                "job-1",
                "00000001",
            )
        )
        self.assertEqual(payload["method"], "mining.submit")
        self.assertEqual(
            payload["params"],
            ["worker", "job-1", "00000001", "11223344", "01020304"],
        )

    def test_current_hot_state_candidate_uses_actual_abi(self):
        words = [0] * 14
        words[8] = 0xFFFFFFFF  # D10 = -1 in the packed u32 field.
        words[9] = 0x11223344  # D11 time state.
        raw = struct.pack("<Q14I", 0x01020304, *words)
        payload = json.loads(
            format_mla1517_hot_state_candidate(
                raw,
                "worker",
                "job-1",
                "00000001",
            )
        )
        self.assertEqual(payload["params"][-2:], ["11223344", "01020304"])

    def test_invalid_legacy_cassini_is_rejected(self):
        raw = bytearray(64)
        struct.pack_into("<i", raw, 32, 0)
        with self.assertRaises(ValueError):
            format_mla1517_to_stratum_share(raw, "worker", "job-1", "00000001")


if __name__ == "__main__":
    unittest.main()
