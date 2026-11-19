# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Explicit C++ libcurl transport for the existing authenticated fleet protocol.

The standard FleetAuth still signs/validates every byte. ctypes.CDLL releases
the GIL during native network I/O. No Python transport retry or fallback.
"""
from __future__ import annotations

import ctypes
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from chronus.fleet.auth import H_BODY, H_MAC
from chronus.fleet.errors import TransportError

NATIVE_TRANSPORT_ENV = "CHRONUS_FLEET_NATIVE_TRANSPORT"


class NativeHTTPTransport:
    def __init__(self, library: str) -> None:
        try:
            path = Path(library).expanduser().resolve(strict=True)
            lib = ctypes.CDLL(str(path))
            lib.chronus_fleet_transport_abi.argtypes = []
            lib.chronus_fleet_transport_abi.restype = ctypes.c_int
            if lib.chronus_fleet_transport_abi() != 1:
                raise TransportError("unsupported native fleet transport ABI")
            lib.chronus_fleet_http.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p),
                ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p,
                ctypes.c_long, ctypes.c_size_t,
            ]
            lib.chronus_fleet_http.restype = ctypes.c_void_p
            for name, restype in (
                ("status", ctypes.c_long), ("size", ctypes.c_size_t),
                ("body", ctypes.c_void_p), ("mac", ctypes.c_char_p),
                ("digest", ctypes.c_char_p), ("free", None),
            ):
                fn = getattr(lib, "chronus_fleet_http_" + name)
                fn.argtypes = [ctypes.c_void_p]
                fn.restype = restype
        except (OSError, AttributeError) as exc:
            raise TransportError("configured native fleet transport unavailable") from exc
        self._lib = lib

    def request(self, base_url: str, method: str, path: str, headers: Mapping[str, str],
                body: bytes, tls_ca: str | None, timeout: float, limit: int) -> tuple[int, dict[str, str], bytes]:
        if (method not in ("GET", "POST") or not path.startswith("/") or "#" in path
                or any(ord(c) <= 32 or ord(c) == 127 for c in path)):
            raise TransportError("invalid native fleet method or request path")
        if not math.isfinite(timeout) or not 0 < timeout <= (2**31 - 1) / 1000:
            raise TransportError("invalid native fleet timeout")
        rendered = []
        for key, value in headers.items():
            line = f"{key}: {value}"
            if any(ord(c) < 32 or ord(c) == 127 for c in line):
                raise TransportError("invalid native fleet header")
            rendered.append(line.encode("latin-1"))
        array = (ctypes.c_char_p * len(rendered))(*rendered)
        url = (base_url + path).encode("ascii")
        ca = os.fsencode(Path(tls_ca).expanduser()) if tls_ca else None
        lib = self._lib
        response = lib.chronus_fleet_http(url, method.encode("ascii"), array, len(rendered),
                                          body, len(body), ca, max(1, math.ceil(timeout * 1000)), limit)
        if not response:
            raise TransportError("native fleet request failed (transport, TLS or response limit)")
        try:
            size = lib.chronus_fleet_http_size(response)
            if size > limit:
                raise TransportError("native fleet response exceeds configured byte limit")
            data = ctypes.string_at(lib.chronus_fleet_http_body(response), size)
            response_headers = {}
            for key, value in ((H_MAC, lib.chronus_fleet_http_mac(response)),
                               (H_BODY, lib.chronus_fleet_http_digest(response))):
                if value:
                    response_headers[key] = value.decode("ascii")
            return lib.chronus_fleet_http_status(response), response_headers, data
        finally:
            lib.chronus_fleet_http_free(response)


@lru_cache(maxsize=4)
def load_native_transport(library: str) -> NativeHTTPTransport:
    return NativeHTTPTransport(library)
