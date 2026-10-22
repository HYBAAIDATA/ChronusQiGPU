"""Standards-conformant Stratum V2 Mining Protocol wire layer.

This module implements the binary Mining Protocol defined by the Stratum V2
specification: framing, SetupConnection negotiation, standard/extended channel
opening, job/target updates, and share submission/acknowledgement.

Security is an explicit transport boundary. Remote SV2 requires a transport
that has already established the specification's authenticated Noise session.
This module never silently downgrades to plaintext TCP or TLS and never
pretends that a fake transport is a pool connection. The official SRI Noise
transport can be adapted through ``SecureChannel`` without changing these
message contracts.

The Job Declaration and Template Distribution protocols are separate SV2
subprotocols. The Mining Protocol is complete here; those roles are not
silently represented by mining messages.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


MAX_FRAME_PAYLOAD = 0xFFFFFF
CHANNEL_MSG_BIT = 0x8000
CORE_EXTENSION = 0


class Sv2ProtocolError(ValueError):
    """Raised for malformed, out-of-state, or unsafe SV2 input."""


class Sv2TransportError(ConnectionError):
    """Raised when the secure transport cannot carry an SV2 session."""


class MessageType:
    SETUP_CONNECTION = 0x00
    SETUP_CONNECTION_SUCCESS = 0x01
    SETUP_CONNECTION_ERROR = 0x02
    RECONNECT = 0x04
    OPEN_STANDARD_MINING_CHANNEL = 0x10
    OPEN_STANDARD_MINING_CHANNEL_SUCCESS = 0x11
    OPEN_MINING_CHANNEL_ERROR = 0x12
    OPEN_EXTENDED_MINING_CHANNEL = 0x13
    OPEN_EXTENDED_MINING_CHANNEL_SUCCESS = 0x14
    NEW_MINING_JOB = 0x15
    UPDATE_CHANNEL = 0x16
    UPDATE_CHANNEL_ERROR = 0x17
    CLOSE_CHANNEL = 0x18
    SET_EXTRANONCE_PREFIX = 0x19
    SUBMIT_SHARES_STANDARD = 0x1A
    SUBMIT_SHARES_EXTENDED = 0x1B
    SUBMIT_SHARES_SUCCESS = 0x1C
    SUBMIT_SHARES_ERROR = 0x1D
    NEW_EXTENDED_MINING_JOB = 0x1F
    SET_NEW_PREV_HASH = 0x20
    SET_TARGET = 0x21
    SET_CUSTOM_MINING_JOB = 0x22
    SET_CUSTOM_MINING_JOB_SUCCESS = 0x23
    SET_CUSTOM_MINING_JOB_ERROR = 0x24
    SET_GROUP_CHANNEL = 0x25


CHANNEL_MESSAGE_TYPES = frozenset(
    {
        MessageType.NEW_MINING_JOB,
        MessageType.UPDATE_CHANNEL,
        MessageType.UPDATE_CHANNEL_ERROR,
        MessageType.CLOSE_CHANNEL,
        MessageType.SET_EXTRANONCE_PREFIX,
        MessageType.SUBMIT_SHARES_STANDARD,
        MessageType.SUBMIT_SHARES_EXTENDED,
        MessageType.SUBMIT_SHARES_SUCCESS,
        MessageType.SUBMIT_SHARES_ERROR,
        MessageType.NEW_EXTENDED_MINING_JOB,
        MessageType.SET_NEW_PREV_HASH,
        MessageType.SET_TARGET,
        MessageType.SET_CUSTOM_MINING_JOB,
        MessageType.SET_CUSTOM_MINING_JOB_SUCCESS,
        MessageType.SET_CUSTOM_MINING_JOB_ERROR,
    }
)


def _u8(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFF:
        raise Sv2ProtocolError(f"{name} must be U8")
    return value


def _u16(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise Sv2ProtocolError(f"{name} must be U16")
    return value


def _u32(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise Sv2ProtocolError(f"{name} must be U32")
    return value


def _u64(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise Sv2ProtocolError(f"{name} must be U64")
    return value


def _u256(value: int | bytes, name: str) -> bytes:
    if isinstance(value, int):
        if not 0 <= value <= (1 << 256) - 1:
            raise Sv2ProtocolError(f"{name} must fit U256")
        return value.to_bytes(32, "little")
    if not isinstance(value, bytes) or len(value) != 32:
        raise Sv2ProtocolError(f"{name} must be 32 bytes")
    return value


def _b(value: bytes, name: str, maximum: int) -> bytes:
    if not isinstance(value, bytes) or len(value) > maximum:
        raise Sv2ProtocolError(f"{name} must be bytes of length 0..{maximum}")
    return value


def _str(value: str | bytes, name: str, maximum: int = 255) -> bytes:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    if not isinstance(raw, bytes) or len(raw) > maximum:
        raise Sv2ProtocolError(f"{name} must be UTF-8/bytes of length 0..{maximum}")
    if b"\x00" in raw:
        raise Sv2ProtocolError(f"{name} must not contain NUL")
    return raw


def _pack_str(value: str | bytes, name: str, maximum: int = 255) -> bytes:
    raw = _str(value, name, maximum)
    if maximum <= 255:
        return bytes((len(raw),)) + raw
    return len(raw).to_bytes(2, "little") + raw


def _read(data: bytes, offset: int, size: int, name: str) -> tuple[bytes, int]:
    end = offset + size
    if end > len(data):
        raise Sv2ProtocolError(f"truncated {name}")
    return data[offset:end], end


def _read_u8(data: bytes, offset: int, name: str) -> tuple[int, int]:
    raw, offset = _read(data, offset, 1, name)
    return raw[0], offset


def _read_u16(data: bytes, offset: int, name: str) -> tuple[int, int]:
    raw, offset = _read(data, offset, 2, name)
    return int.from_bytes(raw, "little"), offset


def _read_u32(data: bytes, offset: int, name: str) -> tuple[int, int]:
    raw, offset = _read(data, offset, 4, name)
    return int.from_bytes(raw, "little"), offset


def _read_u64(data: bytes, offset: int, name: str) -> tuple[int, int]:
    raw, offset = _read(data, offset, 8, name)
    return int.from_bytes(raw, "little"), offset


def _read_str(data: bytes, offset: int, name: str, maximum: int = 255) -> tuple[bytes, int]:
    length, offset = _read_u8(data, offset, f"{name} length")
    if length > maximum:
        raise Sv2ProtocolError(f"{name} exceeds {maximum} bytes")
    return _read(data, offset, length, name)


def _read_b16(data: bytes, offset: int, name: str, maximum: int = 65535) -> tuple[bytes, int]:
    length, offset = _read_u16(data, offset, f"{name} length")
    if length > maximum:
        raise Sv2ProtocolError(f"{name} exceeds {maximum} bytes")
    return _read(data, offset, length, name)


def _read_b24(data: bytes, offset: int, name: str, maximum: int = MAX_FRAME_PAYLOAD) -> tuple[bytes, int]:
    raw, offset = _read(data, offset, 3, f"{name} length")
    length = int.from_bytes(raw, "little")
    if length > maximum:
        raise Sv2ProtocolError(f"{name} exceeds {maximum} bytes")
    return _read(data, offset, length, name)


def _finish(data: bytes, offset: int) -> None:
    if offset != len(data):
        raise Sv2ProtocolError(f"trailing bytes in payload: {len(data) - offset}")


@dataclass(frozen=True)
class Sv2Frame:
    extension_type: int
    message_type: int
    payload: bytes

    def __post_init__(self) -> None:
        _u16(self.extension_type, "extension_type")
        _u8(self.message_type, "message_type")
        if not isinstance(self.payload, bytes) or len(self.payload) > MAX_FRAME_PAYLOAD:
            raise Sv2ProtocolError("payload exceeds U24 frame length")
        if self.message_type in CHANNEL_MESSAGE_TYPES:
            if not (self.extension_type & CHANNEL_MSG_BIT):
                raise Sv2ProtocolError("channel message is missing channel_msg bit")
        elif self.extension_type & CHANNEL_MSG_BIT:
            raise Sv2ProtocolError("non-channel message cannot set channel_msg bit")

    def encode(self) -> bytes:
        return (
            self.extension_type.to_bytes(2, "little")
            + bytes((self.message_type,))
            + len(self.payload).to_bytes(3, "little")
            + self.payload
        )

    @classmethod
    def decode(cls, data: bytes) -> "Sv2Frame":
        if not isinstance(data, bytes) or len(data) < 6:
            raise Sv2ProtocolError("SV2 frame requires a six-byte header")
        extension_type = int.from_bytes(data[:2], "little")
        message_type = data[2]
        length = int.from_bytes(data[3:6], "little")
        if len(data) != 6 + length:
            raise Sv2ProtocolError("SV2 frame length does not match payload")
        return cls(extension_type, message_type, data[6:])


class FrameDecoder:
    """Incremental plaintext-frame decoder for a secure SV2 channel."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[Sv2Frame]:
        if not isinstance(chunk, bytes):
            raise Sv2ProtocolError("transport chunk must be bytes")
        self._buffer.extend(chunk)
        frames: list[Sv2Frame] = []
        while len(self._buffer) >= 6:
            length = int.from_bytes(self._buffer[3:6], "little")
            if length > MAX_FRAME_PAYLOAD:
                raise Sv2ProtocolError("frame length exceeds U24")
            if len(self._buffer) < 6 + length:
                break
            raw = bytes(self._buffer[: 6 + length])
            del self._buffer[: 6 + length]
            frames.append(Sv2Frame.decode(raw))
        return frames

    def finish(self) -> None:
        if self._buffer:
            raise Sv2ProtocolError("truncated frame at end of transport")


