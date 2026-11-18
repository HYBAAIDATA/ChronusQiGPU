"""
Lossless 2-byte-block transform over GL(2, Z/256Z), formally elevated.

We fold, we never truncate.

Algebraic Contract:
  - M15 = M^15 in Gamma(2) <= GL(2, Z/256Z), det(M15) === -1 (mod 256),
    order 128, with Hensel lifts M_k in GL(2, Z/2^k Z) for any k >= 8 via
    c_k = (98^2 - 1) * 219^-1 (mod 2^k).
  - Cayley-Hamilton O(1) inversion: M_k^-1 === M_k - tr(M_k)*I_2 (mod 2^k).
  - No-truncation contract [REVIEW FIX R1]: every production path is the lossless
    bijection on (Z/256Z)^2. The lossy lane-0 projection and its fiber enumeration
    live only in tests/quotient_geometry_audit.py.
  - FoldedRegister7: 7-generator affine register over (Z/2^k Z)^2 folded by M_k.

Wire Framing:
  - v2 (`Folded.to_wire()` / `Folded.from_wire()`):
      `GL2\\x01` (4 B) | flags (1 B) | reserved (3 B) | orig_len (8 B BE)
      | payload (orig_len + (orig_len & 1) B) | CRC-32C (4 B BE)
  - v1 legacy (`to_wire_v1()` / `from_wire_v1()`): 4-byte length prefix + payload.
  - Zero-copy bounded-buffer streaming via `FoldStream` and `UnfoldStream`.
"""

from __future__ import annotations

import ctypes
import os
import struct
from dataclasses import dataclass
from typing import TypeAlias

try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False

MODULUS: int = 256
MASK: int = 0xFF
WIRE_HEADER_SIZE_V1: int = 4
MAX_WIRE_LENGTH_V1: int = 0xFFFF_FFFF

WIRE_MAGIC_V2: bytes = b"GL2\x01"
WIRE_HEADER_STRUCT_V2 = struct.Struct(">4sB3sQ")
WIRE_CRC_STRUCT_V2 = struct.Struct(">I")
WIRE_HEADER_SIZE_V2: int = WIRE_HEADER_STRUCT_V2.size
WIRE_FOOTER_SIZE_V2: int = WIRE_CRC_STRUCT_V2.size
FLAG_LOSSLESS: int = 0x00

Matrix2x2: TypeAlias = tuple[tuple[int, int], tuple[int, int]]
BytesLike: TypeAlias = bytes | bytearray | memoryview


# ---------------------------------------------------------------------------
# 1. Algebraic Core: GL(2, Z/2^k Z), Hensel Lifting & Cayley-Hamilton
# ---------------------------------------------------------------------------

def hensellift_m15(k: int = 8) -> Matrix2x2:
    """Hensel-lift M15 = ((219, 98), (98, 121)) to GL(2, Z/2^k Z) for k >= 8.

    Guarantees M_k === M15 (mod 256), M_k === I_2 (mod 2), det(M_k) === -1 (mod 2^k),
    and maximal 2-group multiplicative order 2^(k-1).
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 8:
        raise ValueError(f"k must be an integer >= 8, got {k!r}")
    mod = 1 << k
    a, b = 219, 98
    c = ((b * b - 1) * pow(a, -1, mod)) % mod
    return ((a, b), (b, c))


def invert_gl2_mod2k(m: Matrix2x2, k: int = 8) -> Matrix2x2:
    """Compute M^-1 in GL(2, Z/2^k Z) and verify M * M^-1 === I_2 (mod 2^k).

    Uses Cayley-Hamilton reduction M^-1 = M - tr(M)*I_2 when det(M) === -1 (mod 2^k),
    and general adjugate inversion det(M)^-1 * adj(M) for arbitrary units.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be an integer >= 1, got {k!r}")
    mod = 1 << k
    mask = mod - 1
    det = (m[0][0] * m[1][1] - m[0][1] * m[1][0]) & mask
    if (det & 1) == 0:
        raise ValueError(f"Matrix is singular mod 2^{k} (even determinant {det})")

    if det == mask:
        tr = (m[0][0] + m[1][1]) & mask
        inv: Matrix2x2 = (
            ((m[0][0] - tr) & mask, m[0][1] & mask),
            (m[1][0] & mask, (m[1][1] - tr) & mask),
        )
    else:
        det_inv = pow(det, -1, mod)
        inv = (
            ((det_inv * m[1][1]) & mask, (det_inv * (-m[0][1])) & mask),
            ((det_inv * (-m[1][0])) & mask, (det_inv * m[0][0]) & mask),
        )

    i00 = (m[0][0] * inv[0][0] + m[0][1] * inv[1][0]) & mask
    i01 = (m[0][0] * inv[0][1] + m[0][1] * inv[1][1]) & mask
    i10 = (m[1][0] * inv[0][0] + m[1][1] * inv[1][0]) & mask
    i11 = (m[1][0] * inv[0][1] + m[1][1] * inv[1][1]) & mask
    if (i00, i01, i10, i11) != (1, 0, 0, 1):
        raise ValueError(f"Matrix failed GL(2, Z/2^{k}Z) inverse verification")
    return inv


