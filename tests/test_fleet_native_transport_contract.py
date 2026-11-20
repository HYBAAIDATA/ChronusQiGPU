# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
import os

import pytest

from chronus.fleet.auth import FleetAuth, new_token
from chronus.fleet.errors import TransportError
from chronus.fleet.native_transport import NATIVE_TRANSPORT_ENV, _request_url
from chronus.fleet.transport import FleetClient

pytestmark = pytest.mark.real


def test_explicit_native_transport_missing_library_fails_closed(tmp_path):
    previous = os.environ.get(NATIVE_TRANSPORT_ENV)
    os.environ[NATIVE_TRANSPORT_ENV] = str(tmp_path / "missing-library")
    try:
        with pytest.raises(TransportError, match="native fleet transport unavailable"):
            FleetClient("http://127.0.0.1:8740", FleetAuth(new_token()), "node")
    finally:
        if previous is None:
            os.environ.pop(NATIVE_TRANSPORT_ENV, None)
        else:
            os.environ[NATIVE_TRANSPORT_ENV] = previous


def test_native_url_idna_preserves_signed_path_and_ipv6():
    assert _request_url("https://bücher.example:8740", "/v1/a%2Fb?x=1") == b"https://xn--bcher-kva.example:8740/v1/a%2Fb?x=1"
    assert _request_url("https://[::1]:8740", "/v1/ping") == b"https://[::1]:8740/v1/ping"
    with pytest.raises(TransportError, match="URL encoding"):
        _request_url("https://localhost:8740", "/v1/é")
