"""Restricted canonical JSON: deterministic UTF-8, no floating point.

This is a documented restricted schema, not a general RFC 8785 implementation.
"""
from __future__ import annotations
import json
from typing import Any

def _validate(value: Any) -> None:
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is list:
        for item in value:
            _validate(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("canonical JSON keys must be strings")
            _validate(item)
        return
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")

def canonical_bytes(value: Any) -> bytes:
    _validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