M15: Matrix2x2 = hensellift_m15(8)
M15_INV: Matrix2x2 = invert_gl2_mod2k(M15, 8)
# Flattened coefficients used by the NumPy and pure-Python pair kernels.
_FWD_COEFFS: tuple[int, int, int, int] = (M15[0][0], M15[0][1], M15[1][0], M15[1][1])
_INV_COEFFS: tuple[int, int, int, int] = (M15_INV[0][0], M15_INV[0][1], M15_INV[1][0], M15_INV[1][1])


# ---------------------------------------------------------------------------
# 2. CRC-32C (Castagnoli) & Optional Native C/SIMD Binding
# ---------------------------------------------------------------------------

def _build_crc32c_table() -> tuple[int, ...]:
    poly = 0x82F63B78
    tbl = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if (c & 1) else (c >> 1)
        tbl.append(c)
    return tuple(tbl)


_CRC32C_TABLE: tuple[int, ...] = _build_crc32c_table()


def _load_native_lib() -> ctypes.CDLL | None:
    so_path = os.environ.get("GL2_FAST_SO")
    if not so_path or not os.path.exists(so_path):
        return None
    try:
        lib = ctypes.CDLL(so_path)
        lib.gl2_fold_pairs.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        lib.gl2_unfold_pairs.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        lib.gl2_crc32c.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t]
        lib.gl2_crc32c.restype = ctypes.c_uint32
        return lib
    except (OSError, AttributeError):
        # Unloadable library, or a loadable one missing a required symbol:
        # the accelerator is unavailable and the exact Python kernels are used.
        return None


_NATIVE_LIB: ctypes.CDLL | None = _load_native_lib()


# [REVIEW FIX R2] Zero-copy buffer addressing for the native path.
# ctypes `from_buffer` rejects read-only buffers (bytes), and the original code fell back to
# `from_buffer_copy`, which copies the whole input. PyObject_GetBuffer returns the address of the
# exporter's own memory (bytes, bytearray, memoryview slices alike) with no copy. The caller keeps
# the memoryview alive for the duration of the native call, which keeps the export pinned.
class _PyBuffer(ctypes.Structure):
    _fields_ = [
        ("buf", ctypes.c_void_p), ("obj", ctypes.py_object), ("len", ctypes.c_ssize_t),
        ("itemsize", ctypes.c_ssize_t), ("readonly", ctypes.c_int), ("ndim", ctypes.c_int),
        ("format", ctypes.c_char_p), ("shape", ctypes.c_void_p), ("strides", ctypes.c_void_p),
        ("suboffsets", ctypes.c_void_p), ("internal", ctypes.c_void_p),
    ]


_PyObject_GetBuffer = ctypes.pythonapi.PyObject_GetBuffer
_PyObject_GetBuffer.argtypes = [ctypes.py_object, ctypes.POINTER(_PyBuffer), ctypes.c_int]
_PyObject_GetBuffer.restype = ctypes.c_int
_PyBuffer_Release = ctypes.pythonapi.PyBuffer_Release
_PyBuffer_Release.argtypes = [ctypes.POINTER(_PyBuffer)]
_PyBuffer_Release.restype = None
_PyBUF_SIMPLE: int = 0
_PyBUF_WRITABLE: int = 0x0001


def _buffer_address(view: memoryview, *, writable: bool = False) -> int:
    """Address of the first byte of a C-contiguous byte view, without copying."""
    if not view.c_contiguous:
        raise ValueError("native path requires a C-contiguous buffer")
    pb = _PyBuffer()
    if _PyObject_GetBuffer(view, ctypes.byref(pb), _PyBUF_WRITABLE if writable else _PyBUF_SIMPLE) != 0:
        raise BufferError("could not acquire buffer")  # pragma: no cover
    try:
        return int(pb.buf or 0)
    finally:
        _PyBuffer_Release(ctypes.byref(pb))


def _ro_ptr(view: memoryview) -> int:
    """Zero-copy read-only pointer (owner's name). [REVIEW NOTE R2b] The owner's draft used
    ctypes.pythonapi.PyObject_AsReadBuffer. On the review box (CPython 3.13.5) that symbol is still
    exported and returns the correct zero-copy address, so it is NOT a failure here; it is the legacy
    buffer API (dropped from the documented headers since 3.10, kept only for ABI compatibility).
    PyObject_GetBuffer/PyBuffer_Release is the documented equivalent and is used here."""
    return _buffer_address(view)


def _rw_ptr(view: memoryview) -> int:
    """Zero-copy writable pointer; raises BufferError on read-only memory."""
    return _buffer_address(view, writable=True)


def _as_view(raw: BytesLike) -> memoryview:
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise TypeError(f"expected bytes-like object, got {type(raw).__name__}")
    view = memoryview(raw)
    return view if view.format == "B" and view.ndim == 1 else view.cast("B")


