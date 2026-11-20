"""CHRN framing for explicitly supplied, trusted block parameters.

No discovery parameter is registered. CPRM is a separate legacy format.
Big-endian framing; recovery is explicit and restricted to parameter ID 2.
"""
from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass
from typing import Protocol

MAGIC = b"CHRN"
VERSION = 0x0100
RECOVERY_FLAG = 1
RS257_PARAM_ID = 2
HEADER_SIZE = 60
_HEADER = struct.Struct(">4sHHQII32s")
_CRC = struct.Struct(">I")


class CorruptFrameError(ValueError):
    """Malformed, unsupported or corrupt frame; no payload is returned."""


class InvalidMagicError(CorruptFrameError):
    pass


class UnsupportedVersionError(CorruptFrameError):
    pass


class InvalidFlagsError(CorruptFrameError):
    pass


class UnsupportedRecoveryError(InvalidFlagsError):
    pass


class HeaderCRCError(CorruptFrameError):
    pass


class FrameLengthError(CorruptFrameError):
    pass


class InvalidParameterError(CorruptFrameError):
    pass


class PayloadIntegrityError(CorruptFrameError):
    pass


class InvalidBlockError(CorruptFrameError):
    pass


class BlockParameters(Protocol):
    """Trusted parameter implementation with fixed encoded width per input length."""

    @property
    def param_id(self) -> int: ...
    @property
    def block_size(self) -> int: ...
    def encoded_size(self, source_length: int) -> int: ...
    def encode_block(self, source: bytes) -> bytes: ...
    def decode_block(self, encoded: bytes, source_length: int) -> bytes: ...


@dataclass(frozen=True)
class ProtectedBlock:
    data: bytes
    error_positions: tuple[tuple[int, int], ...]
    corrected_byte_positions: tuple[int, ...]


@dataclass(frozen=True)
class DecodedFrame:
    data: bytes
    corrected_symbols: tuple[tuple[int, int, int], ...]
    corrected_byte_positions: tuple[int, ...]

    @property
    def status(self) -> str:
        return "corrected" if self.corrected_byte_positions else "clean"


class RecoveryParameters(BlockParameters, Protocol):
    def protected_size(self, source_length: int) -> int: ...
    def encode_block_protected(self, source: bytes) -> bytes: ...
    def decode_block_protected(self, encoded: bytes, source_length: int) -> ProtectedBlock: ...


def _recovery(parameters: BlockParameters, flags: int) -> bool:
    if flags & RECOVERY_FLAG:
        if parameters.param_id != RS257_PARAM_ID or not all(
            callable(getattr(parameters, name, None))
            for name in ("protected_size", "encode_block_protected", "decode_block_protected")
        ):
            raise UnsupportedRecoveryError("recovery profile is not registered")
        return True
    if parameters.param_id == RS257_PARAM_ID:
        raise UnsupportedRecoveryError("parameter 2 requires recovery flag")
    return False


