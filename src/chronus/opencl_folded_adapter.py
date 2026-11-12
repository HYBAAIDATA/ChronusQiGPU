"""Period-516 folded F_257[phi] state buffers for the opt-in OpenCL adapter.

Memory folding, not compression: an unbounded scale index s decomposes
uniquely as s = 516 * q + r over the Galois/Pisano period pi(257) = 516 of
phi in F_257[phi] (phi^2 = phi + 1, phi^516 == 1). The canonical residual r
in [0, 515] maps bijectively to one of 516 exact [a, b] uint16 coefficient
pairs, so folding projects the trajectory onto a finite basis with zero
truncation: unfold(fold(s)) == s bit-for-bit.

This module is the single source of truth for the 2,064-byte constant LUT
(516 x ushort2) and the 16-byte FoldedState16 record. The pure-Python
reference path (fold/step/unfold), the pytest parity suite, and the opt-in
OpenCL adapter all consume the exact same bytes.

The module is import-safe without pyopencl, numpy, or an installed chronus
package: every folding primitive is standard-library only, and the physical
adapter imports its accelerator dependencies lazily, raising
HardwareUnavailableError when no GPU stack is present.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from array import array
from typing import Iterator, Sequence

try:  # Fail-closed error types shared with the accelerator backends.
    from chronus.backends.lattice import (
        HardwareUnavailableError,
        ParityVerificationError,
    )
except ImportError:  # Standalone use of the pure folding core only.

    class HardwareUnavailableError(RuntimeError):
        """A requested physical device or its driver is unavailable."""

    class ParityVerificationError(RuntimeError):
        """Device output differs from the exact mathematical reference."""


MOD = 257
PISANO_PERIOD = 516
HALF_PERIOD = 258

#: A single 64-bit epoch lane holds exact quotients up to 2**64 - 1, covering
#: every scale index up to 516 * (2**64 - 1) + 515 ~= 9.518e21 (including the
#: 10**20 benchmark vector) without multi-limb splitting.
MAX_EPOCH_Q = (1 << 64) - 1
MAX_FOLDABLE_SCALE = PISANO_PERIOD * MAX_EPOCH_Q + (PISANO_PERIOD - 1)

#: 16-byte little-endian record matching OpenCL FoldedState16:
#: Q epoch_q | H r_mod_516 | H coeff_a | H coeff_b | H manifold_flags
FOLDED_STATE_STRUCT = struct.Struct("<QHHHH")
FOLDED_STATE_SIZE = FOLDED_STATE_STRUCT.size
assert FOLDED_STATE_SIZE == 16

#: SHA-256 of the packaged OpenCL kernel source (src/chronus/kernels/pv_folded.cl).
FOLDED_KERNEL_SHA256 = (
    "d0cb785ca6f8632e908886ffc53c062e453695597834601fd88828482d0e338e"
)


def build_canonical_2064b_lut() -> tuple[bytes, tuple[tuple[int, int], ...]]:
    """Generate the read-only 2,064-byte little-endian uint16 F_257[phi] LUT.

    Entry r is [a, b] with a + b*phi == phi^r (mod 257). Generation proves
    period-516 minimality and the residue-256 boundary conditions that make
    uint16 (not uint8) storage mandatory.
    """
    flat_u16 = array("H")
    pairs: list[tuple[int, int]] = []
    a, b = 1, 0
    for k in range(PISANO_PERIOD):
        if k > 0 and (a, b) == (1, 0):
            raise RuntimeError(f"Premature period closure at k={k}")
        pairs.append((a, b))
        flat_u16.append(a)
        flat_u16.append(b)
        a, b = b, (a + b) % MOD
    if (a, b) != (1, 0):
        raise RuntimeError("F_257[phi] does not close at period 516")
    if pairs[HALF_PERIOD] != (MOD - 1, 0) or pairs[HALF_PERIOD - 1] != (1, MOD - 1):
        raise RuntimeError("F_257[phi] residue-256 boundary check failed")
    if sys.byteorder != "little":
        flat_u16.byteswap()
    payload = flat_u16.tobytes()
    if len(payload) != 2064:
        raise RuntimeError(f"LUT payload is {len(payload)} bytes, expected 2064")
    return payload, tuple(pairs)


LUT_2064_BYTES, LUT_TUPLE = build_canonical_2064b_lut()
LUT_SHA256 = hashlib.sha256(LUT_2064_BYTES).hexdigest()


def kernel_source() -> bytes:
    """Return the packaged pv_folded.cl source, digest-pinned."""
    from importlib.resources import files

    source = files("chronus.kernels").joinpath("pv_folded.cl").read_bytes()
    if hashlib.sha256(source).hexdigest() != FOLDED_KERNEL_SHA256:
        raise HardwareUnavailableError("Packaged folded-state kernel digest mismatch")
    return source


def f257_phi_mul(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    """Exact bilinear multiply in F_257[phi]; mirrors the kernel's f257_phi_mul."""
    a0, b0 = x
    a1, b1 = y
    bb = (b0 * b1) % MOD
    return ((a0 * a1 + bb) % MOD, (a0 * b1 + b0 * a1 + bb) % MOD)