def crc32c(data: BytesLike, initial: int = 0) -> int:
    """Compute Castagnoli CRC-32C (hardware SSE4.2/ARMv8 via C lib if loaded, else table)."""
    view = _as_view(data)
    if len(view) == 0:
        return initial & 0xFFFF_FFFF
    if _NATIVE_LIB is not None and view.c_contiguous:
        # [REVIEW FIX R2] zero-copy pointer (was from_buffer_copy for read-only input);
        # strided views take the table path below, which iterates them directly.
        return int(_NATIVE_LIB.gl2_crc32c(initial & 0xFFFF_FFFF, _ro_ptr(view), len(view)))
    c = (initial ^ 0xFFFF_FFFF) & 0xFFFF_FFFF
    tbl = _CRC32C_TABLE
    for b in view:
        c = tbl[(c ^ b) & 0xFF] ^ (c >> 8)
    return (c ^ 0xFFFF_FFFF) & 0xFFFF_FFFF


# ---------------------------------------------------------------------------
# 3. Zero-LUT Pair Transform Kernels (C/SIMD -> NumPy -> Pure Python)
# ---------------------------------------------------------------------------

def _transform_pairs_into(src_pairs: memoryview, dst_pairs: memoryview, forward: bool) -> None:
    """Transform `num_pairs` 2-byte blocks without lookup tables."""
    num_pairs = len(src_pairs) // 2
    if num_pairs == 0:
        return

    if len(dst_pairs) < 2 * num_pairs:
        raise ValueError("destination shorter than source")
    src_v = src_pairs[: 2 * num_pairs]
    dst_v = dst_pairs[: 2 * num_pairs]
    if not src_v.c_contiguous:
        # Strided input: one deliberate contiguous copy; contiguous input stays zero-copy.
        src_v = memoryview(src_v.tobytes())
    if _NATIVE_LIB is not None and dst_v.c_contiguous:
        # [REVIEW FIX R2] zero-copy: pass the exporters' own addresses (was from_buffer_copy of src)
        fn = _NATIVE_LIB.gl2_fold_pairs if forward else _NATIVE_LIB.gl2_unfold_pairs
        fn(_ro_ptr(src_v), _rw_ptr(dst_v), num_pairs)
        return

    if _HAS_NUMPY:
        arr = np.frombuffer(src_v, dtype=np.uint8).reshape(num_pairs, 2)
        out = np.frombuffer(dst_v, dtype=np.uint8).reshape(num_pairs, 2)
        x, y = arr[:, 0], arr[:, 1]
        c00, c01, c10, c11 = (np.uint8(c) for c in (_FWD_COEFFS if forward else _INV_COEFFS))
        out[:, 0] = c00 * x + c01 * y
        out[:, 1] = c10 * x + c11 * y
        return

    m00, m01, m10, m11 = _FWD_COEFFS if forward else _INV_COEFFS
    for i in range(0, 2 * num_pairs, 2):
        x, y = src_v[i], src_v[i + 1]
        dst_v[i] = (m00 * x + m01 * y) & MASK
        dst_v[i + 1] = (m10 * x + m11 * y) & MASK


