"""
HYBA Storage — Delta+FOR + φ-Fold Pipeline (Corrected)

Bug 3 fix: struct.pack('<q', min_val) for signed 64-bit deltas
NEW fix:  Odd-length fold passes through trailing element
EFF fix:  bits_per_value = max(1, max_val.bit_length()) — no +1
"""

from typing import List, Tuple, Optional, Dict, Any
import struct


class HYBAStorage:
    """
    HYBA Storage Pipeline (Corrected)

    Provides:
    - Delta encoding
    - Frame-of-reference (FOR)
    - Bitpacking (efficient — no wasted safety bit)
    - φ-fold with correct odd-length handling
    """

    def __init__(self, block_size: int = 512):
        self.block_size = block_size
        self.stats = {
            'blocks_compressed': 0,
            'blocks_decoded': 0,
            'total_original_bytes': 0,
            'total_compressed_bytes': 0,
            'avg_ratio': 0.0,
        }
        self._compression_ratios = []

    # ─── Compression ──

    def compress(self, data: List[int], use_fold: bool = False) -> bytes:
        """Compress data using delta+FOR."""
        if not data:
            return b''

        original_bytes = len(data) * 8  # int64 baseline

        if use_fold:
            data = self._fold(data)

        # Split into blocks
        blocks = []
        for i in range(0, len(data), self.block_size):
            block = data[i:i + self.block_size]
            compressed_block = self._compress_block(block)
            blocks.append(struct.pack('<I', len(compressed_block)) + compressed_block)
            self.stats['blocks_compressed'] += 1

        # Prepend block count
        result = struct.pack('<I', len(blocks))
        for b in blocks:
            result += b
        compressed_bytes = len(result)

        self.stats['total_original_bytes'] += original_bytes
        self.stats['total_compressed_bytes'] += compressed_bytes
        ratio = original_bytes / compressed_bytes if compressed_bytes > 0 else 0
        self._compression_ratios.append(ratio)
        self.stats['avg_ratio'] = sum(self._compression_ratios) / len(self._compression_ratios)

        return result

    def _compress_block(self, block: List[int]) -> bytes:
        """Delta + FOR + bitpacking per block (CORRECTED)."""
        if not block:
            return b''

        # Delta encode
        deltas = [block[0]]
        for i in range(1, len(block)):
            deltas.append(block[i] - block[i-1])

        # Frame-of-reference
        min_val = min(deltas)  # Can be negative — Bug 3 fix
        refs = [d - min_val for d in deltas]

        # Bitpack — EFFICIENCY FIX: no +1 safety bit
        max_val = max(refs) if refs else 0
        bits_per_value = max(1, max_val.bit_length())

        # Header: min_delta (int64 signed), bits_per_value (uint8), length (uint32)
        # Bug 3 fix: '<q' for signed min_val instead of '<I'
        header = struct.pack('<qBI', min_val, bits_per_value, len(block))

        # Pack refs into bits
        packed_data = bytearray()
        bit_buffer = 0
        bit_count = 0

        for val in refs:
            bit_buffer |= val << bit_count
            bit_count += bits_per_value
            while bit_count >= 8:
                packed_data.append(bit_buffer & 0xFF)
                bit_buffer >>= 8
                bit_count -= 8

        if bit_count > 0:
            packed_data.append(bit_buffer & 0xFF)

        return header + bytes(packed_data)

    # ─── Decompression ──

    def decompress(self, compressed: bytes, use_fold: bool = False) -> List[int]:
        """Decompress data from bytes (CORRECTED)."""
        if not compressed:
            return []

        if len(compressed) < 4:
            return []

        num_blocks = struct.unpack_from('<I', compressed, 0)[0]
        offset = 4

        if num_blocks == 0:
            return []

        data = []

        for _ in range(num_blocks):
            if offset + 4 > len(compressed):
                break
            block_len = struct.unpack_from('<I', compressed, offset)[0]
            offset += 4

            block_data = compressed[offset:offset + block_len]
            offset += block_len

            values = self._decompress_block(block_data)
            data.extend(values)
            self.stats['blocks_decoded'] += 1

        if use_fold:
            data = self._unfold(data)

        return data

    def _decompress_block(self, block_data: bytes) -> List[int]:
        """Decompress a single block (CORRECTED)."""
        header_size = 13  # int64(8) + uint8(1) + uint32(4)

        if len(block_data) < header_size:
            return []

        # Bug 3 fix: '<q' for signed min_val
        min_val, bits_per_value, block_len = struct.unpack_from('<qBI', block_data, 0)

        if bits_per_value <= 0:
            bits_per_value = 1

        payload = block_data[header_size:]

        # Unpack refs — track bit position correctly
        refs = []
        bit_pos = 0
        mask = (1 << bits_per_value) - 1

        for _ in range(block_len):
            val = 0
            for bit_offset in range(bits_per_value):
                abs_bit = bit_pos + bit_offset
                byte_idx = abs_bit // 8
                bit_in_byte = abs_bit % 8
                if byte_idx < len(payload):
                    bit = (payload[byte_idx] >> bit_in_byte) & 1
                    val |= (bit << bit_offset)
            refs.append(val)
            bit_pos += bits_per_value

        # Undo FOR
        deltas = [r + min_val for r in refs]

        # Undo delta
        block = [deltas[0]] if deltas else []
        for i in range(1, len(deltas)):
            block.append(block[-1] + deltas[i])

        return block

    # ─── φ-Fold (ODD-LENGTH FIX) ──

    def _fold(self, data: List[int]) -> List[int]:
        """
        Apply M_φ fold: (x, y) → (x + y, x)
        CORRECTED: Odd-length arrays pass through the trailing element.
        """
        folded = []
        for i in range(0, len(data) - 1, 2):
            x, y = data[i], data[i+1]
            folded.extend([x + y, x])
        # Pass through trailing element on odd length (no padding)
        if len(data) % 2 == 1:
            folded.append(data[-1])
        return folded

    def _unfold(self, data: List[int]) -> List[int]:
        """
        Inverse of M_φ fold: (u, v) → (v, u - v)
        CORRECTED: Odd-length arrays pass through the trailing element.
        """
        unfolded = []
        for i in range(0, len(data) - 1, 2):
            u, v = data[i], data[i+1]
            unfolded.extend([v, u - v])
        # Pass through trailing element on odd length
        if len(data) % 2 == 1:
            unfolded.append(data[-1])
        return unfolded

    # ─── Utilities ──

    def get_stats(self) -> Dict[str, Any]:
        return {
            'blocks_compressed': self.stats['blocks_compressed'],
            'blocks_decoded': self.stats['blocks_decoded'],
            'total_original_bytes': self.stats['total_original_bytes'],
            'total_compressed_bytes': self.stats['total_compressed_bytes'],
            'avg_compression_ratio': self.stats['avg_ratio'],
        }
