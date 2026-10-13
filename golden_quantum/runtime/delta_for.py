"""
Delta + Frame-of-Reference + Bitpacking compression pipeline.

This is a standard lossless integer compression technique used in
columnar database systems. It works best on sorted or near-sorted
integer sequences (surrogate keys, timestamps, event ordinals).

Pipeline:
  1. Delta encoding: replace each value with its difference from the previous
  2. Frame-of-reference: subtract the minimum delta to make all values ≥ 0
  3. Bitpacking: pack non-negative values using the minimum number of bits

The compression is exactly reversible. The fold transform (M_φ) can be
applied before this pipeline but may worsen compression ratios because
it disrupts the delta structure of sorted data.

Block format (little-endian):
  - min_delta: int64 (signed, can be negative)
  - bits_per_value: uint8
  - length: uint32
  - payload: ceil(length * bits_per_value / 8) bytes
"""

import struct
from typing import List


def delta_encode(data: List[int]) -> List[int]:
    """Encode a sequence as deltas: d[0]=data[0], d[i]=data[i]-data[i-1]."""
    if not data:
        return []
    deltas = [data[0]]
    for i in range(1, len(data)):
        deltas.append(data[i] - data[i - 1])
    return deltas


def delta_decode(deltas: List[int]) -> List[int]:
    """Decode deltas back to original: data[i] = sum(deltas[0..i])."""
    if not deltas:
        return []
    data = [deltas[0]]
    for i in range(1, len(deltas)):
        data.append(data[-1] + deltas[i])
    return data


def _pack_bits(values: List[int], bits_per_value: int) -> bytes:
    """Pack non-negative integers into a bit stream.

    Each value uses exactly bits_per_value bits, packed LSB-first.
    """
    if bits_per_value == 0:
        return b''

    result = bytearray()
    current_byte = 0
    bits_in_current = 0

    for val in values:
        for bit_pos in range(bits_per_value):
            bit = (val >> bit_pos) & 1
            current_byte |= (bit << bits_in_current)
            bits_in_current += 1
            if bits_in_current == 8:
                result.append(current_byte)
                current_byte = 0
                bits_in_current = 0

    # Flush remaining bits
    if bits_in_current > 0:
        result.append(current_byte)

    return bytes(result)


def _unpack_bits(payload: bytes, bits_per_value: int, count: int) -> List[int]:
    """Unpack integers from a bit stream."""
    if bits_per_value == 0 or count == 0:
        return [0] * count

    values = []
    bit_index = 0

    for _ in range(count):
        val = 0
        for bit_pos in range(bits_per_value):
            byte_idx = bit_index // 8
            bit_offset = bit_index % 8
            if byte_idx < len(payload):
                bit = (payload[byte_idx] >> bit_offset) & 1
                val |= (bit << bit_pos)
            bit_index += 1
        values.append(val)

    return values


def compress_block(block: List[int]) -> bytes:
    """Compress a single block using delta + FOR + bitpacking.

    Args:
        block: List of integers to compress.

    Returns:
        Compressed bytes with header.
    """
    if not block:
        return struct.pack('<qB I', 0, 0, 0)

    # Delta encode
    deltas = delta_encode(block)

    # Frame of reference: subtract min to make all non-negative
    min_delta = min(deltas)
    refs = [d - min_delta for d in deltas]

    # Determine bits needed
    max_val = max(refs) if refs else 0
    bits_per_value = max_val.bit_length() if max_val > 0 else 1

    # Pack
    payload = _pack_bits(refs, bits_per_value)

    # Header: min_delta (int64), bits_per_value (uint8), length (uint32)
    header = struct.pack('<qB I', min_delta, bits_per_value, len(block))

    return header + payload


def decompress_block(compressed: bytes) -> tuple[List[int], int]:
    """Decompress a single block.

    Returns:
        (decompressed_values, bytes_consumed)
    """
    if len(compressed) < 13:  # header size: 8 + 1 + 4
        return ([], 0)

    min_delta, bits_per_value, length = struct.unpack_from('<qB I', compressed, 0)
    header_size = 13

    if length == 0:
        return ([], header_size)

    # Calculate payload size
    payload_size = (length * bits_per_value + 7) // 8
    payload = compressed[header_size:header_size + payload_size]

    # Unpack
    refs = _unpack_bits(payload, bits_per_value, length)

    # Undo FOR
    deltas = [r + min_delta for r in refs]

    # Undo delta
    data = delta_decode(deltas)

    return (data, header_size + payload_size)


def compress(data: List[int], block_size: int = 512) -> bytes:
    """Compress a list of integers using delta + FOR + bitpacking.

    Data is split into blocks of block_size for independent compression.

    Args:
        data: List of integers to compress.
        block_size: Maximum block size (default 512).

    Returns:
        Compressed bytes.
    """
    if not data:
        return struct.pack('<I', 0)  # 0 blocks

    blocks = []
    for i in range(0, len(data), block_size):
        block = data[i:i + block_size]
        compressed_block = compress_block(block)
        blocks.append(struct.pack('<I', len(compressed_block)) + compressed_block)

    # Prepend block count
    result = struct.pack('<I', len(blocks))
    for b in blocks:
        result += b
    return result


def decompress(compressed: bytes) -> List[int]:
    """Decompress data compressed by compress().

    Args:
        compressed: Compressed bytes from compress().

    Returns:
        Original list of integers.
    """
    if len(compressed) < 4:
        return []

    num_blocks = struct.unpack_from('<I', compressed, 0)[0]
    offset = 4

    if num_blocks == 0:
        return []

    result = []
    for _ in range(num_blocks):
        block_len = struct.unpack_from('<I', compressed, offset)[0]
        offset += 4
        block_data = compressed[offset:offset + block_len]
        values, consumed = decompress_block(block_data)
        result.extend(values)
        offset += block_len

    return result


def compression_ratio(data: List[int], block_size: int = 512) -> float:
    """Compute the compression ratio: original_size / compressed_size.

    A ratio > 1 means compression reduced size.
    Uses the raw byte size of the integers (8 bytes each) as baseline.
    """
    if not data:
        return 1.0
    original_size = len(data) * 8  # int64 per value
    compressed = compress(data, block_size)
    compressed_size = len(compressed)
    if compressed_size == 0:
        return 1.0
    return original_size / compressed_size