# ---------------------------------------------------------------------------
# 4. Self-Describing Container & Wire Framing (v2 CRC-32C + v1 Legacy)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Folded:
    """Self-describing folded byte container preserving exact original length."""

    data: bytes
    length: int

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes):
            raise TypeError(f"data must be bytes, got {type(self.data).__name__}")
        if isinstance(self.length, bool) or not isinstance(self.length, int):
            raise TypeError(f"length must be int, got {type(self.length).__name__}")
        if self.length < 0:
            raise ValueError(f"length must be >= 0, got {self.length}")
        expected_size = self.length + (self.length & 1)
        if len(self.data) != expected_size:
            raise ValueError(
                f"data is {len(self.data)} bytes, expected {expected_size} "
                f"for length {self.length}"
            )

    def __len__(self) -> int:
        return self.length

    def to_wire(self) -> bytes:
        """Serialize to v2 SEU-hardened `GL2\\x01` frame with 64-bit length and CRC-32C."""
        header = WIRE_HEADER_STRUCT_V2.pack(WIRE_MAGIC_V2, FLAG_LOSSLESS, b"\x00\x00\x00", self.length)
        crc = crc32c(self.data, crc32c(header))
        return header + self.data + WIRE_CRC_STRUCT_V2.pack(crc)

    def to_wire_v1(self) -> bytes:
        """Serialize to legacy v1 4-byte big-endian length-prefixed wire buffer."""
        if self.length > MAX_WIRE_LENGTH_V1:
            raise OverflowError(f"length {self.length} exceeds v1 4-byte limit ({MAX_WIRE_LENGTH_V1})")
        return self.length.to_bytes(WIRE_HEADER_SIZE_V1, "big") + self.data

    @classmethod
    def from_wire(cls, blob: BytesLike, *, max_length: int | None = None) -> Folded:
        """Deserialize and CRC-32C verify a v2 `GL2\\x01` wire buffer."""
        view = _as_view(blob)
        min_frame = WIRE_HEADER_SIZE_V2 + WIRE_FOOTER_SIZE_V2
        if len(view) < min_frame:
            raise ValueError(f"v2 wire blob shorter than minimum {min_frame}-byte envelope")

        magic, flags, reserved, length = WIRE_HEADER_STRUCT_V2.unpack(view[:WIRE_HEADER_SIZE_V2])
        if magic != WIRE_MAGIC_V2:
            raise ValueError(f"invalid wire magic {magic!r}, expected {WIRE_MAGIC_V2!r}")
        if flags != FLAG_LOSSLESS:
            raise ValueError(f"unsupported wire flags 0x{flags:02x} for lossless Folded")
        if reserved != b"\x00\x00\x00":
            raise ValueError(f"non-zero reserved header bytes {reserved!r}")
        if max_length is not None and length > max_length:
            raise ValueError(f"wire length {length} exceeds configured max_length {max_length}")

        expected_size = length + (length & 1)
        expected_total = WIRE_HEADER_SIZE_V2 + expected_size + WIRE_FOOTER_SIZE_V2
        if len(view) != expected_total:
            raise ValueError(f"wire frame size {len(view)} != expected {expected_total} for length {length}")

        payload_view = view[WIRE_HEADER_SIZE_V2 : WIRE_HEADER_SIZE_V2 + expected_size]
        (expected_crc,) = WIRE_CRC_STRUCT_V2.unpack(view[WIRE_HEADER_SIZE_V2 + expected_size :])
        actual_crc = crc32c(payload_view, crc32c(view[:WIRE_HEADER_SIZE_V2]))
        if actual_crc != expected_crc:
            raise ValueError(f"CRC-32C mismatch: expected 0x{expected_crc:08x}, got 0x{actual_crc:08x}")

        return cls(bytes(payload_view), length)

    @classmethod
    def from_wire_v1(cls, blob: BytesLike, *, max_length: int | None = None) -> Folded:
        """Deserialize a legacy v1 4-byte length-prefixed wire buffer (validates size before copy)."""
        view = _as_view(blob)
        if len(view) < WIRE_HEADER_SIZE_V1:
            raise ValueError(f"v1 wire blob shorter than {WIRE_HEADER_SIZE_V1}-byte length prefix")
        length = int.from_bytes(view[:WIRE_HEADER_SIZE_V1], "big")
        if max_length is not None and length > max_length:
            raise ValueError(f"wire length {length} exceeds configured max_length {max_length}")
        payload = view[WIRE_HEADER_SIZE_V1:]
        expected_size = length + (length & 1)
        if len(payload) != expected_size:
            raise ValueError(f"data is {len(payload)} bytes, expected {expected_size} for length {length}")
        return cls(bytes(payload), length)


# ---------------------------------------------------------------------------
# 5. One-Shot API (`fold`, `unfold`, wire wrappers)
# ---------------------------------------------------------------------------

def fold(raw: BytesLike) -> Folded:
    """Fold bytes losslessly over GL(2, Z/256Z)."""
    view = _as_view(raw)
    n = len(view)
    even_n = n & ~1
    out = bytearray(n + (n & 1))
    _transform_pairs_into(view[:even_n], memoryview(out)[:even_n], forward=True)

    if n & 1:
        x = view[-1]
        out[even_n] = (219 * x) & MASK
        out[even_n + 1] = (98 * x) & MASK

    return Folded(bytes(out), n)


def unfold(folded: Folded) -> bytes:
    """Exact inverse of `fold` with canonical odd-padding verification."""
    if not isinstance(folded, Folded):
        raise TypeError(f"unfold expects a Folded, got {type(folded).__name__}")

    n = folded.length
    if n == 0:
        return b""

    data_view = memoryview(folded.data)
    even_n = n & ~1
    out = bytearray(n)
    _transform_pairs_into(data_view[:even_n], memoryview(out)[:even_n], forward=False)

    if n & 1:
        u, v = data_view[even_n], data_view[even_n + 1]
        x = (135 * u + 98 * v) & MASK
        pad = (98 * u + 37 * v) & MASK
        if pad != 0:
            raise ValueError("non-zero canonical padding byte in odd-length Folded")
        out[even_n] = x

    return bytes(out)


def to_wire(folded: Folded) -> bytes:
    if not isinstance(folded, Folded):
        raise TypeError(f"to_wire expects a Folded, got {type(folded).__name__}")
    return folded.to_wire()


def from_wire(blob: BytesLike, *, max_length: int | None = None) -> Folded:
    return Folded.from_wire(blob, max_length=max_length)


# ---------------------------------------------------------------------------
# 6. Bounded-Buffer Zero-Copy Streaming (`FoldStream`, `UnfoldStream`)
# ---------------------------------------------------------------------------

def _gf2_matrix_times_vec(mat: list[int], vec: int) -> int:
    acc = 0
    idx = 0
    while vec:
        if vec & 1:
            acc ^= mat[idx]
        vec >>= 1
        idx += 1
    return acc


def _gf2_matrix_square(square: list[int], mat: list[int]) -> None:
    for n in range(32):
        square[n] = _gf2_matrix_times_vec(mat, mat[n])


