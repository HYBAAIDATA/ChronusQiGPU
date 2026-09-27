"""Bounded SHA-256d batches with explicit CPU/OpenCL backend provenance."""

import hashlib
import os
import struct
from pathlib import Path

import numpy as np


def _resolve_kernel_path():
    root = Path(__file__).resolve().parent.parent
    candidates = (
        root / "kernels" / "bitcoin_sha256d.cl",
        root / "iGPU_Accelerator_JV" / "kernels" / "bitcoin_sha256d.cl",
        Path(__file__).resolve().parent / "kernels" / "bitcoin_sha256d.cl",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "SHA-256d kernel not found; checked: " + ", ".join(map(str, candidates))
    )


# HYBA iGPU identity — duplicated from Intelligence/unified_punch.py on
# purpose (hasher must not import sibling Intelligence modules). Same
# HYBA_DEVICE_ALIAS override contract.
DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")


def _hyba_aliases() -> tuple:
    raw = os.environ.get("HYBA_DEVICE_ALIAS", "").strip()
    if raw:
        return tuple(a.strip().lower() for a in raw.split(",") if a.strip())
    return DEFAULT_HYBA_ALIASES


def _require_hyba() -> bool:
    return os.environ.get("HYBA_REQUIRE_HYBA", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _identity_tokens(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    return tuple(token.strip().casefold() for token in raw.split(",") if token.strip())


def _device_matches_identity(dev) -> bool:
    device_name = str(getattr(dev, "name", "")).strip().casefold()
    vendor = str(getattr(dev, "vendor", "")).strip().casefold()
    required_name = os.environ.get("HYBA_DEVICE_NAME", "").strip().casefold()
    required_vendor = os.environ.get("HYBA_DEVICE_VENDOR", "").strip().casefold()
    pci_ids = _identity_tokens("HYBA_DEVICE_PCI_IDS")
    if required_name and device_name != required_name:
        return False
    if required_vendor and required_vendor not in vendor:
        return False
    if pci_ids and not any(token in device_name for token in pci_ids):
        return False
    return True


def _identity_configured() -> bool:
    return bool(
        os.environ.get("HYBA_DEVICE_NAME", "").strip()
        or os.environ.get("HYBA_DEVICE_VENDOR", "").strip()
        or os.environ.get("HYBA_DEVICE_PCI_IDS", "").strip()
    )


def _select_opencl_device(cl, want_gpu_only: bool):
    """Prefer the HYBA iGPU (alias match), else first GPU, else first device.

    ``HYBA_REQUIRE_HYBA`` fails explicitly when no alias-matching device
    enumerates — it never silently hashes on a different device.
    """
    devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    if want_gpu_only:
        devices = [d for d in devices if d.type & cl.device_type.GPU]
    if not devices:
        raise RuntimeError("no requested OpenCL device")
    aliases = _hyba_aliases()
    if _require_hyba() and _identity_configured():
        for dev in devices:
            if _device_matches_identity(dev):
                return dev
        names = [f"{getattr(d, 'vendor', '')}: {getattr(d, 'name', '')}" for d in devices]
        raise RuntimeError(
            "HYBA_REQUIRE_HYBA identity gate rejected all OpenCL devices "
            f"(vendor={os.environ.get('HYBA_DEVICE_VENDOR', '')!r}, "
            f"pci_ids={os.environ.get('HYBA_DEVICE_PCI_IDS', '')!r}, "
            f"name={os.environ.get('HYBA_DEVICE_NAME', '')!r}); found: {names}"
        )
    if _require_hyba():
        for dev in devices:
            name = str(getattr(dev, "name", "")).strip().casefold()
            if any(a and a in name for a in aliases):
                return dev
        names = [str(getattr(d, "name", "")).strip() for d in devices]
        raise RuntimeError(
            "HYBA_REQUIRE_HYBA set but no HYBA-alias OpenCL device "
            f"enumerated (aliases={list(aliases)}); found: {names}"
        )
    for dev in devices:
        name = str(getattr(dev, "name", "")).strip().casefold()
        if any(a and a in name for a in aliases):
            return dev
    gpu = next((d for d in devices if d.type & cl.device_type.GPU), None)
    return gpu if gpu is not None else devices[0]


MAX_BATCH = 65536
GRIND_BATCH = 1 << 20  # grind launch window: amortizes kernel-launch latency
# M32 path: one window may span many launches; each launch is bounded so a
# new pool job is seen within ~1s of kernel time, and every launch boundary
# lands on a 32-step epoch boundary so the on-device traversal is identical
# to the serial solver order end-to-end.
M32_LAUNCH = 1 << 24  # 16M nonces per device launch
M32_WINDOW_MAX = 1 << 27  # 128M nonces per pipeline window call

_SHA256_IV = (
    0x6A09E667,
    0xBB67AE85,
    0x3C6EF372,
    0xA54FF53A,
    0x510E527F,
    0x9B05688C,
    0x1F83D9AB,
    0x5BE0CD19,
)

_SHA256_K = (
    0x428A2F98,
    0x71374491,
    0xB5C0FBCF,
    0xE9B5DBA5,
    0x3956C25B,
    0x59F111F1,
    0x923F82A4,
    0xAB1C5ED5,
    0xD807AA98,
    0x12835B01,
    0x243185BE,
    0x550C7DC3,
    0x72BE5D74,
    0x80DEB1FE,
    0x9BDC06A7,
    0xC19BF174,
    0xE49B69C1,
    0xEFBE4786,
    0x0FC19DC6,
    0x240CA1CC,
    0x2DE92C6F,
    0x4A7484AA,
    0x5CB0A9DC,
    0x76F988DA,
    0x983E5152,
    0xA831C66D,
    0xB00327C8,
    0xBF597FC7,
    0xC6E00BF3,
    0xD5A79147,
    0x06CA6351,
    0x14292967,
    0x27B70A85,
    0x2E1B2138,
    0x4D2C6DFC,
    0x53380D13,
    0x650A7354,
    0x766A0ABB,
    0x81C2C92E,
    0x92722C85,
    0xA2BFE8A1,
    0xA81A664B,
    0xC24B8B70,
    0xC76C51A3,
    0xD192E819,
    0xD6990624,
    0xF40E3585,
    0x106AA070,
    0x19A4C116,
    0x1E376C08,
    0x2748774C,
    0x34B0BCB5,
    0x391C0CB3,
    0x4ED8AA4A,
    0x5B9CCA4F,
    0x682E6FF3,
    0x748F82EE,
    0x78A5636F,
    0x84C87814,
    0x8CC70208,
    0x90BEFFFA,
    0xA4506CEB,
    0xBEF9A3F7,
    0xC67178F2,
)
_NONCE_STRUCT = struct.Struct("<I")


def _rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


def sha256_compress(state, block):
    """One SHA-256 compression: 8-word state + 64-byte block -> 8-word tuple."""
    if len(block) != 64:
        raise ValueError("block must be exactly 64 bytes")
    w = list(struct.unpack(">16I", block)) + [0] * 48
    for i in range(16, 64):
        x, y = w[i - 15], w[i - 2]
        s0 = (_rotr(x, 7) ^ _rotr(x, 18) ^ (x >> 3)) & 0xFFFFFFFF
        s1 = (_rotr(y, 17) ^ _rotr(y, 19) ^ (y >> 10)) & 0xFFFFFFFF
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & 0xFFFFFFFF
    a, b, c, d, e, f, g, h = state
    for i in range(64):
        S1 = (_rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)) & 0xFFFFFFFF
        ch = (e & f) ^ (~e & g)
        t1 = (h + S1 + ch + _SHA256_K[i] + w[i]) & 0xFFFFFFFF
        S0 = (_rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)) & 0xFFFFFFFF
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (S0 + maj) & 0xFFFFFFFF
        h = g
        g = f
        f = e
        e = (d + t1) & 0xFFFFFFFF
        d = c
        c = b
        b = a
        a = (t1 + t2) & 0xFFFFFFFF
    return tuple((v + n) & 0xFFFFFFFF for v, n in zip(state, (a, b, c, d, e, f, g, h)))


