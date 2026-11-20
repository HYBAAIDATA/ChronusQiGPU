"""Known-answer and corruption tests for the proposed framing profile only."""
import hashlib
import json
from pathlib import Path
import struct

import pytest

from chronus.storage import chrn_frame as frame

pytestmark = pytest.mark.real


class ReferenceParameters:
    """Test-only prime-symbol mapping; not the discovery or canonical ID 1."""

    param_id = 0xFFFFFFFE
    block_size = 256
    primes = tuple(n for n in range(2, 1620)
                   if all(n % d for d in range(2, n)))[:256]

    def encoded_size(self, source_length):
        return source_length * 2

    def encode_block(self, source):
        return b"".join(self.primes[x].to_bytes(2, "big") for x in source)

    def decode_block(self, encoded, source_length):
        return bytes(self.primes.index(int.from_bytes(encoded[i:i+2], "big"))
                     for i in range(0, len(encoded), 2))


P = ReferenceParameters()
VECTORS = json.loads((Path(__file__).parent / "vectors" /
                      "chrn_framing_provisional.json").read_text())["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=[v["id"] for v in VECTORS])
def test_known_answers(vector):
    source = bytes.fromhex(vector["input_hex"])
    wire = bytes.fromhex(vector["expected_encoded_hex"])
    assert hashlib.sha256(source).hexdigest() == vector["input_sha256"]
    assert hashlib.sha256(wire).hexdigest() == vector["expected_encoded_sha256"]
    assert frame.encode(source, parameters=P) == wire
    assert frame.decode(wire, parameters=P) == source


def test_crc32c_standard_check_value():
    assert frame.crc32c(b"123456789") == 0xE3069283


@pytest.mark.parametrize("size", [0, 1, 255, 256, 257, 512, 513, 4096])
def test_boundaries(size):
    source = (bytes(range(256)) * ((size + 255)//256))[:size]
    encoded = frame.encode(source, parameters=P)
    assert len(encoded) == 60 + 2*size
    assert frame.encode(memoryview(source), parameters=P) == encoded
    assert frame.decode(encoded, parameters=P) == source


def _header_change(wire, offset, data):
    prefix = bytearray(wire[:56])
    prefix[offset:offset+len(data)] = data
    return bytes(prefix) + struct.pack(">I", frame.crc32c(prefix)) + wire[60:]


@pytest.mark.parametrize("offset,value,error", [
    (0, b"X", frame.InvalidMagicError),
    (4, b"\x02", frame.UnsupportedVersionError),
    (6, b"\x80", frame.InvalidFlagsError),
    (7, b"\x01", frame.UnsupportedRecoveryError),
    (16, b"\xff", frame.InvalidParameterError),
    (20, b"\x00", frame.InvalidParameterError),
    (8, b"\xff", frame.FrameLengthError),
    (24, b"\x00", frame.PayloadIntegrityError),
])
def test_semantic_header_rejections(offset, value, error):
    wire = frame.encode(b"abc", parameters=P)
    with pytest.raises(error):
        frame.decode(_header_change(wire, offset, value), parameters=P)


def test_crc_and_magic_corruption():
    wire = bytearray(frame.encode(b"abc", parameters=P))
    wire[56] ^= 1
    with pytest.raises(frame.HeaderCRCError):
        frame.decode(wire, parameters=P)
    wire[0] ^= 1
    with pytest.raises(frame.InvalidMagicError):
        frame.decode(wire, parameters=P)


def test_bad_body_and_valid_symbol_substitution():
    wire = frame.encode(b"abc", parameters=P)
    with pytest.raises(frame.InvalidBlockError):
        frame.decode(wire[:60] + b"\x00\x04" + wire[62:], parameters=P)
    with pytest.raises(frame.PayloadIntegrityError):
        frame.decode(wire[:60] + b"\x00\x02" + wire[62:], parameters=P)


def test_every_truncation_and_trailing_byte():
    wire = frame.encode(b"abc", parameters=P)
    for length in range(len(wire)):
        with pytest.raises(frame.CorruptFrameError):
            frame.decode(wire[:length], parameters=P)
    with pytest.raises(frame.FrameLengthError):
        frame.decode(wire + b"\x00", parameters=P)


def test_no_implicit_parameter_or_legacy_fallback():
    with pytest.raises(TypeError):
        frame.encode(b"x")
    with pytest.raises(TypeError):
        frame.decode(b"x")
    with pytest.raises(frame.InvalidMagicError):
        frame.decode(b"CPRM" + b"\x00"*56, parameters=P)


def test_input_type_and_block_contract():
    with pytest.raises(TypeError):
        frame.encode("x", parameters=P)

    class Bad(ReferenceParameters):
        def encode_block(self, source):
            return b""

    with pytest.raises(frame.InvalidBlockError):
        frame.encode(b"x", parameters=Bad())