def _crc32c_combine(crc1: int, crc2: int, len2: int) -> int:
    """Combine two CRC-32C checksums in O(log len2) time via GF(2) matrix squaring."""
    if len2 <= 0:
        return crc1 & 0xFFFF_FFFF
    even = [0] * 32
    odd = [0] * 32
    odd[0] = 0x82F63B78
    row = 1
    for n in range(1, 32):
        odd[n] = row
        row <<= 1

    _gf2_matrix_square(even, odd)
    _gf2_matrix_square(odd, even)

    while len2 != 0:
        _gf2_matrix_square(even, odd)
        if len2 & 1:
            crc1 = _gf2_matrix_times_vec(even, crc1)
        len2 >>= 1
        if len2 == 0:
            break
        _gf2_matrix_square(odd, even)
        if len2 & 1:
            crc1 = _gf2_matrix_times_vec(odd, crc1)
        len2 >>= 1

    return (crc1 ^ crc2) & 0xFFFF_FFFF


class FoldStream:
    """Incremental encoder emitting v2 `GL2\\x01` frames in O(chunk) memory.

    Even when total stream length is unknown until EOF, `finalize()` combines the
    16-byte header CRC with the incremental payload CRC in O(log N) operations.
    """

    def __init__(self) -> None:
        self._carry: int | None = None
        self._total_len: int = 0
        self._payload_crc: int = 0
        self._finalized: bool = False

    @property
    def bytes_processed(self) -> int:
        return self._total_len

    def header(self, total_length: int) -> bytes:
        if total_length < 0:
            raise ValueError("total_length must be >= 0")
        return WIRE_HEADER_STRUCT_V2.pack(WIRE_MAGIC_V2, FLAG_LOSSLESS, b"\x00\x00\x00", total_length)

    def update(self, chunk: BytesLike) -> bytes:
        if self._finalized:
            raise RuntimeError("FoldStream already finalized")
        view = _as_view(chunk)
        if len(view) == 0:
            return b""

        self._total_len += len(view)
        offset = 0
        prefix = b""

        if self._carry is not None:
            x, y = self._carry, view[0]
            self._carry = None
            offset = 1
            prefix = bytes(((219 * x + 98 * y) & MASK, (98 * x + 121 * y) & MASK))

        rem = len(view) - offset
        even_rem = rem & ~1
        mid = bytearray(even_rem)
        if even_rem > 0:
            _transform_pairs_into(view[offset : offset + even_rem], memoryview(mid), forward=True)

        if rem & 1:
            self._carry = view[-1]

        out = prefix + bytes(mid)
        if out:
            self._payload_crc = crc32c(out, self._payload_crc)
        return out

    def finalize(self) -> tuple[bytes, bytes]:
        """Flush trailing odd byte and return `(final_payload_bytes, 4_byte_crc32c_trailer)`."""
        if self._finalized:
            raise RuntimeError("FoldStream already finalized")
        self._finalized = True

        tail = b""
        if self._carry is not None:
            x = self._carry
            self._carry = None
            tail = bytes(((219 * x) & MASK, (98 * x) & MASK))
            self._payload_crc = crc32c(tail, self._payload_crc)

        hdr = self.header(self._total_len)
        payload_bytes = self._total_len + (self._total_len & 1)
        full_crc = _crc32c_combine(crc32c(hdr), self._payload_crc, payload_bytes)
        return tail, WIRE_CRC_STRUCT_V2.pack(full_crc)


