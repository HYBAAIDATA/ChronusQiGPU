# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
import os

import pytest

from chronus.fleet.auth import FleetAuth, new_token
from chronus.fleet.errors import TransportError
from chronus.fleet.native_transport import NATIVE_TRANSPORT_ENV
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