def _channel_payload(channel_id: int, payload: bytes) -> bytes:
    return struct.pack("<I", _u32(channel_id, "channel_id")) + payload


def _channel_frame(message_type: int, channel_id: int, payload: bytes) -> Sv2Frame:
    return Sv2Frame(CHANNEL_MSG_BIT, message_type, _channel_payload(channel_id, payload))


def _split_channel(frame: Sv2Frame) -> tuple[int, bytes]:
    if not (frame.extension_type & CHANNEL_MSG_BIT) or len(frame.payload) < 4:
        raise Sv2ProtocolError("channel frame has no channel_id")
    return int.from_bytes(frame.payload[:4], "little"), frame.payload[4:]


@dataclass(frozen=True)
class SetupConnection:
    protocol: int = 0
    min_version: int = 2
    max_version: int = 2
    flags: int = 0
    endpoint_host: str = ""
    endpoint_port: int = 0
    vendor: str = "PHIDATA2"
    hardware_version: str = "PYTHIA"
    firmware: str = "PYTHIA-SV2"
    device_id: str = ""

    def encode(self) -> Sv2Frame:
        if self.protocol not in (0, 1, 2):
            raise Sv2ProtocolError("unsupported SV2 protocol selector")
        if self.min_version != 2 or self.max_version != 2:
            raise Sv2ProtocolError("this implementation supports SV2 version 2 only")
        payload = bytes((self.protocol,)) + struct.pack(
            "<HHI", _u16(self.min_version, "min_version"),
            _u16(self.max_version, "max_version"), _u32(self.flags, "flags")
        ) + _pack_str(self.endpoint_host, "endpoint_host") + struct.pack(
            "<H", _u16(self.endpoint_port, "endpoint_port")
        )
        for value, name in (
            (self.vendor, "vendor"), (self.hardware_version, "hardware_version"),
            (self.firmware, "firmware"), (self.device_id, "device_id"),
        ):
            payload += _pack_str(value, name)
        return Sv2Frame(CORE_EXTENSION, MessageType.SETUP_CONNECTION, payload)

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SetupConnection":
        if frame.message_type != MessageType.SETUP_CONNECTION:
            raise Sv2ProtocolError("not a SetupConnection frame")
        data, offset = frame.payload, 0
        protocol, offset = _read_u8(data, offset, "protocol")
        min_version, offset = _read_u16(data, offset, "min_version")
        max_version, offset = _read_u16(data, offset, "max_version")
        flags, offset = _read_u32(data, offset, "flags")
        host, offset = _read_str(data, offset, "endpoint_host")
        port, offset = _read_u16(data, offset, "endpoint_port")
        values = []
        for name in ("vendor", "hardware_version", "firmware", "device_id"):
            value, offset = _read_str(data, offset, name)
            values.append(value.decode("utf-8", "strict"))
        _finish(data, offset)
        return cls(protocol, min_version, max_version, flags, host.decode(), port, *values)