class UnfoldStream:
    """Incremental decoder & CRC-32C verifier for v2 `GL2\\x01` frames in O(chunk) memory."""

    def __init__(self, *, max_length: int | None = None) -> None:
        self._max_length = max_length
        self._buf = bytearray()
        self._header_parsed = False
        self._orig_length = 0
        self._expected_payload_bytes = 0
        self._payload_consumed = 0
        self._running_crc = 0
        self._finalized = False

    @property
    def original_length(self) -> int | None:
        return self._orig_length if self._header_parsed else None

    def update(self, chunk: BytesLike) -> bytes:
        if self._finalized:
            raise RuntimeError("UnfoldStream already finalized")
        view = _as_view(chunk)
        if len(view) == 0:
            return b""
        self._buf.extend(view)

        if not self._header_parsed:
            if len(self._buf) < WIRE_HEADER_SIZE_V2:
                return b""
            hdr = bytes(self._buf[:WIRE_HEADER_SIZE_V2])
            del self._buf[:WIRE_HEADER_SIZE_V2]
            magic, flags, reserved, orig_len = WIRE_HEADER_STRUCT_V2.unpack(hdr)
            if magic != WIRE_MAGIC_V2:
                raise ValueError(f"invalid wire magic {magic!r}, expected {WIRE_MAGIC_V2!r}")
            if flags != FLAG_LOSSLESS:
                raise ValueError(f"unsupported wire flags 0x{flags:02x}")
            if reserved != b"\x00\x00\x00":
                raise ValueError(f"non-zero reserved header bytes {reserved!r}")
            if self._max_length is not None and orig_len > self._max_length:
                raise ValueError(f"wire length {orig_len} exceeds max_length {self._max_length}")

            self._header_parsed = True
            self._orig_length = orig_len
            self._expected_payload_bytes = orig_len + (orig_len & 1)
            self._running_crc = crc32c(hdr, 0)

        # Bound buffered input by what the frame can still contain (payload + trailer).
        allowed = self._expected_payload_bytes - self._payload_consumed + WIRE_FOOTER_SIZE_V2
        if len(self._buf) > allowed:
            excess = len(self._buf) - allowed
            self._buf.clear()
            self._finalized = True
            raise ValueError(f"{excess} bytes beyond the v2 frame trailer")

        rem_payload = self._expected_payload_bytes - self._payload_consumed
        pairs_bytes = min(len(self._buf), rem_payload) & ~1
        if pairs_bytes == 0:
            return b""

        slice_bytes = bytes(self._buf[:pairs_bytes])
        del self._buf[:pairs_bytes]
        self._running_crc = crc32c(slice_bytes, self._running_crc)
        self._payload_consumed += pairs_bytes

        dec = bytearray(pairs_bytes)
        _transform_pairs_into(memoryview(slice_bytes), memoryview(dec), forward=False)

        if self._payload_consumed == self._expected_payload_bytes and (self._orig_length & 1):
            if dec[-1] != 0:
                raise ValueError("non-zero canonical padding byte in odd-length stream")
            return bytes(dec[:-1])

        return bytes(dec)

    def finalize(self) -> None:
        if self._finalized:
            raise RuntimeError("UnfoldStream already finalized")
        self._finalized = True
        if not self._header_parsed:
            raise ValueError("incomplete v2 header")
        if self._payload_consumed != self._expected_payload_bytes:
            raise ValueError(
                f"truncated payload: got {self._payload_consumed} of {self._expected_payload_bytes} bytes"
            )
        if len(self._buf) != WIRE_FOOTER_SIZE_V2:
            raise ValueError(
                f"expected {WIRE_FOOTER_SIZE_V2}-byte CRC-32C trailer, got {len(self._buf)} trailing bytes"
            )
        (expected_crc,) = WIRE_CRC_STRUCT_V2.unpack(self._buf)
        self._buf.clear()
        if self._running_crc != expected_crc:
            raise ValueError(f"CRC-32C mismatch: expected 0x{expected_crc:08x}, got 0x{self._running_crc:08x}")


# ---------------------------------------------------------------------------
# 7. FoldedRegister7: 7-generator affine register over (Z/2^k Z)^2, folded by M_k
# ---------------------------------------------------------------------------
# Owner's verbatim class (t58u).  Requires: from __future__ import annotations, dataclass,
# TypeAlias, Matrix2x2, hensellift_m15, invert_gl2_mod2k (all defined above in this module).

Vec2: TypeAlias = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FoldedRegister7:
    """
    O(log N) factored 7-generator state (2^7 = 128 virtual states) over (Z/2^k Z)^2.
    Invariant under Hensel-lifted M_k in Gamma(2) <= GL(2, Z/2^k Z) and Cayley-Hamilton
    inverse M_k^-1 = M_k - tr(M_k)*I_2.
    """
    base: Vec2
    generators: tuple[Vec2, Vec2, Vec2, Vec2, Vec2, Vec2, Vec2]
    k: int = 8
    resolved_mask: int = 0
    resolved_bits: int = 0

    def __post_init__(self) -> None:
        if len(self.generators) != 7:
            raise ValueError(f"Expected 7 generators, got {len(self.generators)}")
        if self.k < 8:
            raise ValueError(f"Ring exponent k must be >= 8, got {self.k}")
        if not (0 <= self.resolved_mask <= 0x7F) or not (0 <= self.resolved_bits <= 0x7F):
            raise ValueError("resolved_mask and resolved_bits must be 7-bit integers")

    @classmethod
    def from_domain_offset(cls, domain_base: int, *, k: int = 8) -> FoldedRegister7:
        """Constructs a 128-state domain without enumerating individual states."""
        mask = (1 << k) - 1
        base: Vec2 = ((domain_base >> k) & mask, domain_base & mask)
        gens = tuple((0, (1 << j) & mask) for j in range(7))
        return cls(base=base, generators=gens, k=k)  # type: ignore[arg-type]

    def _apply_mat(self, m: Matrix2x2) -> FoldedRegister7:
        mask = (1 << self.k) - 1
        m00, m01 = m[0]
        m10, m11 = m[1]

        def mv(v: Vec2) -> Vec2:
            return (
                (m00 * v[0] + m01 * v[1]) & mask,
                (m10 * v[0] + m11 * v[1]) & mask,
            )

        return FoldedRegister7(
            base=mv(self.base),
            generators=tuple(mv(g) for g in self.generators),  # type: ignore[arg-type]
            k=self.k,
            resolved_mask=self.resolved_mask,
            resolved_bits=self.resolved_bits,
        )

    def fold_mk(self) -> FoldedRegister7:
        """Applies Hensel-lifted M_k across all 128 virtual states in 8 matvec ops."""
        return self._apply_mat(hensellift_m15(self.k))

    def unfold_mk(self) -> FoldedRegister7:
        """Exact Cayley-Hamilton inverse M_k^-1 = M_k - tr(M_k)*I_2 across all 128 states."""
        mk = hensellift_m15(self.k)
        return self._apply_mat(invert_gl2_mod2k(mk, self.k))

    def collapse_generator(self, idx: int, bit_val: int) -> FoldedRegister7:
        """Collapses generator idx (0..6) to bit_val (0 or 1) in O(1) operations."""
        if not (0 <= idx < 7):
            raise ValueError(f"Generator index must be in 0..6, got {idx}")
        if bit_val not in (0, 1):
            raise ValueError(f"bit_val must be 0 or 1, got {bit_val}")
        bit_flag = 1 << idx
        if (self.resolved_mask & bit_flag) and (((self.resolved_bits >> idx) & 1) != bit_val):
            raise ValueError(f"Contradictory collapse on generator {idx}")

        mask = (1 << self.k) - 1
        gk = self.generators[idx]
        new_base: Vec2 = (
            ((self.base[0] + gk[0]) & mask, (self.base[1] + gk[1]) & mask)
            if bit_val == 1
            else self.base
        )
        new_gens = list(self.generators)
        new_gens[idx] = (0, 0)
        return FoldedRegister7(
            base=new_base,
            generators=tuple(new_gens),  # type: ignore[arg-type]
            k=self.k,
            resolved_mask=self.resolved_mask | bit_flag,
            resolved_bits=(self.resolved_bits & ~bit_flag) | (bit_val << idx),
        )

    @property
    def active_dimension(self) -> int:
        return 7 - self.resolved_mask.bit_count()

    def readout_winner(self) -> tuple[int, Vec2]:
        if self.active_dimension != 0:
            raise RuntimeError(f"{self.active_dimension} generators still active")
        return self.resolved_bits, self.base


