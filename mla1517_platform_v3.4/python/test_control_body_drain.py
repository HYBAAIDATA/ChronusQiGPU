"""Oversized request bodies are drained (bounded) before the 413 is written."""

import io
import unittest

import control_api


class _Reader(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.requested = 0

    def read(self, size: int = -1) -> bytes:
        chunk = super().read(size)
        self.requested += len(chunk)
        return chunk


def _handler(length: int, payload: bytes):
    handler = control_api._Handler.__new__(control_api._Handler)
    handler.headers = {"Content-Length": str(length)}
    handler.rfile = _Reader(payload)
    handler.close_connection = False
    return handler


class BodyDrainTests(unittest.TestCase):
    def test_oversized_body_is_drained_before_refusal(self) -> None:
        size = control_api._TOE_MAX_BODY_BYTES + 1024
        handler = _handler(size, b"x" * size)
        self.assertEqual(handler._read_json_body(), (None, "body_too_large"))
        self.assertEqual(handler.rfile.requested, size)
        self.assertFalse(handler.close_connection)

    def test_drain_is_bounded_and_closes_past_the_cap(self) -> None:
        cap = control_api._TOE_MAX_BODY_BYTES * 4
        handler = _handler(10**12, b"x" * (cap + 4096))
        self.assertEqual(handler._read_json_body(), (None, "body_too_large"))
        self.assertEqual(handler.rfile.requested, cap)
        self.assertTrue(handler.close_connection)

    def test_small_body_still_parses(self) -> None:
        handler = _handler(len(b'{"a": 1}'), b'{"a": 1}')
        self.assertEqual(handler._read_json_body(), ({"a": 1}, None))


if __name__ == "__main__":
    unittest.main()
