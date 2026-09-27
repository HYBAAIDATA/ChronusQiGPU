"""Falsification and contract tests for the Stratum V2 Mining Protocol."""

import asyncio
import unittest

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
