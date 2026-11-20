# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Mutual HMAC authentication, replay and skew protection, impostor detection and TLS."""

import threading
import unittest
from pathlib import Path

from chronus.fleet import auth as A
from chronus.fleet.errors import AuthenticationError, TransportError
from chronus.fleet.transport import FleetClient, FleetHTTPServer
from tests.fleet_support import filesystem_keeps_modes, state_dir
import pytest

pytestmark = pytest.mark.real


def echo(method, path, node_id, payload):
    if path == "/missing":
        return 404, {"error": "nope"}
    return 200, {"method": method, "path": path, "node": node_id, "payload": payload}


class Server:
    def __init__(self, token, tls=None):
        self.server = FleetHTTPServer(("127.0.0.1", 0), echo, A.FleetAuth(token), tls)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self.server.server_address[1]

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class HMACTests(unittest.TestCase):
    def setUp(self):
        self.token = A.new_token()
        self.auth = A.FleetAuth(self.token)

    def test_request_round_trip_and_tampering(self):
        headers = self.auth.sign_request("POST", "/v1/lease", "node-1", b'{"a":1}')
        node, nonce = self.auth.verify_request("POST", "/v1/lease", headers, b'{"a":1}', A.ReplayCache())
        self.assertEqual((node, nonce), ("node-1", headers[A.H_NONCE]))
        for method, path, body in (("GET", "/v1/lease", b'{"a":1}'), ("POST", "/v1/join", b'{"a":1}'), ("POST", "/v1/lease", b'{"a":2}')):
            with self.assertRaises(AuthenticationError):
                self.auth.verify_request(method, path, headers, body, A.ReplayCache())

    def test_wrong_token_replay_skew_and_missing_headers(self):
        headers = self.auth.sign_request("POST", "/v1/x", "n", b"")
        with self.assertRaises(AuthenticationError):
            A.FleetAuth(A.new_token()).verify_request("POST", "/v1/x", headers, b"", A.ReplayCache())
        cache = A.ReplayCache()
        self.auth.verify_request("POST", "/v1/x", headers, b"", cache)
        with self.assertRaises(AuthenticationError):
            self.auth.verify_request("POST", "/v1/x", headers, b"", cache)
        old = dict(headers)
        old[A.H_TIME] = str(int(headers[A.H_TIME]) - 2 * A.MAX_CLOCK_SKEW_NS)
        old[A.H_MAC] = self.auth._mac("REQ", "POST", "/v1/x", "n", old[A.H_TIME], old[A.H_NONCE], old[A.H_BODY])
        with self.assertRaises(AuthenticationError):
            self.auth.verify_request("POST", "/v1/x", old, b"", A.ReplayCache())
        with self.assertRaises(AuthenticationError):
            self.auth.verify_request("POST", "/v1/x", {}, b"", A.ReplayCache())

    def test_responses_are_bound_to_the_request_nonce(self):
        signed = self.auth.sign_response("n1", 200, b"{}")
        self.auth.verify_response("n1", 200, signed, b"{}")
        for nonce, status, body in (("n2", 200, b"{}"), ("n1", 500, b"{}"), ("n1", 200, b"{ }")):
            with self.assertRaises(AuthenticationError):
                self.auth.verify_response(nonce, status, signed, body)

    def test_short_tokens_are_refused(self):
        with self.assertRaises(AuthenticationError):
            A.load_token("too-short")

    def test_token_files(self):
        with state_dir() as tmp:
            path = A.write_token_file(Path(tmp) / "token", self.token)
            self.assertEqual(A.load_token(token_file=path), self.token)
            if filesystem_keeps_modes(tmp):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class TransportTests(unittest.TestCase):
    def test_authenticated_round_trip(self):
        token = A.new_token()
        with Server(token) as port:
            client = FleetClient(f"http://127.0.0.1:{port}", A.FleetAuth(token), "node-9")
            reply = client.post("/v1/echo", {"x": [1, 2]})
            self.assertEqual(reply, {"method": "POST", "path": "/v1/echo", "node": "node-9", "payload": {"x": [1, 2]}})
            with self.assertRaises(TransportError) as caught:
                client.get("/missing")
            self.assertEqual(caught.exception.status, 404)

    def test_a_client_without_the_token_is_rejected(self):
        with Server(A.new_token()) as port:
            with self.assertRaises(AuthenticationError):
                FleetClient(f"http://127.0.0.1:{port}", A.FleetAuth(A.new_token()), "intruder").get("/v1/status")

    def test_an_impostor_coordinator_is_rejected(self):
        """A server that accepts the request but lacks the token cannot MAC its answer."""
        token = A.new_token()

        class Impostor(A.FleetAuth):
            def __init__(self):
                super().__init__(A.new_token())
                self.real = A.FleetAuth(token)

            def verify_request(self, *args):
                return self.real.verify_request(*args)

        impostor = FleetHTTPServer(("127.0.0.1", 0), echo, Impostor(), None)
        thread = threading.Thread(target=impostor.serve_forever, daemon=True)
        thread.start()
        try:
            client = FleetClient(f"http://127.0.0.1:{impostor.server_address[1]}", A.FleetAuth(token), "node")
            with self.assertRaises(AuthenticationError) as caught:
                client.get("/v1/status")
            self.assertIn("impostor", str(caught.exception))
        finally:
            impostor.shutdown()
            impostor.server_close()

    def test_tls_round_trip_with_a_generated_certificate(self):
        token = A.new_token()
        with state_dir() as tmp:
            cert, key = A.generate_self_signed(Path(tmp) / "tls", ["127.0.0.1", "localhost"])
            with Server(token, A.tls_server_context(cert, key)) as port:
                client = FleetClient(f"https://127.0.0.1:{port}", A.FleetAuth(token), "node", tls_ca=str(cert))
                self.assertEqual(client.get("/v1/ping")["path"], "/v1/ping")
                other_cert, _ = A.generate_self_signed(Path(tmp) / "other-tls", ["127.0.0.1", "localhost"])
                wrong_ca = FleetClient(f"https://127.0.0.1:{port}", A.FleetAuth(token), "node", tls_ca=str(other_cert))
                with self.assertRaises(TransportError):
                    wrong_ca.get("/v1/ping")
                plain = FleetClient(f"https://127.0.0.1:{port}", A.FleetAuth(token), "node")
                with self.assertRaises(TransportError):
                    plain.get("/v1/ping")

    def test_bad_urls_are_refused(self):
        auth = A.FleetAuth(A.new_token())
        for url in ("ftp://x:1", "http://host:1/path"):
            with self.assertRaises(TransportError):
                FleetClient(url, auth, "n")
        with self.assertRaises(TransportError):
            FleetClient("http://127.0.0.1:1", auth, "n", tls_ca="cert.pem")


if __name__ == "__main__":
    unittest.main()
