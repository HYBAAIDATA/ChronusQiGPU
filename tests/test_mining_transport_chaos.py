"""Deterministic chaos tests for production mining transport boundaries."""

import asyncio
import unittest

from mining.stratum_v2 import (
    FrameDecoder,
    SetupConnection,
    StratumV2Client,
    Sv2ProtocolError,
    Sv2TransportError,
    SessionState,
)


class _ChaosChannel:
    secure = True

    def __init__(self, *, receive_payload=b"", send_error=None):
        self.receive_payload = receive_payload
        self.send_error = send_error
        self.opened = False
        self.closed = False

    async def open(self):
        self.opened = True

    async def send(self, payload):
        if self.send_error is not None:
            raise self.send_error

    async def receive(self):
        return self.receive_payload

    async def close(self):
        self.closed = True


class MiningTransportChaosTests(unittest.TestCase):
    def test_truncated_frame_is_rejected_at_transport_end(self):
        decoder = FrameDecoder()
        self.assertEqual(decoder.feed(b"\x00\x00\x01"), [])
        with self.assertRaises(Sv2ProtocolError):
            decoder.finish()

    def test_peer_drop_during_setup_closes_session(self):
        async def run():
            channel = _ChaosChannel(receive_payload=b"")
            client = StratumV2Client(
                channel,
                SetupConnection(endpoint_host="pool.example", endpoint_port=3333),
            )
            with self.assertRaises(Sv2TransportError):
                await client.open()
            self.assertTrue(channel.closed)
            self.assertEqual(client.state, SessionState.CLOSED)

        asyncio.run(run())

    def test_write_failure_during_setup_closes_session(self):
        async def run():
            channel = _ChaosChannel(send_error=ConnectionResetError("peer reset"))
            client = StratumV2Client(
                channel,
                SetupConnection(endpoint_host="pool.example", endpoint_port=3333),
            )
            with self.assertRaises(ConnectionResetError):
                await client.open()
            self.assertTrue(channel.closed)
            self.assertEqual(client.state, SessionState.CLOSED)

        asyncio.run(run())

    def test_plaintext_transport_is_closed_without_setup_write(self):
        async def run():
            channel = _ChaosChannel()
            channel.secure = False
            client = StratumV2Client(
                channel,
                SetupConnection(endpoint_host="pool.example", endpoint_port=3333),
            )
            with self.assertRaises(Sv2TransportError):
                await client.open()
            self.assertTrue(channel.closed)
            self.assertEqual(client.state, SessionState.CLOSED)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