@dataclass(frozen=True)
class SetupConnectionSuccess:
    used_version: int
    flags: int

    def encode(self) -> Sv2Frame:
        return Sv2Frame(
            CORE_EXTENSION,
            MessageType.SETUP_CONNECTION_SUCCESS,
            struct.pack(
                "<HI", _u16(self.used_version, "used_version"),
                _u32(self.flags, "flags")
            ),
        )

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SetupConnectionSuccess":
        if frame.message_type != MessageType.SETUP_CONNECTION_SUCCESS or len(frame.payload) != 6:
            raise Sv2ProtocolError("invalid SetupConnection.Success")
        return cls(int.from_bytes(frame.payload[:2], "little"), int.from_bytes(frame.payload[2:], "little"))


@dataclass(frozen=True)
class SetupConnectionError:
    flags: int
    error_code: str

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SetupConnectionError":
        if frame.message_type != MessageType.SETUP_CONNECTION_ERROR:
            raise Sv2ProtocolError("not a SetupConnection.Error frame")
        flags, offset = _read_u32(frame.payload, 0, "flags")
        code, offset = _read_str(frame.payload, offset, "error_code")
        _finish(frame.payload, offset)
        return cls(flags, code.decode("utf-8", "strict"))


@dataclass(frozen=True)
class OpenStandardMiningChannel:
    request_id: int
    user_identity: str
    nominal_hash_rate: float
    max_target: int

    def encode(self) -> Sv2Frame:
        if self.nominal_hash_rate < 0 or not math.isfinite(self.nominal_hash_rate):
            raise Sv2ProtocolError("nominal_hash_rate must be finite and non-negative")
        payload = struct.pack("<If", _u32(self.request_id, "request_id"), float(self.nominal_hash_rate))
        payload = struct.pack("<I", self.request_id) + _pack_str(self.user_identity, "user_identity")
        payload += struct.pack("<f", float(self.nominal_hash_rate)) + _u256(self.max_target, "max_target")
        return Sv2Frame(CORE_EXTENSION, MessageType.OPEN_STANDARD_MINING_CHANNEL, payload)


