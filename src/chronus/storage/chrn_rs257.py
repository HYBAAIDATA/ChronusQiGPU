"""CHRN parameter 2: systematic AL HARAS RS(48,32), eight interleaved lanes.

The systematic data is stored byte-for-byte; parity coefficients are nine-bit
unsigned integers in row-major, rotated lane order, most-significant bit first.
This is a distinct recovery profile, not the unresolved discovery parameter 1.
"""
from __future__ import annotations

from chronus.security.al_haras import reed_solomon as rs
from chronus.storage import chrn_frame as frame

PARAM_ID = frame.RS257_PARAM_ID
BLOCK_SIZE = 256
LANES = 8
K = 32
N = 48
T = 8
PARITY_BYTES = 144


def _length(length: int) -> None:
    if type(length) is not int or not 0 <= length <= BLOCK_SIZE:
        raise ValueError("source block length outside 0..256")


def _lane_data(source: bytes, lane: int) -> list[int]:
    live = list(source[lane::LANES])
    return live + [0] * (K - len(live))


def _parity_rows(source: bytes) -> list[list[int]]:
    return [rs.encode_block(_lane_data(source, lane), N, K) for lane in range(LANES)]


def _pack_parity(parity: list[list[int]], rotation: int) -> bytes:
    out = bytearray()
    for row in range(N-K):
        word = 0
        for index in range(LANES):
            word = (word << 9) | parity[(index+rotation)%LANES][row]
        out.extend(word.to_bytes(9, "big"))
    return bytes(out)


def _unpack_parity(encoded: bytes, rotation: int) -> list[list[int]]:
    if len(encoded) != PARITY_BYTES:
        raise ValueError("incorrect parity size")
    parity = [[0]*(N-K) for _ in range(LANES)]
    for row in range(N-K):
        word = int.from_bytes(encoded[row*9:(row+1)*9], "big")
        for index in range(LANES):
            parity[(index+rotation)%LANES][row] = (word >> (9*(LANES-1-index))) & 511
    return parity


class RS257Parameters:
    param_id = PARAM_ID
    block_size = BLOCK_SIZE

    def encoded_size(self, source_length: int) -> int:
        return self.protected_size(source_length)

    def encode_block(self, source: bytes) -> bytes:
        raise frame.UnsupportedRecoveryError("parameter 2 requires recovery flag")

    def decode_block(self, encoded: bytes, source_length: int) -> bytes:
        raise frame.UnsupportedRecoveryError("parameter 2 requires recovery flag")

    def protected_size(self, source_length: int) -> int:
        _length(source_length)
        return source_length + PARITY_BYTES if source_length else 0

    def encode_block_protected(self, source: bytes) -> bytes:
        if not isinstance(source, bytes):
            raise TypeError("block must be bytes")
        _length(len(source))
        if not source:
            return b""
        return source + _pack_parity(_parity_rows(source),len(source)%LANES)

    def decode_block_protected(self, encoded: bytes, source_length: int) -> frame.ProtectedBlock:
        _length(source_length)
        if not isinstance(encoded, bytes) or len(encoded)!=self.protected_size(source_length):
            raise ValueError("protected block length mismatch")
        if not source_length:
            return frame.ProtectedBlock(b"", (), ())
        systematic = encoded[:source_length]
        parity = _unpack_parity(encoded[source_length:],source_length%LANES)
        output = bytearray(source_length)
        positions = []
        for lane in range(LANES):
            received_data = _lane_data(systematic,lane)
            # Invalid nine-bit labels are counted as errors, not silently reduced
            # modulo 257. Substitute a fixed field element for BW, then compare
            # the recovered canonical codeword to the raw labels below.
            received_parity = parity[lane]
            field_parity = [v if v <= 256 else 0 for v in received_parity]
            result = rs.decode_block(received_data + field_parity,N,K)
            if result["status"] not in {"clean","corrected"}:
                raise ValueError("uncorrectable RS lane")
            data = result["data"]
            live = len(systematic[lane::LANES])
            if len(data)!=K or any(type(v) is not int or not 0<=v<=255 for v in data[:live]) or any(data[live:]):
                raise ValueError("noncanonical systematic data or shortened padding")
            canonical = data + rs.encode_block(data,N,K)
            received = received_data + received_parity
            errors = [i for i,(a,b) in enumerate(zip(received,canonical)) if a!=b]
            if len(errors)>T:
                raise ValueError("RS correction exceeds declared radius")
            positions.extend((lane,i) for i in errors)
            output[lane::LANES] = bytes(data[:live])
        payload = bytes(output)
        repaired = self.encode_block_protected(payload)
        wire_errors = tuple(i for i,(a,b) in enumerate(zip(encoded,repaired)) if a!=b)
        return frame.ProtectedBlock(payload,tuple(positions),wire_errors)


PARAMETERS = RS257Parameters()


def encode(data: bytes) -> bytes:
    return frame.encode(data,parameters=PARAMETERS,recovery=True)


def decode(data: bytes) -> bytes:
    return frame.decode(data,parameters=PARAMETERS)


def decode_with_report(data: bytes) -> frame.DecodedFrame:
    return frame.decode_with_report(data,parameters=PARAMETERS)
