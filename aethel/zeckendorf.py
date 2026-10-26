"""Hardened Zeckendorf codec and sparse-topology payload compression.

The codec is extended to F_93 (> 2^64 - 1) so it covers the full unsigned
64-bit range, and the compression helpers fold arbitrary byte payloads into
``SparseTopology`` block maps that roundtrip losslessly.  When an OpenCL
punch host is supplied the encode/decode stages dispatch to the device;
otherwise the identical CPU computation runs.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

# Punch opcodes dispatched to a bound OpenCL host when one is available.
PUNCH_MANIFOLD_COMPUTE = 0x15
PUNCH_ZECKENDORF_ENCODE = 0x02
PUNCH_ZECKENDORF_DECODE = 0x1C

_ZECKENDORF_FIB_LIMIT = 12200160415121876738

_PUNCH_OUT_BLOCK = 121  # DIM * DIM per-work-item output stride


class HardenedZeckendorfCodec:
    """Extended Zeckendorf codec.

    FIBONACCI extended to F_93 > 2^64 - 1.  Handles full 64-bit unsigned
    integers.
    """

    FIBONACCI = [
        0,
        1,
        2,
        3,
        5,
        8,
        13,
        21,
        34,
        55,
        89,
        144,
        233,
        377,
        610,
        987,
        1597,
        2584,
        4181,
        6765,
        10946,
        17711,
        28657,
        46368,
        75025,
        121393,
        196418,
        317811,
        514229,
        832040,
        1346269,
        2178309,
        3524578,
        5702887,
        9227465,
        14930352,
        24157817,
        39088169,
        63245986,
        102334155,
        165580141,
        267914296,
        433494437,
        701408733,
        1134903170,
        1836311903,
        2971215073,
        4807526976,
        7778742049,
        12586269025,
        20365011074,
        32951280099,
        53316291173,
        86267571272,
        139583862445,
        225851433717,
        365435296162,
        591286729879,
        956722026041,
        1548008755920,
        2504730781961,
        4052739537881,
        6557470319842,
        10610209857723,
        17167680177565,
        27777890035288,
        44945570212853,
        72723460248141,
        117669030460994,
        190392490709135,
        308061521170129,
        498454011879264,
        806515533049393,
        1304969544928657,
        2111485077978050,
        3416454622906707,
        5527939700884757,
        8944394323791464,
        14472334024676221,
        23416728348467685,
        37889062373143906,
        61305790721611591,
        99194853094755497,
        160500643816367088,
        259695496911122585,
        420196140727489673,
        679891637638612258,
        1100087778366101931,
        1779979416004714189,
        2880067194370816120,
        4660046610375530309,
        7540113804746346429,
        12200160415121876738,
        19740274219868223167,
    ]

    MAX_FIB_INDEX = len(FIBONACCI) - 1

    @classmethod
    def encode(cls, n: int) -> int:
        """Encode n as a Zeckendorf mask. Safe for full 64-bit unsigned."""
        if not isinstance(n, int):
            raise TypeError(f"Expected int, got {type(n)}")
        if n < 0:
            raise ValueError(f"Negative values not supported: {n}")
        if n == 0:
            return 0
        if n >= cls.FIBONACCI[-1]:
            raise ValueError(f"n={n} exceeds F_{len(cls.FIBONACCI) - 1}")
        mask = 0
        rem = n
        for i in range(len(cls.FIBONACCI) - 1, 0, -1):
            if cls.FIBONACCI[i] <= rem:
                mask |= 1 << (i - 1)
                rem -= cls.FIBONACCI[i]
        return mask

    @classmethod
    def decode(cls, mask: int) -> int:
        """Decode a Zeckendorf mask back to an integer."""
        if mask == 0:
            return 0
        if mask < 0:
            raise ValueError("Negative Zeckendorf masks are not supported")
        table = cls.FIBONACCI
        if mask.bit_length() >= len(table):
            raise ValueError(f"Mask bit {mask.bit_length() - 1} exceeds table size")
        n = 0
        remaining = mask
        while remaining:
            lowest = remaining & -remaining
            n += table[lowest.bit_length()]
            remaining ^= lowest
        return n

    @classmethod
    def verify_non_adjacent(cls, mask: int) -> bool:
        """Verify (mask & (mask << 1)) == 0."""
        return (mask & (mask << 1)) == 0

    @classmethod
    def encode_safe_chunk(cls, chunk_bytes: bytes) -> int:
        """Encode an 8-byte chunk safely."""
        n = int.from_bytes(chunk_bytes, "big")
        return cls.encode(n)

    @classmethod
    def encode_7byte_chunk(cls, chunk_bytes: bytes) -> int:
        """Encode a 7-byte chunk (56 bits, always < F_92)."""
        n = int.from_bytes(chunk_bytes.ljust(7, b"\x00"), "big")
        return cls.encode(n)


class SparseTopology:
    """Sparse block map produced by Zeckendorf payload compression."""

    def __init__(self) -> None:
        self.blocks: Dict[int, int] = {}
        self.total_bytes = 0

    def add(self, offset: int, mask: int) -> None:
        self.blocks[offset] = mask

    def items(self):
        return self.blocks.items()

    def __len__(self) -> int:
        return len(self.blocks)


def apply_zeckendorf_compression(payload: bytes, host=None) -> SparseTopology:
    sparse = SparseTopology()
    chunks = [payload[i : i + 8].ljust(8, b"\x00") for i in range(0, len(payload), 8)]
    if host is not None and chunks:
        ints = np.array([int.from_bytes(c, "big") for c in chunks], dtype=np.uint64)
        res = host.run_punch_batch(PUNCH_ZECKENDORF_ENCODE, in_ulong=ints)
        out = res["ulong"]
        for i in range(len(chunks)):
            base = i * _PUNCH_OUT_BLOCK
            sparse.add(i * 8, int(out[base]) | (int(out[base + 1]) << 64))
    else:
        for i, chunk in enumerate(chunks):
            n = int.from_bytes(chunk, "big")
            # n <= 2**64 - 1 < FIBONACCI[-1] (F_93), so encode cannot
            # raise for an 8-byte chunk — no fallback path is needed.
            sparse.add(i * 8, HardenedZeckendorfCodec.encode(n))
    sparse.total_bytes = len(payload)
    return sparse


def reverse_zeckendorf_expansion(sparse: SparseTopology, host=None) -> bytes:
    offsets = sorted(sparse.blocks.keys())
    if host is not None and offsets:
        interleaved = np.zeros(len(offsets) * 2, dtype=np.uint64)
        for i, offset in enumerate(offsets):
            mask = sparse.blocks[offset]
            interleaved[i * 2] = np.uint64(mask & 0xFFFFFFFFFFFFFFFF)
            interleaved[i * 2 + 1] = np.uint64((mask >> 64) & 0xFFFFFFFFFFFFFFFF)
        res = host.run_punch_batch(PUNCH_ZECKENDORF_DECODE, n=len(offsets), in_ulong=interleaved)
        out = res["ulong"]
        data = b"".join(
            int(out[i * _PUNCH_OUT_BLOCK]).to_bytes(8, "big") for i in range(len(offsets))
        )
        return data[: sparse.total_bytes]
    data = bytearray()
    for offset in offsets:
        n = HardenedZeckendorfCodec.decode(sparse.blocks[offset])
        data.extend(n.to_bytes(8, "big"))
    return bytes(data[: sparse.total_bytes])


def sparse_from_blocks(blocks: Optional[Dict[int, int]], total_bytes: int = 0) -> SparseTopology:
    """Rebuild a SparseTopology view over a stored block map."""
    sparse = SparseTopology()
    sparse.blocks = dict(blocks or {})
    sparse.total_bytes = total_bytes or len(sparse.blocks) * 8
    return sparse