@dataclass(frozen=True)
class OpenExtendedMiningChannel(OpenStandardMiningChannel):
    min_extranonce_size: int = 0

    def encode(self) -> Sv2Frame:
        base = OpenStandardMiningChannel.encode(self).payload
        return Sv2Frame(
            CORE_EXTENSION, MessageType.OPEN_EXTENDED_MINING_CHANNEL,
            base + struct.pack("<H", _u16(self.min_extranonce_size, "min_extranonce_size")),
        )


@dataclass(frozen=True)
class OpenStandardMiningChannelSuccess:
    request_id: int
    channel_id: int
    target: int
    extranonce_prefix: bytes
    group_channel_id: int

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "OpenStandardMiningChannelSuccess":
        if frame.message_type != MessageType.OPEN_STANDARD_MINING_CHANNEL_SUCCESS:
            raise Sv2ProtocolError("not OpenStandardMiningChannel.Success")
        data, offset = frame.payload, 0
        request_id, offset = _read_u32(data, offset, "request_id")
        channel_id, offset = _read_u32(data, offset, "channel_id")
        target_raw, offset = _read(data, offset, 32, "target")
        prefix, offset = _read_str(data, offset, "extranonce_prefix", 32)
        group, offset = _read_u32(data, offset, "group_channel_id")
        _finish(data, offset)
        return cls(request_id, channel_id, int.from_bytes(target_raw, "little"), prefix, group)


@dataclass(frozen=True)
class OpenExtendedMiningChannelSuccess:
    request_id: int
    channel_id: int
    target: int
    extranonce_size: int
    extranonce_prefix: bytes
    group_channel_id: int

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "OpenExtendedMiningChannelSuccess":
        if frame.message_type != MessageType.OPEN_EXTENDED_MINING_CHANNEL_SUCCESS:
            raise Sv2ProtocolError("not OpenExtendedMiningChannel.Success")
        data, offset = frame.payload, 0
        request_id, offset = _read_u32(data, offset, "request_id")
        channel_id, offset = _read_u32(data, offset, "channel_id")
        target_raw, offset = _read(data, offset, 32, "target")
        size, offset = _read_u16(data, offset, "extranonce_size")
        prefix, offset = _read_str(data, offset, "extranonce_prefix", 32)
        group, offset = _read_u32(data, offset, "group_channel_id")
        _finish(data, offset)
        return cls(request_id, channel_id, int.from_bytes(target_raw, "little"), size, prefix, group)


