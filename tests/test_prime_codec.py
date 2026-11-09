"""Tests for the lossless prime-symbol reference codec."""

import struct

import pytest

from chronus.storage.prime_codec import (
    PrimeCodecError,
    PrimeCodecIntegrityError,
    decode,
    encode,
)


def test_all_octets_round_trip():
    source = bytes(range(256))
    payload, metadata = encode(source)
    assert decode(payload, metadata) == source
    assert len(payload) == len(source) * 2


def test_empty_input_round_trip():
    payload, metadata = encode(b"")
    assert payload == b""
    assert decode(payload, metadata) == b""


def test_encode_is_deterministic_and_accepts_bytes_like_input():
    assert encode(bytearray(b"chronus")) == encode(memoryview(b"chronus"))


def test_decode_rejects_wrong_input_types():
    with pytest.raises(TypeError):
        encode("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        decode("not bytes", b"x")  # type: ignore[arg-type]


def test_decode_rejects_malformed_metadata_and_payload():
    payload, metadata = encode(b"abc")
    with pytest.raises(PrimeCodecError, match="invalid length"):
        decode(payload, metadata[:-1])
    with pytest.raises(PrimeCodecError, match="magic"):
        decode(payload, b"XXXX" + metadata[4:])
    with pytest.raises(PrimeCodecError, match="payload length"):
        decode(payload[:-1], metadata)


def test_decode_rejects_non_prime_symbol():
    _, metadata = encode(b"a")
    with pytest.raises(PrimeCodecError, match="invalid prime symbol"):
        decode(struct.pack(">H", 4), metadata)


def test_decode_detects_substitution_with_another_valid_prime():
    payload, metadata = encode(b"a")
    tampered = struct.pack(">H", 2)  # another valid symbol prime
    assert tampered != payload
    with pytest.raises(PrimeCodecIntegrityError, match="digest"):
        decode(tampered, metadata)


def test_decode_rejects_unsupported_version():
    payload, metadata = encode(b"a")
    unsupported = metadata[:4] + b"\x02" + metadata[5:]
    with pytest.raises(PrimeCodecError, match="unsupported"):
        decode(payload, unsupported)