def _fold_parts(s: int) -> tuple[int, int, int, int]:
    if not isinstance(s, int) or isinstance(s, bool) or s < 0:
        raise ValueError("Scale index s must be a non-negative integer")
    q, r = divmod(s, PISANO_PERIOD)
    coeff_a, coeff_b = LUT_TUPLE[r]
    return q, r, coeff_a, coeff_b


def fold_scale_index(s: int, flags: int = 0) -> bytes:
    """Fold an arbitrary-precision scale index s >= 0 into a 16-byte record.

    For s > MAX_FOLDABLE_SCALE the epoch quotient is masked to its low
    64-bit limb; track the high limbs host-side and pass them back as
    high_q_limbs to unfold_scale_record.
    """
    q, r, coeff_a, coeff_b = _fold_parts(s)
    if not 0 <= flags <= 0xFFFF:
        raise ValueError("flags must fit in a uint16 lane")
    return FOLDED_STATE_STRUCT.pack(q & MAX_EPOCH_Q, r, coeff_a, coeff_b, flags)


def unfold_scale_record(
    record_16b: bytes | memoryview, high_q_limbs: int = 0
) -> tuple[int, tuple[int, int], int]:
    """Bijective inverse of fold: rebuild s and verify [a, b] parity."""
    epoch_q_low, r, coeff_a, coeff_b, flags = FOLDED_STATE_STRUCT.unpack(record_16b)
    if r >= PISANO_PERIOD:
        raise ValueError(f"Folded residual r={r} is outside [0, {PISANO_PERIOD - 1}]")
    expected_a, expected_b = LUT_TUPLE[r]
    if (coeff_a, coeff_b) != (expected_a, expected_b):
        raise ValueError(
            f"Folded state corruption at r={r}: got [{coeff_a}, {coeff_b}], "
            f"expected [{expected_a}, {expected_b}]"
        )
    if high_q_limbs < 0:
        raise ValueError("high_q_limbs must be non-negative")
    full_q = (high_q_limbs << 64) | epoch_q_low
    exact_s = full_q * PISANO_PERIOD + r
    return exact_s, (coeff_a, coeff_b), flags


def pack_folded_batch(scales: Sequence[int], flags: int = 0) -> bytearray:
    """Pack N scale indices that fit the device epoch lane without truncation."""
    buf = bytearray(len(scales) * FOLDED_STATE_SIZE)
    for i, s in enumerate(scales):
        q, r, coeff_a, coeff_b = _fold_parts(s)
        if q > MAX_EPOCH_Q:
            raise OverflowError("batch scale exceeds the device epoch lane; retain high limbs host-side")
        FOLDED_STATE_STRUCT.pack_into(
            buf, i * FOLDED_STATE_SIZE, q & MAX_EPOCH_Q, r, coeff_a, coeff_b, flags
        )
    return buf