@dataclass(frozen=True)
class NewMiningJob:
    channel_id: int
    job_id: int
    min_ntime: int | None
    version: int
    merkle_root: bytes

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "NewMiningJob":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.NEW_MINING_JOB:
            raise Sv2ProtocolError("not NewMiningJob")
        job_id, offset = _read_u32(data, 0, "job_id")
        present, offset = _read_u8(data, offset, "min_ntime option")
        if present not in (0, 1):
            raise Sv2ProtocolError("invalid min_ntime option")
        min_ntime = None
        if present:
            min_ntime, offset = _read_u32(data, offset, "min_ntime")
        version, offset = _read_u32(data, offset, "version")
        merkle, offset = _read(data, offset, 32, "merkle_root")
        _finish(data, offset)
        return cls(channel_id, job_id, min_ntime, version, merkle)


@dataclass(frozen=True)
class NewExtendedMiningJob:
    channel_id: int
    job_id: int
    min_ntime: int | None
    version: int
    version_rolling_allowed: bool
    merkle_path: tuple[bytes, ...]
    coinbase_tx_prefix: bytes
    coinbase_tx_suffix: bytes

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "NewExtendedMiningJob":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.NEW_EXTENDED_MINING_JOB:
            raise Sv2ProtocolError("not NewExtendedMiningJob")
        job_id, offset = _read_u32(data, 0, "job_id")
        present, offset = _read_u8(data, offset, "min_ntime option")
        if present not in (0, 1):
            raise Sv2ProtocolError("invalid min_ntime option")
        min_ntime = None
        if present:
            min_ntime, offset = _read_u32(data, offset, "min_ntime")
        version, offset = _read_u32(data, offset, "version")
        rolling, offset = _read_u8(data, offset, "version_rolling_allowed")
        if rolling not in (0, 1):
            raise Sv2ProtocolError("invalid version_rolling_allowed")
        count, offset = _read_u8(data, offset, "merkle_path count")
        path = []
        for _ in range(count):
            item, offset = _read(data, offset, 32, "merkle_path item")
            path.append(item)
        prefix, offset = _read_b16(data, offset, "coinbase_tx_prefix")
        suffix, offset = _read_b16(data, offset, "coinbase_tx_suffix")
        _finish(data, offset)
        return cls(channel_id, job_id, min_ntime, version, bool(rolling), tuple(path), prefix, suffix)


@dataclass(frozen=True)
class SetNewPrevHash:
    channel_id: int
    job_id: int
    prev_hash: bytes
    min_ntime: int
    nbits: int

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SetNewPrevHash":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.SET_NEW_PREV_HASH:
            raise Sv2ProtocolError("not SetNewPrevHash")
        job_id, offset = _read_u32(data, 0, "job_id")
        prev, offset = _read(data, offset, 32, "prev_hash")
        min_ntime, offset = _read_u32(data, offset, "min_ntime")
        nbits, offset = _read_u32(data, offset, "nbits")
        _finish(data, offset)
        return cls(channel_id, job_id, prev, min_ntime, nbits)


@dataclass(frozen=True)
class SetTarget:
    channel_id: int
    maximum_target: int

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SetTarget":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.SET_TARGET or len(data) != 32:
            raise Sv2ProtocolError("invalid SetTarget")
        return cls(channel_id, int.from_bytes(data, "little"))


@dataclass(frozen=True)
class SetExtranoncePrefix:
    channel_id: int
    extranonce_prefix: bytes

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SetExtranoncePrefix":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.SET_EXTRANONCE_PREFIX:
            raise Sv2ProtocolError("invalid SetExtranoncePrefix")
        prefix, offset = _read_str(data, 0, "extranonce_prefix", 32)
        _finish(data, offset)
        return cls(channel_id, prefix)


