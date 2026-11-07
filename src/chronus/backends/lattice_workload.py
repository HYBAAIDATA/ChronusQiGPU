"""Shared wire format and validation for exact PV lattice workloads."""

import json
from typing import Any

from chronus.backends.lattice import LatticeOverflowError, PhiElement
from chronus.config import runtime_bounds

INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


def _bounds() -> dict[str, int]:
    return runtime_bounds()


def wire_integer(value: Any) -> int:
    max_digits = _bounds()["max_decimal_digits"]
    if isinstance(value, int) and not isinstance(value, bool):
        if value.bit_length() <= 3402 and len(str(abs(value))) <= max_digits:
            return value
    if isinstance(value, str):
        digits = value[1:] if value.startswith("-") else value
        if 1 <= len(digits) <= max_digits and digits.isascii() and digits.isdecimal():
            return int(value)
    raise ValueError(f"coefficients must be integers or decimal strings of at most {max_digits} digits")


def checked_int64(value: int) -> int:
    if not INT64_MIN <= value <= INT64_MAX:
        raise LatticeOverflowError("lattice coefficient or fixed-width intermediate exceeds int64")
    return value


def parse_lattice_values(raw_values: Any) -> list[PhiElement]:
    max_elements = _bounds()["max_lattice_elements"]
    if not isinstance(raw_values, list) or not 1 <= len(raw_values) <= max_elements:
        raise ValueError(f"values must contain 1 to {max_elements} elements")
    values = []
    for value in raw_values:
        if not isinstance(value, dict) or set(value) != {"a", "b", "denominator"}:
            raise ValueError("each value must contain a, b and denominator")
        element = PhiElement(
            wire_integer(value["a"]), wire_integer(value["b"]),
            wire_integer(value["denominator"]),
        )
        checked_int64(element.a)
        checked_int64(element.b)
        values.append(element)
    return values


def parse_lattice_workload(payload: bytes) -> tuple[list[PhiElement], int]:
    bounds = _bounds()
    if len(payload) > bounds["max_payload_bytes"]:
        raise ValueError(f"payload exceeds {bounds['max_payload_bytes']} bytes")
    try:
        request = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("payload must be a UTF-8 JSON object") from exc
    if not isinstance(request, dict):
        raise ValueError("payload must be a JSON object")
    order = request.get("order")
    max_order = bounds["max_pv_order"]
    if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= max_order:
        raise ValueError(f"order must be an integer between 0 and {max_order}")
    return parse_lattice_values(request.get("values")), order


def serialize_lattice(values: list[PhiElement]) -> list[dict[str, str]]:
    return [
        {"a": str(value.a), "b": str(value.b), "denominator": str(value.denominator)}
        for value in values
    ]