def sha256_midstate(header64):
    """First-block compression state of the constant header prefix.

    The prefix (header bytes 0..63) never changes within a job, so it is
    compressed once here instead of once per nonce on the device.
    """
    if len(header64) != 64:
        raise ValueError("midstate prefix must be exactly 64 bytes")
    return struct.pack(">8I", *sha256_compress(_SHA256_IV, header64))


class BitcoinHasher:
    def __init__(self, backend="auto"):
        if backend not in ("auto", "cpu", "opencl", "gpu"):
            raise ValueError("backend must be auto, cpu, opencl or gpu")
        self.kernel_ms = 0.0
        self.launches = 0
        self.backend = "cpu"
        self.device = "CPU (hashlib)"
        self.fallback_reason = None
        if backend == "cpu":
            return
        try:
            import pyopencl as cl

            device = _select_opencl_device(cl, backend == "gpu")
            self.cl = cl
            self.ctx = cl.Context([device])
            self.queue = cl.CommandQueue(
                self.ctx, properties=cl.command_queue_properties.PROFILING_ENABLE
            )
            path = _resolve_kernel_path()
            self.program = cl.Program(self.ctx, path.read_text(encoding="utf-8")).build()
            self.kernel = self.program.bitcoin_sha256d
            self.k_target = getattr(self.program, "bitcoin_sha256d_midstate", None)
            self._init_target_buffers(cl)
            self.backend = "opencl:gpu" if device.type & cl.device_type.GPU else "opencl:cpu"
            self.device = device.name.strip()
            # Fail initialization if the device disagrees with the reference.
            header = bytes(range(80))
            nonces = [0, 1, 0x12345678, 0xFFFFFFFF]
            expected = [self._cpu_hash(header, n) for n in nonces]
            if self.hash_batch(header, nonces) != expected:
                raise RuntimeError("OpenCL SHA-256d self-check failed")
            if self.k_target is not None:
                # The max target accepts every digest; the first probed nonce
                # must win and its digest must match the hashlib reference.
                win, dig, count = self.grind_target_batch(header, b"\xff" * 32, nonces)
                if (win, dig, count) != (nonces[0], expected[0], len(nonces)):
                    raise RuntimeError("OpenCL target-kernel self-check failed")
                if self.k_range is not None:
                    win, dig, count = self.grind_target_range(header, b"\xff" * 32, 0, len(nonces))
                    if (win, dig, count) != (nonces[0], expected[0], len(nonces)):
                        raise RuntimeError("OpenCL range-kernel self-check failed")
        except Exception as exc:
            if backend in ("opencl", "gpu"):
                if _require_hyba():
                    raise RuntimeError(f"HYBA_REQUIRE_HYBA unsatisfiable: {exc}") from exc
                raise
            self.backend = "cpu"
            self.device = "CPU (hashlib)"
            reason = str(exc)
            if _require_hyba():
                reason = f"HYBA_REQUIRE_HYBA unsatisfiable: {reason}"
            self.fallback_reason = reason

    def _init_target_buffers(self, cl):
        """Persistent device buffers for the midstate grind (allocated once)."""
        if self.k_target is None:
            return
        mf = cl.mem_flags
        self._buf_mid = cl.Buffer(self.ctx, mf.READ_ONLY, 32)
        self._buf_header = cl.Buffer(self.ctx, mf.READ_ONLY, 80)
        self._buf_target = cl.Buffer(self.ctx, mf.READ_ONLY, 32)
        self._buf_nonce = cl.Buffer(self.ctx, mf.READ_ONLY, GRIND_BATCH * 4)
        self._buf_hits = cl.Buffer(self.ctx, mf.WRITE_ONLY, GRIND_BATCH)
        self._buf_scratch = cl.Buffer(self.ctx, mf.READ_WRITE, 4)
        self._hits_host = np.zeros(GRIND_BATCH, dtype=np.uint8)
        self._cached_header = None
        self._cached_target = None
        self.k_range = getattr(self.program, "bitcoin_sha256d_range", None)
        self.k_m32 = getattr(self.program, "bitcoin_sha256d_m32", None)
        self._buf_lanes = cl.Buffer(self.ctx, mf.READ_ONLY, 32) if self.k_m32 is not None else None

    @staticmethod
    def _cpu_hash(header, nonce):
        blob = bytearray(header)
        return BitcoinHasher._cpu_hash_into(blob, nonce)

    @staticmethod
    def _cpu_hash_into(blob: bytearray, nonce: int) -> bytes:
        _NONCE_STRUCT.pack_into(blob, 76, int(nonce) & 0xFFFFFFFF)
        view = memoryview(blob)
        return hashlib.sha256(hashlib.sha256(view).digest()).digest()

    def _validate_nonces(self, nonces):
        """Vectorized bounds check for numpy input; per-item for Python lists."""
        if isinstance(nonces, np.ndarray):
            if nonces.dtype != np.uint32:
                nonces = nonces.astype(np.uint64)
            if nonces.size:
                if int(nonces.max()) > 0xFFFFFFFF or int(nonces.min()) < 0:
                    raise ValueError("nonces must be uint32 integers")
            return nonces.astype(np.uint32, copy=False)
        nonces = list(nonces)
        if any(not isinstance(n, int) or not 0 <= n <= 0xFFFFFFFF for n in nonces):
            raise ValueError("nonces must be uint32 integers")
        return np.asarray(nonces, dtype=np.uint32)

    def hash_batch(self, header, nonces):
        if len(header) != 80:
            raise ValueError("header must be exactly 80 bytes")
        nonce_array = self._validate_nonces(nonces)
        if nonce_array.size > MAX_BATCH:
            raise ValueError("batch exceeds 65536 nonces")
        if nonce_array.size == 0:
            return []
        if self.backend == "cpu":
            blob = bytearray(header)
            return [self._cpu_hash_into(blob, int(nonce)) for nonce in nonce_array]
        cl = self.cl
        mf = cl.mem_flags
        header_array = np.frombuffer(header, dtype=np.uint8)
        out = np.empty((int(nonce_array.size), 32), dtype=np.uint8)
        hb = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=header_array)
        nb = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=nonce_array)
        ob = cl.Buffer(self.ctx, mf.WRITE_ONLY, out.nbytes)
        count = int(nonce_array.size)
        evt = self.kernel(self.queue, (count,), None, hb, nb, ob, np.uint32(count))
        evt.wait()
        self.kernel_ms += (evt.profile.end - evt.profile.start) / 1e6
        self.launches += 1
        cl.enqueue_copy(self.queue, out, ob).wait()
        return [row.tobytes() for row in out]

    def grind_target_batch(self, header80, target_be, nonces):
        """Grind a bounded batch with the accept predicate on the device.

        Every digest in the batch is physically computed — ``hashes`` counts
        real work, never skipped work. The kernel writes per-item hit flags;
        the host picks the first hit in probe order (deterministic, identical
        to the serial scan) and re-verifies it with hashlib before returning.
        A device hit that fails the reference recheck raises — nothing is
        ever accepted without double-SHA256 confirming it.

        Host-side costs are minimized: midstate/header/target are uploaded
        once per (header, target) pair and cached on-device; the nonce
        upload, kernel launch and the byte-sized hits readback are the only
        per-batch transfers (the kernel overwrites every flag, so no
        zeroing upload is needed; the in-order queue serializes safely).
        Returns ``(winner_nonce | None, winner_digest | None, hashes)``.
        """
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        nonce_array = self._validate_nonces(nonces)
        n = int(nonce_array.size)
        if n > GRIND_BATCH:
            raise ValueError(f"batch exceeds {GRIND_BATCH} nonces")
        if n == 0:
            return None, None, 0
        if self.backend == "cpu":
            target_int = int.from_bytes(target_be, "big")
            hashes = 0
            blob = bytearray(header80)
            for nonce in nonce_array:
                digest = self._cpu_hash_into(blob, int(nonce))
                hashes += 1
                if int.from_bytes(digest, "little") <= target_int:
                    return int(nonce), digest, hashes
            return None, None, hashes
        cl = self.cl
        if header80 != self._cached_header:
            mid = sha256_midstate(header80[:64])
            cl.enqueue_copy(self.queue, self._buf_mid, np.frombuffer(mid, np.uint8)).wait()
            cl.enqueue_copy(self.queue, self._buf_header, np.frombuffer(header80, np.uint8)).wait()
            self._cached_header = header80
        if target_be != self._cached_target:
            cl.enqueue_copy(self.queue, self._buf_target, np.frombuffer(target_be, np.uint8)).wait()
            self._cached_target = target_be
        cl.enqueue_copy(self.queue, self._buf_nonce, nonce_array)
        evt = self.k_target(
            self.queue,
            (n,),
            None,
            self._buf_mid,
            self._buf_header,
            self._buf_target,
            self._buf_nonce,
            self._buf_hits,
            np.uint32(n),
        )
        evt.wait()
        self.kernel_ms += (evt.profile.end - evt.profile.start) / 1e6
        self.launches += 1
        hits = np.empty(n, dtype=np.uint8)
        cl.enqueue_copy(self.queue, hits, self._buf_hits).wait()
        idx = int(np.argmax(hits))
        if hits[idx]:
            nonce = int(nonce_array[idx])
            blob = header80[:76] + struct.pack("<I", np.uint32(nonce))
            digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
            if digest[::-1] <= target_be:
                return nonce, digest, n
            raise RuntimeError(
                "device reported a hit that fails the hashlib recheck "
                f"(nonce {nonce}) — refusing to accept"
            )
        return None, None, n

    def grind_target_range(self, header80, target_be, base_nonce, count):
        """Contiguous-window grind with on-device nonce derivation.

        The kernel derives ``nonce = (base_nonce + gid) mod 2^32`` itself, so
        nothing but the 4-byte sentinel is uploaded, and the first winning
        index (smallest gid — identical to the serial scan) is reduced
        on-device via ``atomic_min``; the host reads back one uint. Every
        digest in the window is physically computed; the winner is
        re-verified with hashlib before being returned. Consensus remains
        the sole accept authority.

        Returns ``(winner_nonce | None, winner_digest | None, hashes)``.
        """
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        count = int(count)
        base_nonce = int(base_nonce) & 0xFFFFFFFF
        if count <= 0:
            return None, None, 0
        if count > GRIND_BATCH:
            raise ValueError(f"window exceeds {GRIND_BATCH} nonces")
        if self.backend == "cpu":
            # Full-window semantics match the device path: every digest in
            # the window is physically computed and hashes == count; the
            # first hit in probe order wins (identical to atomic_min).
            win_nonce = None
            win_digest = None
            target_int = int.from_bytes(target_be, "big")
            blob = bytearray(header80)
            for i in range(count):
                nonce = (base_nonce + i) & 0xFFFFFFFF
                digest = self._cpu_hash_into(blob, nonce)
                if win_nonce is None and int.from_bytes(digest, "little") <= target_int:
                    win_nonce = nonce
                    win_digest = digest
            return win_nonce, win_digest, count
        if self.k_range is None:
            # Kernel variant absent (stale build): fall back to the flag path.
            nonces = np.arange(base_nonce, base_nonce + count, dtype=np.uint64) & 0xFFFFFFFF
            return self.grind_target_batch(header80, target_be, nonces)
        cl = self.cl
        if header80 != self._cached_header:
            mid = sha256_midstate(header80[:64])
            cl.enqueue_copy(self.queue, self._buf_mid, np.frombuffer(mid, np.uint8)).wait()
            cl.enqueue_copy(self.queue, self._buf_header, np.frombuffer(header80, np.uint8)).wait()
            self._cached_header = header80
        if target_be != self._cached_target:
            cl.enqueue_copy(self.queue, self._buf_target, np.frombuffer(target_be, np.uint8)).wait()
            self._cached_target = target_be
        NO_HIT = 0xFFFFFFFF
        cl.enqueue_copy(self.queue, self._buf_scratch, np.array([NO_HIT], dtype=np.uint32))
        evt = self.k_range(
            self.queue,
            (count,),
            None,
            self._buf_mid,
            self._buf_header,
            self._buf_target,
            np.uint32(base_nonce),
            self._buf_scratch,
            np.uint32(count),
        )
        evt.wait()
        self.kernel_ms += (evt.profile.end - evt.profile.start) / 1e6
        self.launches += 1
        scratch = np.empty(1, dtype=np.uint32)
        cl.enqueue_copy(self.queue, scratch, self._buf_scratch).wait()
        gid = int(scratch[0])
        if gid != NO_HIT:
            nonce = (base_nonce + gid) & 0xFFFFFFFF
            blob = header80[:76] + struct.pack("<I", np.uint32(nonce))
            digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
            if digest[::-1] <= target_be:
                return nonce, digest, count
            raise RuntimeError(
                "device reported a hit that fails the hashlib recheck "
                f"(nonce {nonce}) — refusing to accept"
            )
        return None, None, count

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        """M32/Turing-order grind with on-device nonce derivation.

        The canonical solver walks ``nonce = base + order[step % 32] +
        32*(step / 32)``; this launches the same traversal on-device — the
        32-entry lane permutation is uploaded once (32 bytes) and the kernel
        derives every nonce itself. Covering set is unchanged (each epoch
        covers all 32 residues exactly once) and every digest is physically
        computed. The first winning step index (``atomic_min`` — identical
        to the serial scan) is re-verified with hashlib before returning;
        a device hit that fails the recheck raises.

        ``count`` must be a multiple of 32 so the window ends on a lane
        boundary. Returns ``(winner_nonce | None, winner_digest | None,
        hashes)``.
        """
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be 32 bytes")
        lanes = np.asarray(lane_order, dtype=np.uint8)
        if lanes.size != 32 or sorted(lanes.tolist()) != list(range(32)):
            raise ValueError("lane_order must contain every M32 lane exactly once")
        count = int(count)
        if count <= 0:
            return None, None, 0
        if count % 32:
            raise ValueError("m32 grind window must be a multiple of 32")
        if count > M32_WINDOW_MAX:
            raise ValueError(f"window exceeds {M32_WINDOW_MAX} nonces")
        base_nonce = int(base_nonce) & 0xFFFFFFFF
        target_int = int.from_bytes(target_be, "big")
        if self.backend == "cpu":
            hashes = 0
            blob = bytearray(header80)
            for step in range(count):
                nonce = (base_nonce + int(lanes[step % 32]) + 32 * (step // 32)) & 0xFFFFFFFF
                digest = self._cpu_hash_into(blob, nonce)
                hashes += 1
                if int.from_bytes(digest, "little") <= target_int:
                    return nonce, digest, hashes
            return None, None, hashes
        if getattr(self, "k_m32", None) is None:
            hashes = 0
            done = 0
            lanes64 = lanes.astype(np.uint64)
            while done < count:
                take = min(GRIND_BATCH, count - done)
                steps = np.arange(done, done + take, dtype=np.uint64)
                chunk = (
                    np.uint64(base_nonce)
                    + lanes64[steps & np.uint64(31)]
                    + np.uint64(32) * (steps >> np.uint64(5))
                ) & np.uint64(0xFFFFFFFF)
                winner, digest, hashed = self.grind_target_batch(
                    header80, target_be, chunk.astype(np.uint32, copy=False)
                )
                hashes += hashed
                if winner is not None:
                    return winner, digest, hashes
                done += take
            return None, None, hashes
        cl = self.cl
        if header80 != self._cached_header:
            mid = sha256_midstate(header80[:64])
            cl.enqueue_copy(self.queue, self._buf_mid, np.frombuffer(mid, np.uint8)).wait()
            cl.enqueue_copy(self.queue, self._buf_header, np.frombuffer(header80, np.uint8)).wait()
            self._cached_header = header80
        if target_be != self._cached_target:
            cl.enqueue_copy(self.queue, self._buf_target, np.frombuffer(target_be, np.uint8)).wait()
            self._cached_target = target_be
        cl.enqueue_copy(self.queue, self._buf_lanes, lanes).wait()
        NO_HIT = 0xFFFFFFFF
        # Bound each launch to M32_LAUNCH so job-rotation latency stays
        # bounded; chunk boundaries fall on epoch boundaries (both are
        # multiples of 32) so the on-device order is globally identical to
        # the serial m32 scan.
        done = 0
        while done < count:
            take = min(M32_LAUNCH, count - done)
            launch_base = (base_nonce + done) & 0xFFFFFFFF
            cl.enqueue_copy(self.queue, self._buf_scratch, np.array([NO_HIT], dtype=np.uint32))
            evt = self.k_m32(
                self.queue,
                (take,),
                None,
                self._buf_mid,
                self._buf_header,
                self._buf_target,
                np.uint32(launch_base),
                self._buf_lanes,
                self._buf_scratch,
                np.uint32(take),
            )
            evt.wait()
            self.kernel_ms += (evt.profile.end - evt.profile.start) / 1e6
            self.launches += 1
            scratch = np.empty(1, dtype=np.uint32)
            cl.enqueue_copy(self.queue, scratch, self._buf_scratch).wait()
            gid = int(scratch[0])
            if gid != NO_HIT:
                nonce = (launch_base + int(lanes[gid % 32]) + 32 * (gid // 32)) & 0xFFFFFFFF
                blob = header80[:76] + struct.pack("<I", np.uint32(nonce))
                digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
                if digest[::-1] <= target_be:
                    return nonce, digest, done + take
                raise RuntimeError(
                    "device reported a hit that fails the hashlib recheck "
                    f"(nonce {nonce}) — refusing to accept"
                )
            done += take
        return None, None, count

    def telemetry(self) -> dict:
        """Truthful device/telemetry: the device that actually hashed."""
        return {
            "backend": self.backend,
            "device": self.device,
            "kernel_ms": self.kernel_ms,
            "launches": self.launches,
            "fallback_reason": self.fallback_reason,
        }