def build_extended_header(
    job: NewExtendedMiningJob,
    *,
    prev_hash: bytes,
    extranonce_prefix: bytes,
    extranonce: bytes,
    ntime: int,
    nbits: int,
    nonce: int,
    version: int | None = None,
) -> bytes:
    """Build the exact 80-byte Bitcoin header for an extended SV2 job.

    SV2 supplies the coinbase prefix/suffix and merkle path separately. The
    caller supplies the channel prefix/extranonce and the current prevhash
    announced by ``SetNewPrevHash``. No transaction ordering or nonce shortcut
    is introduced.
    """
    if not isinstance(prev_hash, bytes) or len(prev_hash) != 32:
        raise Sv2ProtocolError("prev_hash must be 32 bytes")
    if len(extranonce) > 32 or len(extranonce_prefix) > 32:
        raise Sv2ProtocolError("extranonce components exceed B0_32")
    if job.min_ntime is not None and ntime < job.min_ntime:
        raise Sv2ProtocolError("ntime is below the job minimum")
    if job.version_rolling_allowed is False and version is not None and version != job.version:
        raise Sv2ProtocolError("version rolling is not allowed for this job")
    selected_version = job.version if version is None else _u32(version, "version")
    coinbase = job.coinbase_tx_prefix + extranonce_prefix + extranonce + job.coinbase_tx_suffix
    merkle = hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()
    for branch in job.merkle_path:
        merkle = hashlib.sha256(hashlib.sha256(merkle + branch).digest()).digest()
    return (
        struct.pack("<I", selected_version)
        + prev_hash
        + merkle
        + struct.pack(
            "<III",
            _u32(ntime, "ntime"),
            _u32(nbits, "nbits"),
            _u32(nonce, "nonce"),
        )
    )


def submit_shares_standard(
    channel_id: int, sequence_number: int, job_id: int, nonce: int, ntime: int, version: int
) -> Sv2Frame:
    payload = struct.pack(
        "<IIIII", _u32(sequence_number, "sequence_number"), _u32(job_id, "job_id"),
        _u32(nonce, "nonce"), _u32(ntime, "ntime"), _u32(version, "version"),
    )
    return _channel_frame(MessageType.SUBMIT_SHARES_STANDARD, channel_id, payload)


def submit_shares_extended(
    channel_id: int, sequence_number: int, job_id: int, nonce: int, ntime: int,
    version: int, extranonce: bytes
) -> Sv2Frame:
    payload = submit_shares_standard(channel_id, sequence_number, job_id, nonce, ntime, version).payload[4:]
    # B0_32 is binary, not STR0_32: embedded NUL bytes are valid.
    extranonce = _b(extranonce, "extranonce", 32)
    return _channel_frame(
        MessageType.SUBMIT_SHARES_EXTENDED, channel_id,
        payload + bytes((len(extranonce),)) + extranonce,
    )


@dataclass(frozen=True)
class SubmitSharesSuccess:
    channel_id: int
    last_sequence_number: int
    new_submits_accepted_count: int
    new_shares_sum: int

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SubmitSharesSuccess":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.SUBMIT_SHARES_SUCCESS or len(data) != 16:
            raise Sv2ProtocolError("invalid SubmitShares.Success")
        last, count, total = struct.unpack("<IIQ", data)
        return cls(channel_id, last, count, total)


@dataclass(frozen=True)
class SubmitSharesError:
    channel_id: int
    sequence_number: int
    error_code: str

    @classmethod
    def decode(cls, frame: Sv2Frame) -> "SubmitSharesError":
        channel_id, data = _split_channel(frame)
        if frame.message_type != MessageType.SUBMIT_SHARES_ERROR:
            raise Sv2ProtocolError("invalid SubmitShares.Error")
        seq, offset = _read_u32(data, 0, "sequence_number")
        code, offset = _read_str(data, offset, "error_code")
        _finish(data, offset)
        return cls(channel_id, seq, code.decode("utf-8", "strict"))


class SecureChannel(Protocol):
    """Adapter contract for an authenticated SV2 Noise session."""

    secure: bool

    async def open(self) -> None: ...
    async def send(self, payload: bytes) -> None: ...
    async def receive(self) -> bytes: ...
    async def close(self) -> None: ...


class SessionState(Enum):
    NEW = "new"
    SETUP = "setup"
    CHANNEL_OPEN = "channel_open"
    CLOSED = "closed"


