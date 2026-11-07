"""Shared wire format and validation for exact PV lattice workloads."""

import json
from typing import Any

from chronus.backends.lattice import LatticeOverflowError, PhiElement

INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
MAX_ELEMENTS = 4096
MAX_DECIMAL_DIGITS = 1024


def wire_integer(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        if value.bit_length() <= 3402 and len(str(abs(value))) <= MAX_DECIMAL_DIGITS:
            return value
    if isinstance(value, str):
        digits = value[1:] if value.startswith("-") else value
        if 1 <= len(digits) <= MAX_DECIMAL_DIGITS and digits.isascii() and digits.isdecimal():
            return int(value)
    raise ValueError(f"coefficients must be integers or decimal strings of at most {MAX_DECIMAL_DIGITS} digits")


def checked_int64(value: int) -> int:
    if not INT64_MIN <= value <= INT64_MAX:
        raise LatticeOverflowError("lattice coefficient or fixed-width intermediate exceeds int64")
    return value


def parse_lattice_values(raw_values: Any) -> list[PhiElement]:
    if not isinstance(raw_values, list) or not 1 <= len(raw_values) <= MAX_ELEMENTS:
        raise ValueError(f"values must contain 1 to {MAX_ELEMENTS} elements")
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
    if len(payload) > 1024 * 1024:
        raise ValueError("payload exceeds 1 MiB")
    try:
        request = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("payload must be a UTF-8 JSON object") from exc
    if not isinstance(request, dict):
        raise ValueError("payload must be a JSON object")
    order = request.get("order")
    if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 360:
        raise ValueError("order must be an integer between 0 and 360")
    return parse_lattice_values(request.get("values")), order


def serialize_lattice(values: list[PhiElement]) -> list[dict[str, str]]:
    return [
        {"a": str(value.a), "b": str(value.b), "denominator": str(value.denominator)}
        for value in values
    ]
