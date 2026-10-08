"""Falsification and contract tests for the Stratum V2 Mining Protocol."""

import asyncio
import os
import unittest
from unittest.mock import patch

from chronus.mla1517.mining.stratum_adapter import StratumProofAdapter, SubscriptionState
from chronus.mla1517.mining.production_transport import ProductionMiningCoordinator
from chronus.mla1517.mining.stratum_v2_transport import (
    ProductionStratumV2Client,
    Sv2NotWritten,
    load_secure_channel_factory,
    normalize_extended_job,
)
from manifold_pool_coordinator import PoolEndpoint, parse_endpoint

from mining.stratum_v2 import (
    CHANNEL_MSG_BIT,
    MessageType,
    NewExtendedMiningJob,
    NewMiningJob,
    SetupConnection,
    SetupConnectionSuccess,
    StratumV2Client,
    Sv2Frame,
    Sv2ProtocolError,
    Sv2TransportError,
    SessionState,
    SubmitSharesSuccess,
    build_extended_header,
    submit_shares_extended,
    submit_shares_standard,
)


class FakeSecureChannel:
    secure = True

    def __init__(self):
        self.sent = []
        self.incoming = []
        self.opened = False
        self.closed = False

    async def open(self):
        self.opened = True

    async def send(self, payload):
        self.sent.append(payload)

    async def receive(self):
        if not self.incoming:
            raise RuntimeError("test transport has no queued frame")
        return self.incoming.pop(0)

    async def close(self):
        self.closed = True


class BlockingSecureChannel(FakeSecureChannel):
    async def receive(self):
        while not self.incoming:
            await asyncio.sleep(0.001)
        return self.incoming.pop(0)


class FailingSubmitSecureChannel(BlockingSecureChannel):
    def __init__(self, submit_error):
        super().__init__()
        self.submit_error = submit_error

    async def send(self, payload):
        # SetupConnection and OpenExtendedMiningChannel are the first two
        # writes. The third write is the share submission under test.
        if len(self.sent) >= 2:
            raise self.submit_error
        self.sent.append(payload)


def queue_ready_extended_session(channel):
    channel.incoming.append(SetupConnectionSuccess(2, 0).encode().encode())
    target = (1 << 256) - 1
    open_payload = (
        (1).to_bytes(4, "little")
        + (77).to_bytes(4, "little")
        + target.to_bytes(32, "little")
        + (4).to_bytes(2, "little")
        + b"\x01\xaa"
        + (0).to_bytes(4, "little")
    )
    channel.incoming.append(
        Sv2Frame(
            0,
            MessageType.OPEN_EXTENDED_MINING_CHANNEL_SUCCESS,
            open_payload,
        ).encode()
    )
    job_payload = (
        (12).to_bytes(4, "little")
        + b"\x00"
        + (0x20000000).to_bytes(4, "little")
        + b"\x00"
        + b"\x00"
        + (2).to_bytes(2, "little")
        + b"\x01\x02"
        + (2).to_bytes(2, "little")
        + b"\x03\x04"
    )
    channel.incoming.append(
        Sv2Frame(
            CHANNEL_MSG_BIT,
            MessageType.NEW_EXTENDED_MINING_JOB,
            (77).to_bytes(4, "little") + job_payload,
        ).encode()
    )
    prev_payload = (
        (77).to_bytes(4, "little")
        + (12).to_bytes(4, "little")
        + bytes.fromhex("22" * 32)
        + (100).to_bytes(4, "little")
        + (0x207FFFFF).to_bytes(4, "little")
    )
    channel.incoming.append(
        Sv2Frame(
            CHANNEL_MSG_BIT,
            MessageType.SET_NEW_PREV_HASH,
            prev_payload,
        ).encode()
    )


async def ready_production_v2_client(channel):
    queue_ready_extended_session(channel)
    client = ProductionStratumV2Client(
        PoolEndpoint("pool.example", 34254, "sv2-test", protocol="v2"),
        username="worker-1",
        password="x",
        channel_factory=lambda **_kwargs: channel,
        request_timeout=1.0,
    )
    await client.connect()
    deadline = asyncio.get_running_loop().time() + 1.0
    while not client.runtime_state.ready:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("SV2 normalized job did not become ready")
        await asyncio.sleep(0.001)
    return client