@dataclass
class StratumV2Client:
    """Strict Mining Protocol client over an authenticated secure channel."""

    channel: SecureChannel
    setup: SetupConnection
    require_secure: bool = True
    state: SessionState = field(default=SessionState.NEW, init=False)
    negotiated_flags: int = field(default=0, init=False)
    channel_id: int | None = field(default=None, init=False)
    target: int | None = field(default=None, init=False)
    extranonce_prefix: bytes = field(default=b"", init=False)
    extranonce_size: int | None = field(default=None, init=False)
    sequence_number: int = field(default=0, init=False)
    jobs: dict[int, NewMiningJob | NewExtendedMiningJob] = field(default_factory=dict, init=False)
    active_job_id: int | None = field(default=None, init=False)
    current_prev_hash: bytes | None = field(default=None, init=False)
    current_min_ntime: int | None = field(default=None, init=False)
    current_nbits: int | None = field(default=None, init=False)
    _decoder: FrameDecoder = field(default_factory=FrameDecoder, init=False)
    _pending_frames: list[Sv2Frame] = field(default_factory=list, init=False)

    async def open_standard_channel(self, request_id: int, nominal_hash_rate: float, max_target: int, user_identity: str) -> int:
        if self.state is not SessionState.SETUP:
            raise Sv2ProtocolError("SetupConnection must succeed before opening a channel")
        request = OpenStandardMiningChannel(request_id, user_identity, nominal_hash_rate, max_target)
        await self._send(request.encode())
        response = await self._next_frame()
        opened = OpenStandardMiningChannelSuccess.decode(response)
        if opened.request_id != request_id:
            raise Sv2ProtocolError("channel response request_id mismatch")
        self.channel_id = opened.channel_id
        self.target = opened.target
        self.extranonce_prefix = opened.extranonce_prefix
        self.state = SessionState.CHANNEL_OPEN
        return self.channel_id

    async def open_extended_channel(
        self,
        request_id: int,
        nominal_hash_rate: float,
        max_target: int,
        user_identity: str,
        min_extranonce_size: int = 0,
    ) -> int:
        if self.state is not SessionState.SETUP:
            raise Sv2ProtocolError("SetupConnection must succeed before opening a channel")
        request = OpenExtendedMiningChannel(
            request_id,
            user_identity,
            nominal_hash_rate,
            max_target,
            min_extranonce_size,
        )
        await self._send(request.encode())
        response = await self._next_frame()
        opened = OpenExtendedMiningChannelSuccess.decode(response)
        if opened.request_id != request_id:
            raise Sv2ProtocolError("channel response request_id mismatch")
        self.channel_id = opened.channel_id
        self.target = opened.target
        self.extranonce_prefix = opened.extranonce_prefix
        self.extranonce_size = opened.extranonce_size
        self.state = SessionState.CHANNEL_OPEN
        return self.channel_id

    async def open(self) -> SetupConnectionSuccess:
        if self.state is not SessionState.NEW:
            raise Sv2ProtocolError("SV2 client can only be opened once")
        try:
            await self.channel.open()
            if self.require_secure and not getattr(self.channel, "secure", False):
                raise Sv2TransportError(
                    "remote Stratum V2 requires an authenticated secure transport"
                )
            await self._send(self.setup.encode())
            frame = await self._next_frame()
            if frame.message_type == MessageType.SETUP_CONNECTION_ERROR:
                error = SetupConnectionError.decode(frame)
                raise Sv2ProtocolError(f"SetupConnection rejected: {error.error_code}")
            success = SetupConnectionSuccess.decode(frame)
            if success.used_version != 2:
                raise Sv2ProtocolError("server selected unsupported SV2 version")
            self.negotiated_flags = success.flags
            self.state = SessionState.SETUP
            return success
        except BaseException:
            # Any handshake/protocol/transport failure invalidates the channel.
            # Never leave a half-open authenticated transport available for reuse.
            try:
                await self.channel.close()
            finally:
                self.state = SessionState.CLOSED
            raise

    async def submit_standard(self, job_id: int, nonce: int, ntime: int, version: int) -> None:
        if self.state is not SessionState.CHANNEL_OPEN or self.channel_id is None:
            raise Sv2ProtocolError("no open SV2 mining channel")
        if job_id not in self.jobs:
            raise Sv2ProtocolError("cannot submit against an unknown or stale job")
        sequence = self.sequence_number
        self.sequence_number = (self.sequence_number + 1) & 0xFFFFFFFF
        await self._send(submit_shares_standard(self.channel_id, sequence, job_id, nonce, ntime, version))

    async def submit_extended(
        self,
        job_id: int,
        nonce: int,
        ntime: int,
        version: int,
        extranonce: bytes,
    ) -> None:
        if self.state is not SessionState.CHANNEL_OPEN or self.channel_id is None:
            raise Sv2ProtocolError("no open SV2 mining channel")
        if self.extranonce_size is None:
            raise Sv2ProtocolError("extended channel is not open")
        if len(extranonce) != self.extranonce_size:
            raise Sv2ProtocolError("extranonce does not match negotiated size")
        if job_id not in self.jobs:
            raise Sv2ProtocolError("cannot submit against an unknown or stale job")
        sequence = self.sequence_number
        self.sequence_number = (self.sequence_number + 1) & 0xFFFFFFFF
        await self._send(
            submit_shares_extended(
                self.channel_id, sequence, job_id, nonce, ntime, version, extranonce
            )
        )

    async def receive_event(self) -> Any:
        if self.state not in (SessionState.SETUP, SessionState.CHANNEL_OPEN):
            raise Sv2ProtocolError("SV2 client is not open")
        frame = await self._next_frame()
        if frame.message_type == MessageType.NEW_MINING_JOB:
            job = NewMiningJob.decode(frame)
            self._record_job(job)
            return job
        if frame.message_type == MessageType.NEW_EXTENDED_MINING_JOB:
            job = NewExtendedMiningJob.decode(frame)
            self._record_job(job)
            return job
        if frame.message_type == MessageType.SET_NEW_PREV_HASH:
            event = SetNewPrevHash.decode(frame)
            if event.job_id not in self.jobs:
                raise Sv2ProtocolError("SetNewPrevHash references unknown job")
            self.active_job_id = event.job_id
            self.current_prev_hash = event.prev_hash
            self.current_min_ntime = event.min_ntime
            self.current_nbits = event.nbits
            return event
        if frame.message_type == MessageType.SET_TARGET:
            event = SetTarget.decode(frame)
            if self.channel_id != event.channel_id:
                raise Sv2ProtocolError("SetTarget addressed another channel")
            self.target = event.maximum_target
            return event
        if frame.message_type == MessageType.SET_EXTRANONCE_PREFIX:
            event = SetExtranoncePrefix.decode(frame)
            if self.channel_id != event.channel_id:
                raise Sv2ProtocolError("SetExtranoncePrefix addressed another channel")
            self.extranonce_prefix = event.extranonce_prefix
            return event
        if frame.message_type == MessageType.SUBMIT_SHARES_SUCCESS:
            return SubmitSharesSuccess.decode(frame)
        if frame.message_type == MessageType.SUBMIT_SHARES_ERROR:
            return SubmitSharesError.decode(frame)
        raise Sv2ProtocolError(f"unsupported or unexpected SV2 message 0x{frame.message_type:02x}")

    async def close(self) -> None:
        if self.state is not SessionState.CLOSED:
            await self.channel.close()
        self.state = SessionState.CLOSED

    async def _send(self, frame: Sv2Frame) -> None:
        await self.channel.send(frame.encode())

    async def _next_frame(self) -> Sv2Frame:
        while True:
            if self._pending_frames:
                return self._pending_frames.pop(0)
            chunk = await self.channel.receive()
            if not isinstance(chunk, bytes) or not chunk:
                raise Sv2TransportError("secure channel returned no bytes")
            frames = self._decoder.feed(chunk)
            if frames:
                self._pending_frames.extend(frames)
                return self._pending_frames.pop(0)

    def _record_job(self, job: NewMiningJob | NewExtendedMiningJob) -> None:
        if self.channel_id != job.channel_id:
            raise Sv2ProtocolError("job addressed another channel")
        self.jobs[job.job_id] = job
        if job.min_ntime is not None:
            self.active_job_id = job.job_id


__all__ = [
    "CHANNEL_MSG_BIT", "CORE_EXTENSION", "FrameDecoder", "MessageType",
    "build_extended_header",
    "NewExtendedMiningJob", "NewMiningJob", "OpenExtendedMiningChannel",
    "OpenExtendedMiningChannelSuccess", "OpenStandardMiningChannel",
    "OpenStandardMiningChannelSuccess", "SecureChannel", "SessionState",
    "SetExtranoncePrefix", "SetNewPrevHash", "SetTarget", "SetupConnection", "SetupConnectionError",
    "SetupConnectionSuccess", "StratumV2Client", "Sv2Frame",
    "Sv2ProtocolError", "Sv2TransportError",
    "SubmitSharesError", "SubmitSharesSuccess", "submit_shares_extended",
    "submit_shares_standard",
]
