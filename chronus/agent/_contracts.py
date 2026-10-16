"""Exact admission and canonical evidence encoding; no intelligence scores."""

from dataclasses import asdict, is_dataclass
from enum import Enum
from fractions import Fraction
import hashlib
import json


class ContractError(ValueError):
    pass


def integer(value, *, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ContractError("exact integer outside the admitted domain")
    return value


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 4096:
        raise ContractError("nonempty bounded text required")
    return value


def ratio(value):
    if type(value) not in (int, Fraction) or not 0 <= value <= 1:
        raise ContractError("exact probability/score in [0,1] required; no float coercion")
    return Fraction(value)


def wire(value):
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if is_dataclass(value):
        return wire(asdict(value))
    if isinstance(value, (tuple, list)):
        return [wire(v) for v in value]
    if isinstance(value, dict):
        if any(type(k) is not str for k in value):
            raise ContractError("JSON keys must be strings")
        return {k: wire(v) for k, v in value.items()}
    if value is None or type(value) in (str, int, bool):
        return value
    raise ContractError("unsupported evidence type; floats and arbitrary objects refused")


def canonical(value):
    data = json.dumps(
        wire(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    if len(data) > 65536:
        raise ContractError("evidence record exceeds 64KiB")
    return data


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ContractError("lowercase SHA256 evidence digest required")
    return value