class TestStratumV2(unittest.TestCase):
    def test_frame_round_trip_and_incremental_decode(self):
        frame = Sv2Frame(0, MessageType.SETUP_CONNECTION_SUCCESS, b"\x02\x00\x00\x00\x00\x00")
        encoded = frame.encode()
        self.assertEqual(Sv2Frame.decode(encoded), frame)

        from mining.stratum_v2 import FrameDecoder

        decoder = FrameDecoder()
        self.assertEqual(decoder.feed(encoded[:2]), [])
        self.assertEqual(decoder.feed(encoded[2:]), [frame])
        decoder.finish()

    def test_channel_bit_is_required_and_rejects_wrong_routing(self):
        with self.assertRaises(Sv2ProtocolError):
            Sv2Frame(0, MessageType.SET_TARGET, b"\x00" * 36)
        with self.assertRaises(Sv2ProtocolError):
            Sv2Frame(CHANNEL_MSG_BIT, MessageType.SETUP_CONNECTION, b"")

    def test_setup_payload_is_spec_ordered_and_round_trips(self):
        setup = SetupConnection(
            endpoint_host="pool.example",
            endpoint_port=34254,
            vendor="PHIDATA2",
            hardware_version="PYTHIA",
            firmware="PYTHIA-SV2",
            device_id="worker-1",
        )
        self.assertEqual(SetupConnection.decode(setup.encode()), setup)
        self.assertEqual(setup.encode().payload[0], 0)
        self.assertEqual(int.from_bytes(setup.encode().payload[1:3], "little"), 2)

    def test_share_frames_use_channel_routing_and_little_endian_fields(self):
        standard = submit_shares_standard(7, 3, 11, 0x01020304, 0x05060708, 0x0A0B0C0D)
        self.assertEqual(standard.extension_type, CHANNEL_MSG_BIT)
        self.assertEqual(standard.message_type, MessageType.SUBMIT_SHARES_STANDARD)
        self.assertEqual(int.from_bytes(standard.payload[:4], "little"), 7)
        self.assertEqual(standard.payload[4:8], (3).to_bytes(4, "little"))

        extended = submit_shares_extended(7, 3, 11, 1, 2, 3, b"\xaa\xbb")
        self.assertEqual(extended.message_type, MessageType.SUBMIT_SHARES_EXTENDED)
        self.assertEqual(extended.payload[-3:], b"\x02\xaa\xbb")

    def test_production_endpoint_parser_marks_sv2_without_tls_downgrade(self):
        endpoint = parse_endpoint("stratum+v2://pool.example:34254", "sv2")
        self.assertEqual(endpoint.protocol, "v2")
        self.assertFalse(endpoint.tls)
        self.assertEqual(endpoint.host, "pool.example")
        self.assertEqual(endpoint.port, 34254)

    def test_secure_channel_factory_is_mandatory_for_configured_sv2(self):
        with patch.dict(os.environ, {"PYTHIA_SV2_CHANNEL_FACTORY": ""}):
            with self.assertRaisesRegex(
                Sv2TransportError,
                "PYTHIA_SV2_CHANNEL_FACTORY is absent",
            ):
                load_secure_channel_factory()

    def test_production_coordinator_refuses_insecure_sv2_without_fallback(self):
        async def run():
            channel = FakeSecureChannel()
            channel.secure = False
            coordinator = ProductionMiningCoordinator(
                [PoolEndpoint("pool.example", 34254, "sv2-only", protocol="v2")],
                username="worker-1",
                password="x",
                submit_enabled=False,
                sv2_channel_factory=lambda **_kwargs: channel,
            )
            with self.assertRaises(ConnectionError):
                await coordinator.connect_with_failover()
            self.assertIsNone(coordinator.client)
            self.assertEqual(channel.sent, [])
            self.assertTrue(channel.closed)

        asyncio.run(run())

    def test_production_coordinator_selects_authenticated_sv2_client(self):
        async def run():
            channel = BlockingSecureChannel()
            queue_ready_extended_session(channel)
            coordinator = ProductionMiningCoordinator(
                [PoolEndpoint("pool.example", 34254, "sv2-only", protocol="v2")],
                username="worker-1",
                password="x",
                submit_enabled=False,
                sv2_channel_factory=lambda **_kwargs: channel,
            )
            client = await coordinator.connect_with_failover()
            try:
                self.assertIsInstance(client, ProductionStratumV2Client)
                deadline = asyncio.get_running_loop().time() + 1.0
                while not client.runtime_state.ready:
                    if asyncio.get_running_loop().time() >= deadline:
                        self.fail("production coordinator did not receive canonical SV2 work")
                    await asyncio.sleep(0.001)
                identity, reason = coordinator._resolve_work_identity()
                self.assertIsNone(reason)
                self.assertIsNotNone(identity)
                self.assertEqual(identity.job_id, "12")
                self.assertEqual(client.status_snapshot()["protocol"], "stratum_v2")
                self.assertTrue(
                    client.status_snapshot()["sv2"]["authenticated_transport"]
                )
            finally:
                await client.close()

        asyncio.run(run())

    def test_remote_client_rejects_plaintext_transport_before_setup(self):
        channel = FakeSecureChannel()
        channel.secure = False
        client = StratumV2Client(
            channel,
            SetupConnection(endpoint_host="pool.example", endpoint_port=34254),
        )
        with self.assertRaises(Sv2TransportError):
            asyncio.run(client.open())
        self.assertTrue(channel.closed)
        self.assertEqual(client.state.value, "closed")
        self.assertEqual(channel.sent, [])

    def test_client_negotiates_channel_and_tracks_job(self):
        channel = FakeSecureChannel()
        channel.incoming.append(
            SetupConnectionSuccess(2, 0).encode().encode()
        )
        success_payload = (
            (9).to_bytes(4, "little")
            + (77).to_bytes(4, "little")
            + (100).to_bytes(32, "little")
            + b"\x01\xaa"
            + (0).to_bytes(4, "little")
        )
        channel.incoming.append(
            Sv2Frame(0, MessageType.OPEN_STANDARD_MINING_CHANNEL_SUCCESS, success_payload).encode()
        )
        job_payload = (
            (123).to_bytes(4, "little")
            + b"\x01"
            + (1700000000).to_bytes(4, "little")
            + (0x20000000).to_bytes(4, "little")
            + bytes(range(32))
        )
        channel.incoming.append(
            Sv2Frame(CHANNEL_MSG_BIT, MessageType.NEW_MINING_JOB, (77).to_bytes(4, "little") + job_payload).encode()
        )

        async def run():
            client = StratumV2Client(
                channel,
                SetupConnection(endpoint_host="pool.example", endpoint_port=34254),
            )
            success = await client.open()
            self.assertEqual(success.used_version, 2)
            channel_id = await client.open_standard_channel(
                9, 1000.0, (1 << 256) - 1, "worker-1"
            )
            self.assertEqual(channel_id, 77)
            event = await client.receive_event()
            self.assertIsInstance(event, NewMiningJob)
            self.assertEqual(event.job_id, 123)
            self.assertEqual(client.active_job_id, 123)
            await client.submit_standard(123, 4, 1700000000, 0x20000000)
            self.assertEqual(len(channel.sent), 3)
            await client.close()

        asyncio.run(run())

    def test_submit_success_payload_decodes_at_spec_length(self):
        payload = (
            (77).to_bytes(4, "little")
            + (3).to_bytes(4, "little")
            + (1).to_bytes(4, "little")
            + (4096).to_bytes(8, "little")
        )
        frame = Sv2Frame(
            CHANNEL_MSG_BIT,
            MessageType.SUBMIT_SHARES_SUCCESS,
            payload,
        )
        success = SubmitSharesSuccess.decode(frame)
        self.assertEqual(success.channel_id, 77)
        self.assertEqual(success.last_sequence_number, 3)
        self.assertEqual(success.new_submits_accepted_count, 1)
        self.assertEqual(success.new_shares_sum, 4096)

    def test_production_v2_adapter_runs_canonical_extended_share_voyage(self):
        async def run():
            channel = BlockingSecureChannel()
            channel.incoming.append(
                SetupConnectionSuccess(2, 0).encode().encode()
            )
            target = (1 << 256) - 1
            open_payload = (
                (1).to_bytes(4, "little")
                + (77).to_bytes(4, "little")
                + target.to_bytes(32, "little")
                + (4).to_bytes(2, "little")
                + b"\x01\xaa"
                + (0).to_bytes(4, "little")
            )
            channel.incoming.append(
                Sv2Frame(
                    0,
                    MessageType.OPEN_EXTENDED_MINING_CHANNEL_SUCCESS,
                    open_payload,
                ).encode()
            )

            # One extended job, then the SetNewPrevHash that activates it.
            job_payload = (
                (12).to_bytes(4, "little")
                + b"\x00"
                + (0x20000000).to_bytes(4, "little")
                + b"\x00"
                + b"\x00"
                + (2).to_bytes(2, "little")
                + b"\x01\x02"
                + (2).to_bytes(2, "little")
                + b"\x03\x04"
            )
            channel.incoming.append(
                Sv2Frame(
                    CHANNEL_MSG_BIT,
                    MessageType.NEW_EXTENDED_MINING_JOB,
                    (77).to_bytes(4, "little") + job_payload,
                ).encode()
            )
            prev_hash = bytes.fromhex("22" * 32)
            prev_payload = (
                (77).to_bytes(4, "little")
                + (12).to_bytes(4, "little")
                + prev_hash
                + (100).to_bytes(4, "little")
                + (0x207FFFFF).to_bytes(4, "little")
            )
            channel.incoming.append(
                Sv2Frame(
                    CHANNEL_MSG_BIT,
                    MessageType.SET_NEW_PREV_HASH,
                    prev_payload,
                ).encode()
            )

            client = ProductionStratumV2Client(
                PoolEndpoint(
                    "pool.example",
                    34254,
                    "sv2-test",
                    protocol="v2",
                ),
                username="worker-1",
                password="x",
                channel_factory=lambda **_kwargs: channel,
                request_timeout=1.0,
            )
            await client.connect()
            deadline = asyncio.get_running_loop().time() + 1.0
            while not client.runtime_state.ready:
                if asyncio.get_running_loop().time() >= deadline:
                    self.fail("SV2 normalized job did not become ready")
                await asyncio.sleep(0.001)

            proof = client.proof_adapter.validate_candidate(
                job_id="12",
                extranonce2="00000000",
                ntime="00000064",
                nonce=9,
            )
            self.assertEqual(len(proof.header), 80)

            submit_task = asyncio.create_task(
                client.submit(
                    ["worker-1", "12", "00000000", "00000064", "00000009"]
                )
            )
            while client.wire_writes_for("mining.submit") == 0:
                await asyncio.sleep(0.001)
            success_payload = (
                (77).to_bytes(4, "little")
                + (0).to_bytes(4, "little")
                + (1).to_bytes(4, "little")
                + (1).to_bytes(8, "little")
            )
            channel.incoming.append(
                Sv2Frame(
                    CHANNEL_MSG_BIT,
                    MessageType.SUBMIT_SHARES_SUCCESS,
                    success_payload,
                ).encode()
            )
            self.assertTrue(await submit_task)
            snapshot = client.status_snapshot()
            self.assertEqual(snapshot["protocol"], "stratum_v2")
            self.assertEqual(snapshot["counters"]["submitted"], 1)
            self.assertEqual(snapshot["counters"]["accepted"], 1)
            self.assertEqual(snapshot["counters"]["rejected"], 0)
            self.assertEqual(snapshot["submission"]["wire_writes"], 1)
            self.assertTrue(snapshot["sv2"]["authenticated_transport"])
            await client.close()

        asyncio.run(run())

    def test_ambiguous_sv2_send_failure_is_non_retryable_unknown(self):
        async def run():
            channel = FailingSubmitSecureChannel(
                ConnectionResetError("reset during encrypted send")
            )
            client = await ready_production_v2_client(channel)
            try:
                with self.assertRaises(ConnectionResetError):
                    await client.submit(
                        ["worker-1", "12", "00000000", "00000064", "00000009"]
                    )
                snapshot = client.status_snapshot()
                self.assertEqual(
                    snapshot["submission"]["last_result"],
                    "OUTCOME_UNKNOWN",
                )
                self.assertEqual(snapshot["counters"]["submitted"], 1)
                self.assertEqual(snapshot["counters"]["unknown"], 1)
                self.assertEqual(client.wire_writes_for("mining.submit"), 0)
            finally:
                await client.close()

        asyncio.run(run())

    def test_explicit_sv2_zero_write_proof_is_retryable_not_submitted(self):
        async def run():
            channel = FailingSubmitSecureChannel(
                Sv2NotWritten("secure channel proved zero write")
            )
            client = await ready_production_v2_client(channel)
            try:
                with self.assertRaises(Sv2NotWritten):
                    await client.submit(
                        ["worker-1", "12", "00000000", "00000064", "00000009"]
                    )
                snapshot = client.status_snapshot()
                self.assertEqual(
                    snapshot["submission"]["last_result"],
                    "NOT_SUBMITTED",
                )
                self.assertEqual(snapshot["counters"]["submitted"], 0)
                self.assertEqual(snapshot["counters"]["unknown"], 0)
                self.assertEqual(client.wire_writes_for("mining.submit"), 0)
                self.assertTrue(snapshot["ready"])
            finally:
                await client.close()

        asyncio.run(run())

    def test_client_refuses_stale_share_job(self):
        client = StratumV2Client(
            FakeSecureChannel(),
            SetupConnection(endpoint_host="pool.example", endpoint_port=34254),
        )

        async def run():
            client.state = SessionState.CHANNEL_OPEN
            client.channel_id = 1
            with self.assertRaisesRegex(Sv2ProtocolError, "unknown or stale"):
                await client.submit_standard(999, 0, 0, 0)

        asyncio.run(run())

    def test_extended_job_normalization_preserves_exact_header_bytes(self):
        job = NewExtendedMiningJob(
            channel_id=7,
            job_id=12,
            min_ntime=100,
            version=0x20000000,
            version_rolling_allowed=False,
            merkle_path=(bytes.fromhex("11" * 32), bytes.fromhex("33" * 32)),
            coinbase_tx_prefix=b"\x01\x02",
            coinbase_tx_suffix=b"\x03\x04",
        )
        prev_hash = bytes.fromhex("22" * 32)
        target = (1 << 255) - 1
        normalized = normalize_extended_job(
            job,
            prev_hash=prev_hash,
            nbits=0x1D00FFFF,
            ntime=100,
            target=target,
        )
        adapter = StratumProofAdapter()
        adapter.replace_subscription(
            SubscriptionState("aa", 2),
            invalidate_jobs=False,
        )
        adapter.set_exact_target(target, retarget_existing=False)
        adapter.on_job_received(normalized)
        header = adapter.build_header("12", "bbcc", "00000064", 9)
        native = build_extended_header(
            job,
            prev_hash=prev_hash,
            extranonce_prefix=b"\xaa",
            extranonce=b"\xbb\xcc",
            ntime=100,
            nbits=0x1D00FFFF,
            nonce=9,
        )
        self.assertEqual(header, native)
        self.assertEqual(len(header), 80)

    def test_extended_job_header_is_exactly_80_bytes(self):
        job = NewExtendedMiningJob(
            channel_id=7,
            job_id=12,
            min_ntime=100,
            version=0x20000000,
            version_rolling_allowed=False,
            merkle_path=(bytes.fromhex("11" * 32),),
            coinbase_tx_prefix=b"\x01\x02",
            coinbase_tx_suffix=b"\x03\x04",
        )
        header = build_extended_header(
            job,
            prev_hash=bytes.fromhex("22" * 32),
            extranonce_prefix=b"\xaa",
            extranonce=b"\xbb\xcc",
            ntime=100,
            nbits=0x1d00ffff,
            nonce=9,
        )
        self.assertEqual(len(header), 80)
        self.assertEqual(header[:4], (0x20000000).to_bytes(4, "little"))
        self.assertEqual(header[68:72], (100).to_bytes(4, "little"))
        self.assertEqual(header[72:76], (0x1d00ffff).to_bytes(4, "little"))
        self.assertEqual(header[76:], (9).to_bytes(4, "little"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
