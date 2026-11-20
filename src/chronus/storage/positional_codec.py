"""Exact positional base-five byte representation for explicit CHRN trials.

Four coefficients per input byte in ascending power order, one octet each.
This is an expanding representation, not the owner-approved canonical ID 1.
"""
from __future__ import annotations

from chronus.storage import chrn_frame

PARAM_ID = 0xFFFFFFFD
BLOCK_SIZE = 256


def encode_byte(value: int) -> tuple[int, int, int, int]:
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError("byte outside 0..255")
    digits = []
    for _ in range(4):
        value, digit = divmod(value, 5)
        digits.append(digit)
    return tuple(digits)


def decode_byte(digits) -> int:
    if not isinstance(digits, (list, tuple, bytes)) or len(digits) != 4:
        raise ValueError("exactly four digits required")
    if any(type(digit) is not int or not 0 <= digit < 5 for digit in digits):
        raise ValueError("invalid digit")
    result = sum(digit * 5**i for i,digit in enumerate(digits))
    if result > 255:
        raise ValueError("noncanonical byte codeword")
    return result


class PositionalParameters:
    @property
    def param_id(self):
        return PARAM_ID

    @property
    def block_size(self):
        return BLOCK_SIZE

    def encoded_size(self, source_length):
        return 4 * source_length

    def encode_block(self, source):
        return bytes(digit for value in source for digit in encode_byte(value))

    def decode_block(self, encoded, source_length):
        if len(encoded) != self.encoded_size(source_length):
            raise ValueError("block length mismatch")
        return bytes(decode_byte(encoded[i:i+4]) for i in range(0,len(encoded),4))


def encode(data: bytes) -> bytes:
    return chrn_frame.encode(data, parameters=PositionalParameters())


def decode(data: bytes) -> bytes:
    return chrn_frame.decode(data, parameters=PositionalParameters())