def iter_folded_batch(buf: bytes | bytearray | memoryview) -> Iterator[tuple[int, int, int, int, int]]:
    """Yield (epoch_q, r_mod_516, coeff_a, coeff_b, manifold_flags) per record."""
    if len(buf) % FOLDED_STATE_SIZE:
        raise ValueError("Folded batch length is not a multiple of 16 bytes")
    for offset in range(0, len(buf), FOLDED_STATE_SIZE):
        yield FOLDED_STATE_STRUCT.unpack(buf[offset:offset + FOLDED_STATE_SIZE])


def step_folded_record(record_16b: bytes | memoryview, delta_s: int) -> bytes:
    """Pure-Python device reference: advance one folded state by delta_s.

    Mirrors step_folded_states in pv_folded_states exactly: one div/mod folds
    the jump into (q, r), and [a, b] is refreshed from the same 2,064-byte
    LUT the device reads from constant cache.
    """
    if not isinstance(delta_s, int) or isinstance(delta_s, bool) or delta_s < 0:
        raise ValueError("delta_s must be a non-negative integer")
    # Reject corrupted source coefficients before refreshing them from the LUT.
    unfold_scale_record(record_16b)
    epoch_q, r, _a, _b, flags = FOLDED_STATE_STRUCT.unpack(record_16b)
    if r >= PISANO_PERIOD:
        raise ValueError(f"Folded residual r={r} is outside [0, {PISANO_PERIOD - 1}]")
    dq, dr = divmod(delta_s, PISANO_PERIOD)
    next_r = r + dr
    if next_r >= PISANO_PERIOD:
        next_r -= PISANO_PERIOD
        dq += 1
    epoch_q += dq
    if epoch_q > MAX_EPOCH_Q:
        raise OverflowError("epoch quotient exceeds the 64-bit FoldedState16 lane")
    coeff_a, coeff_b = LUT_TUPLE[next_r]
    return FOLDED_STATE_STRUCT.pack(epoch_q, next_r, coeff_a, coeff_b, flags)


def verify_step_parity(
    inputs: Sequence[bytes | memoryview],
    outputs: Sequence[bytes | memoryview],
    delta_s: int,
) -> None:
    """Fail-closed host parity: recompute every stepped record exactly."""
    if len(inputs) != len(outputs):
        raise ParityVerificationError("output length differs from input length")
    for index, (source, output) in enumerate(zip(inputs, outputs)):
        if step_folded_record(source, delta_s) != bytes(output):
            raise ParityVerificationError(
                f"folded-state step parity failed at index {index}"
            )


