# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
import pytest

from chronus.fleet.auth import FleetAuth, new_token
from chronus.fleet.errors import TransportError
from chronus.fleet.native_transport import NATIVE_TRANSPORT_ENV
from chronus.fleet.transport import FleetClient

pytestmark = pytest.mark.real


def test_explicit_native_transport_missing_library_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv(NATIVE_TRANSPORT_ENV, str(tmp_path / "missing-library"))
    with pytest.raises(TransportError, match="native fleet transport unavailable"):
        FleetClient("http://127.0.0.1:8740", FleetAuth(new_token()), "node")