# ---------------------------------------------------------------------------
# 8. FoldedRegisterN: N-generator affine register over (Z/2^k Z)^2, folded by M_k
# ---------------------------------------------------------------------------
# Generalisation of the owner's FoldedRegister7 (left untouched above).  All
# arithmetic is integer mod 2^k; no float, no RNG.

ALLOWED_RINGS_K: tuple[int, ...] = (8, 16, 32, 64)
MAX_GENERATORS_N: int = 64
_REGN_HEADER = struct.Struct(">BBQQ")  # k, n, resolved_mask, resolved_bits


@dataclass(frozen=True, slots=True)
class FoldedRegisterN:
    """Factored N-generator state (2^N virtual states) over (Z/2^k Z)^2.

    State index i in [0, 2^N) denotes base + sum_j bit_j(i) * generators[j].
    Folding applies M_k to the base and every generator (N+1 matvecs); by
    linearity that equals folding every one of the 2^N states.

    Wrap note: ``from_domain_offset`` puts the low k bits of ``domain_base`` in
    lane 1 and adds generators (0, 2^j) there, so ``lo + i`` wraps mod 2^k
    inside lane 1 and never carries into lane 0.  For a 32-bit nonce lane at
    k=32 that is exactly nonce arithmetic mod 2^32.
    """

    base: Vec2
    generators: tuple[Vec2, ...]
    k: int = 32
    resolved_mask: int = 0
    resolved_bits: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.k, bool) or self.k not in ALLOWED_RINGS_K:
            raise ValueError(f"k must be one of {ALLOWED_RINGS_K}, got {self.k!r}")
        n = len(self.generators)
        if not 1 <= n <= MAX_GENERATORS_N:
            raise ValueError(f"Expected 1..{MAX_GENERATORS_N} generators, got {n}")
        full = (1 << n) - 1
        if not (0 <= self.resolved_mask <= full) or not (0 <= self.resolved_bits <= full):
            raise ValueError(f"resolved_mask and resolved_bits must be {n}-bit integers")
        if self.resolved_bits & ~self.resolved_mask:
            raise ValueError("resolved_bits set outside resolved_mask")
        mod = 1 << self.k
        for v in (self.base, *self.generators):
            if len(v) != 2 or any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < mod for x in v):
                raise ValueError(f"vector components must be integers in [0, 2^{self.k})")

    @property
    def num_generators(self) -> int:
        return len(self.generators)

    @property
    def active_dimension(self) -> int:
        return self.num_generators - self.resolved_mask.bit_count()

    @classmethod
    def from_domain_offset(cls, domain_base: int, *, num_generators: int = 16, k: int = 32) -> "FoldedRegisterN":
        """2^num_generators consecutive lane-1 values starting at domain_base's low k bits."""
        if isinstance(domain_base, bool) or not isinstance(domain_base, int) or domain_base < 0:
            raise ValueError("domain_base must be a non-negative integer")
        if k not in ALLOWED_RINGS_K:
            raise ValueError(f"k must be one of {ALLOWED_RINGS_K}, got {k!r}")
        if isinstance(num_generators, bool) or not isinstance(num_generators, int) or not 1 <= num_generators <= min(k, MAX_GENERATORS_N):
            # (0, 2^j mod 2^k) is the zero vector for j >= k: states would collide.
            raise ValueError(f"num_generators must be in 1..{min(k, MAX_GENERATORS_N)} for k={k}")
        mask = (1 << k) - 1
        base: Vec2 = ((domain_base >> k) & mask, domain_base & mask)
        gens = tuple((0, 1 << j) for j in range(num_generators))
        return cls(base=base, generators=gens, k=k)

    def _apply_mat(self, m: Matrix2x2) -> "FoldedRegisterN":
        mask = (1 << self.k) - 1
        m00, m01 = m[0]
        m10, m11 = m[1]

        def mv(v: Vec2) -> Vec2:
            return ((m00 * v[0] + m01 * v[1]) & mask, (m10 * v[0] + m11 * v[1]) & mask)

        return FoldedRegisterN(
            base=mv(self.base),
            generators=tuple(mv(g) for g in self.generators),
            k=self.k,
            resolved_mask=self.resolved_mask,
            resolved_bits=self.resolved_bits,
        )

    def fold_mk(self) -> "FoldedRegisterN":
        return self._apply_mat(hensellift_m15(self.k))

    def unfold_mk(self) -> "FoldedRegisterN":
        """Cayley-Hamilton inverse M_k^-1 = M_k - tr(M_k) I_2 (det M_k = -1)."""
        return self._apply_mat(invert_gl2_mod2k(hensellift_m15(self.k), self.k))

    def evaluate_index(self, offset_idx: int) -> Vec2:
        """State value for index offset_idx in O(N) adds.

        Resolved generators contribute their resolved bit (their vector is
        already absorbed into base and zeroed), active ones the bit of offset_idx.
        """
        n = self.num_generators
        if isinstance(offset_idx, bool) or not isinstance(offset_idx, int) or not 0 <= offset_idx < (1 << n):
            raise ValueError(f"offset_idx must be in [0, 2^{n})")
        mask = (1 << self.k) - 1
        x, y = self.base
        for j, g in enumerate(self.generators):
            if (self.resolved_mask >> j) & 1:
                bit = (self.resolved_bits >> j) & 1
            else:
                bit = (offset_idx >> j) & 1
            if bit:
                x += g[0]
                y += g[1]
        return (x & mask, y & mask)

    def collapse_generator(self, idx: int, bit_val: int) -> "FoldedRegisterN":
        n = self.num_generators
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < n:
            raise ValueError(f"Generator index must be in 0..{n - 1}, got {idx}")
        if bit_val not in (0, 1) or isinstance(bit_val, bool):
            raise ValueError(f"bit_val must be 0 or 1, got {bit_val}")
        flag = 1 << idx
        if (self.resolved_mask & flag) and (((self.resolved_bits >> idx) & 1) != bit_val):
            raise ValueError(f"Contradictory collapse on generator {idx}")
        mask = (1 << self.k) - 1
        g = self.generators[idx]
        new_base = ((self.base[0] + g[0]) & mask, (self.base[1] + g[1]) & mask) if bit_val else self.base
        gens = list(self.generators)
        gens[idx] = (0, 0)
        return FoldedRegisterN(
            base=new_base,
            generators=tuple(gens),
            k=self.k,
            resolved_mask=self.resolved_mask | flag,
            resolved_bits=(self.resolved_bits & ~flag) | (bit_val << idx),
        )

    def readout_winner(self) -> tuple[int, Vec2]:
        if self.active_dimension != 0:
            raise RuntimeError(f"{self.active_dimension} generators still active")
        return self.resolved_bits, self.base

    @staticmethod
    def _payload_length(k: int, n: int) -> int:
        return _REGN_HEADER.size + 2 * (k // 8) * (1 + n)

    def to_wire_bytes(self) -> bytes:
        """Big-endian register payload, framed as a lossless GL2\\x01 v2 wire frame."""
        bw = self.k // 8
        parts = [_REGN_HEADER.pack(self.k, self.num_generators, self.resolved_mask, self.resolved_bits)]
        for v in (self.base, *self.generators):
            parts.append(v[0].to_bytes(bw, "big"))
            parts.append(v[1].to_bytes(bw, "big"))
        payload = b"".join(parts)
        if len(payload) != self._payload_length(self.k, self.num_generators):
            raise AssertionError("register payload length invariant")
        return fold(payload).to_wire()

    @classmethod
    def from_wire_bytes(cls, blob: BytesLike) -> "FoldedRegisterN":
        """Verify CRC-32C, unfold, length-check and rebuild; fails closed."""
        payload = unfold(Folded.from_wire(blob))
        if len(payload) < _REGN_HEADER.size:
            raise ValueError("register payload shorter than header")
        k, n, rmask, rbits = _REGN_HEADER.unpack_from(payload, 0)
        if k not in ALLOWED_RINGS_K or not 1 <= n <= MAX_GENERATORS_N:
            raise ValueError("register header out of range")
        if len(payload) != cls._payload_length(k, n):
            raise ValueError(f"register payload length {len(payload)} != {cls._payload_length(k, n)}")
        bw = k // 8
        off = _REGN_HEADER.size
        vecs = []
        for _ in range(n + 1):
            x = int.from_bytes(payload[off:off + bw], "big")
            y = int.from_bytes(payload[off + bw:off + 2 * bw], "big")
            vecs.append((x, y))
            off += 2 * bw
        return cls(base=vecs[0], generators=tuple(vecs[1:]), k=k, resolved_mask=rmask, resolved_bits=rbits)
