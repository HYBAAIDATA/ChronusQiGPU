"""Restricted deterministic JSON encoding for signed evidence.

NOT full RFC 8785 conformance: integers must be within I-JSON safe range,
floats and surrogate codepoints are rejected, and keys are BMP-only.
"""
from __future__ import annotations
import json
from typing import Any

class NonCanonical(ValueError):
    pass

def _check(obj: Any, path: str = "$") -> None:
    if obj is None or type(obj) in (str, bool):
        if type(obj) is str and any(0xD800 <= ord(c) <= 0xDFFF for c in obj):
            raise NonCanonical(f"surrogate at {path}")
        return
    if type(obj) is int:
        if not -(2**53-1) <= obj <= 2**53-1:
            raise NonCanonical(f"unsafe integer at {path}")
        return
    if type(obj) is dict:
        for key, value in obj.items():
            if type(key) is not str or any(ord(c)>0xFFFF or 0xD800<=ord(c)<=0xDFFF for c in key):
                raise NonCanonical(f"invalid key at {path}")
            _check(value, f"{path}.{key}")
        return
    if type(obj) in (list, tuple):
        for i, value in enumerate(obj):
            _check(value, f"{path}[{i}]")
        return
    raise NonCanonical(f"unsupported type {type(obj).__name__} at {path}")

def canonical_bytes(obj: Any) -> bytes:
    _check(obj)
    return json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