class ChronusOpenCLFoldedAdapter:
    """Opt-in OpenCL adapter for folded period-516 state transitions.

    GPU-only: no CPU OpenCL or silent reference fallback. The 2,064-byte LUT
    is pinned in device constant memory once per context; every dispatch is
    verified host-side with verify_step_parity before results are accepted.
    """

    name = "opencl-folded-pv"
    execution_mode = "PHYSICAL_ACCELERATOR"
    kernel_name = "step_folded_states"
    _UINT64_MAX_PLUS_1 = 1 << 64

    def __init__(self) -> None:
        try:
            import numpy as np
            import pyopencl as cl
        except ImportError as exc:
            raise HardwareUnavailableError(
                "Install the accelerator extra to use OpenCL"
            ) from exc
        self._np = np
        self._cl = cl
        source = kernel_source()
        try:
            platforms = cl.get_platforms()
            devices = [
                device
                for platform in platforms
                for device in platform.get_devices()
                if device.type & cl.device_type.GPU
            ]
            if not devices:
                raise HardwareUnavailableError("No OpenCL GPU device is available")
            self.device = devices[0]
            if not self.device.endian_little:
                raise HardwareUnavailableError("folded-state records require a little-endian OpenCL device")
            self.context = cl.Context([self.device])
            self.queue = cl.CommandQueue(self.context)
            self.program = cl.Program(self.context, source.decode("utf-8")).build()
        except cl.Error as exc:
            raise HardwareUnavailableError("OpenCL GPU initialization failed") from exc

        flags = cl.mem_flags
        self._lut_buffer = cl.Buffer(
            self.context,
            flags.READ_ONLY | flags.COPY_HOST_PTR,
            hostbuf=LUT_2064_BYTES,
        )
        self._known_answer_test()

    def _known_answer_test(self) -> None:
        """s = 10**20 folds to q=193798449612403100, r=400, coeff [248, 130]."""
        kat = pack_folded_batch([10**20, 10**18, 516, 0])
        stepped = self._dispatch_once(kat, 10**12)
        verify_step_parity(
            [bytes(kat[i:i + FOLDED_STATE_SIZE]) for i in range(0, len(kat), FOLDED_STATE_SIZE)],
            [bytes(stepped[i:i + FOLDED_STATE_SIZE]) for i in range(0, len(stepped), FOLDED_STATE_SIZE)],
            10**12,
        )
        s, (coeff_a, coeff_b), _flags = unfold_scale_record(stepped[0:FOLDED_STATE_SIZE])
        if s != 10**20 + 10**12 or (coeff_a, coeff_b) != LUT_TUPLE[(400 + (10**12 % 516)) % 516]:
            raise ParityVerificationError("OpenCL folded-state known-answer test failed")

    def _dispatch_once(self, packed_states: bytes | bytearray, delta_s: int) -> bytearray:
        """Single launch with the host-reduced exact quotient and residual."""
        cl, np = self._cl, self._np
        count = len(packed_states) // FOLDED_STATE_SIZE
        flags = cl.mem_flags
        state_buffer = cl.Buffer(
            self.context,
            flags.READ_WRITE | flags.COPY_HOST_PTR,
            hostbuf=packed_states,
        )
        kernel = cl.Kernel(self.program, self.kernel_name)
        kernel(
            self.queue,
            (count,),
            None,
            self._lut_buffer,
            state_buffer,
            np.uint64(delta_s // PISANO_PERIOD),
            np.uint16(delta_s % PISANO_PERIOD),
            np.uint32(count),
        )
        out = bytearray(len(packed_states))
        cl.enqueue_copy(self.queue, out, state_buffer).wait()
        return out

    def step_batch(self, packed_states: bytes | bytearray, delta_s: int) -> bytearray:
        """Advance canonical records with one launch and full host parity.

        Divide the exact integer jump on the host into quotient and residual.
        Validate corruption and epoch overflow before allocating device buffers.
        Records carry only the low epoch limb; higher limbs remain host-owned.
        """
        if type(delta_s) is not int or delta_s < 0:
            raise ValueError("delta_s must be a non-negative integer")
        if len(packed_states) % FOLDED_STATE_SIZE:
            raise ValueError("packed_states length is not a multiple of 16 bytes")
        if len(packed_states) // FOLDED_STATE_SIZE >= 1 << 32:
            raise ValueError("batch count exceeds the uint32 kernel lane")
        if not packed_states:
            return bytearray()
        records_in = [bytes(packed_states[i:i + FOLDED_STATE_SIZE])
                      for i in range(0, len(packed_states), FOLDED_STATE_SIZE)]
        # Preflight before dispatch; the kernel cannot safely report an epoch carry.
        expected = b"".join(step_folded_record(record, delta_s) for record in records_in)
        stepped = self._dispatch_once(packed_states, delta_s)
        if bytes(stepped) != expected:
            raise ParityVerificationError("folded-state batch parity failed")
        return stepped