def crc32c(data: bytes) -> int:
    """Reflected Castagnoli CRC-32C; init/final XOR both 0xffffffff."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def _bytes(value: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError("expected bytes-like input")
    return bytes(value)


def _validate_parameters(parameters: BlockParameters) -> tuple[int, int]:
    pid = parameters.param_id
    size = parameters.block_size
    if type(pid) is not int or not 0 < pid < 2**32:
        raise InvalidParameterError("invalid parameter identifier")
    if type(size) is not int or not 0 < size < 2**32:
        raise InvalidParameterError("invalid block size")
    return pid, size


def _width(parameters: BlockParameters, length: int, protected: bool) -> int:
    if length == 0:
        return 0
    width = parameters.protected_size(length) if protected else parameters.encoded_size(length)
    if type(width) is not int or width <= 0:
        raise InvalidParameterError("invalid encoded block width")
    return width


def _layout(parameters: BlockParameters, length: int, size: int, protected: bool) -> tuple[int, int, int, int]:
    count, tail = divmod(length, size)
    width = _width(parameters, size, protected) if count else 0
    return count, tail, width, _width(parameters, tail, protected)


def encode(data: bytes | bytearray | memoryview, *, parameters: BlockParameters, recovery: bool = False) -> bytes:
    """Frame data with explicit, opt-in bounded recovery."""
    source = _bytes(data)
    pid, size = _validate_parameters(parameters)
    if len(source) >= 2**64:
        raise FrameLengthError("source length exceeds uint64")
    if type(recovery) is not bool:
        raise TypeError("recovery must be a boolean")
    flags = RECOVERY_FLAG if recovery else 0
    protected = _recovery(parameters, flags)
    count, tail, width, tail_width = _layout(parameters, len(source), size, protected)
    prefix = _HEADER.pack(MAGIC, VERSION, flags, len(source), size, pid,
                          hashlib.sha256(source).digest())
    frame = bytearray(prefix + _CRC.pack(crc32c(prefix)))
    for index in range(count + bool(tail)):
        length, expected = (size, width) if index < count else (tail, tail_width)
        block = source[index * size:index * size + length]
        encoded = parameters.encode_block_protected(block) if protected else parameters.encode_block(block)
        if not isinstance(encoded, bytes) or len(encoded) != expected:
            raise InvalidBlockError("encoded block does not match parameter width")
        frame.extend(encoded)
    return bytes(frame)


def decode(frame: bytes | bytearray | memoryview, *, parameters: BlockParameters) -> bytes:
    """Return the entire verified payload or raise a typed error."""
    return decode_with_report(frame, parameters=parameters).data


def decode_with_report(frame: bytes | bytearray | memoryview, *, parameters: BlockParameters) -> DecodedFrame:
    """Return recovery locations only after full payload integrity verification."""
    raw = _bytes(frame)
    if len(raw) < HEADER_SIZE:
        raise FrameLengthError("truncated header")
    magic, version, flags, length, size, pid, digest = _HEADER.unpack_from(raw)
    if magic != MAGIC:
        raise InvalidMagicError("invalid CHRN magic")
    if version != VERSION:
        raise UnsupportedVersionError("unsupported CHRN version")
    if flags & ~1:
        raise InvalidFlagsError("reserved flags are nonzero")
    protected = _recovery(parameters, flags)
    if _CRC.unpack_from(raw, 56)[0] != crc32c(raw[:56]):
        raise HeaderCRCError("header CRC-32C mismatch")
    expected_pid, expected_size = _validate_parameters(parameters)
    if pid != expected_pid or size != expected_size:
        raise InvalidParameterError("header does not identify the supplied parameters")
    count, tail, width, tail_width = _layout(parameters, length, size, protected)
    if len(raw) != HEADER_SIZE + count * width + tail_width:
        raise FrameLengthError("body length mismatch or trailing bytes")
    out = bytearray()
    symbols = []
    positions = []
    offset = HEADER_SIZE
    for index in range(count + bool(tail)):
        expected, encoded_width = (size, width) if index < count else (tail, tail_width)
        try:
            encoded = raw[offset:offset + encoded_width]
            if protected:
                recovered = parameters.decode_block_protected(encoded, expected)
                if not isinstance(recovered, ProtectedBlock):
                    raise InvalidBlockError("invalid recovery report")
                block = recovered.data
                symbols.extend((index, lane, symbol) for lane, symbol in recovered.error_positions)
                positions.extend(offset + p for p in recovered.corrected_byte_positions)
            else:
                block = parameters.decode_block(encoded, expected)
        except ValueError as exc:
            raise InvalidBlockError("invalid encoded block") from exc
        if not isinstance(block, bytes) or len(block) != expected:
            raise InvalidBlockError("decoded block does not match declared length")
        out.extend(block)
        offset += encoded_width
    result = bytes(out)
    if not hmac.compare_digest(hashlib.sha256(result).digest(), digest):
        raise PayloadIntegrityError("payload SHA-256 mismatch")
    return DecodedFrame(result, tuple(symbols), tuple(positions))
