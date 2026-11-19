"""Regression tests for the 2026-11-19 security sweep (CodeQL alerts 49, 59, 60)."""

from __future__ import annotations

import json
import logging
import threading

import pytest

from chronus.fleet import auth as A
from chronus.fleet.errors import TransportError
from chronus.fleet.transport import FleetClient, FleetHTTPServer
from chronus.service.routers.console import _script_json

pytestmark = pytest.mark.real


def test_console_telemetry_json_cannot_close_the_script_element():
    hostile = {"tenant_id": "</script><script>alert(1)</script><!--", "n": 3, "amp": "a&b"}
    encoded = _script_json(hostile)
    assert "<" not in encoded and ">" not in encoded and "&" not in encoded
    # Still the same JavaScript/JSON value once parsed.
    assert json.loads(encoded) == hostile


def _boom(method, path, node_id, payload):
    raise RuntimeError("secret internal detail /var/lib/chronus/db")


def test_fleet_500_does_not_echo_internal_exception_text(caplog):
    token = A.new_token()
    server = FleetHTTPServer(("127.0.0.1", 0), _boom, A.FleetAuth(token))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = FleetClient(f"http://127.0.0.1:{server.server_address[1]}", A.FleetAuth(token), "node-1")
        with caplog.at_level(logging.ERROR, logger="chronus.fleet.transport"):
            with pytest.raises(TransportError) as caught:
                client.post("/v1/echo", {})
        assert caught.value.status == 500
        assert "secret internal detail" not in str(caught.value)
        assert str(caught.value) == "internal error"
        # The detail is retained for operators in the server log.
        assert any("secret internal detail" in (r.exc_text or "") or (r.exc_info and "secret internal detail" in str(r.exc_info[1]))
                   for r in caplog.records)
    finally:
        server.shutdown()
        server.server_close()
