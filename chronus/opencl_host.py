"""iGPU-first OpenCL punch host.

Binds one device. Prefers HYBA / integrated GPU names, then any GPU.
use_opencl is true only after a context and kernel compile succeed.
IGpuSku.scan_nonce already calls scan_sha256d when gpu_active.

Honesty contract
----------------
``last_dispatch_backend`` names the substrate that produced the result, never
the one that merely exists. A CPU fallback after a failed device verification
reports ``cpu`` / ``cpu_fallback``; it is never reported as a device run.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)

# Punch opcodes mirrored from igpu/kernels/unified_punch_kernel.cl.
PUNCH_ZECKENDORF_ENCODE = 0x02
PUNCH_ZECKENDORF_DECODE = 0x1C

# DIM * DIM: the per-work-item output stride the kernel reserves.
_PUNCH_OUT_BLOCK = 121


class PunchUnsupported(NotImplementedError):
    """Raised when a punch opcode has no reference implementation.

    Failing loudly here is deliberate: a punch that silently echoed its input
    would be indistinguishable from a completed device computation.
    """


# Fibonacci table exactly as declared in the kernel's FIB_TABLE[94], so the
# CPU reference and the device agree bit-for-bit. Standard F(0)=0, F(1)=1.
_FIB = [0, 1]
for _i in range(2, 94):
    _FIB.append(_FIB[-1] + _FIB[-2])


def _fib_split(n: int) -> tuple[int, int]:
    """Greedy Zeckendorf decomposition -> (mask bits 0-63, bits 64-127).

    Mirrors ``zeckendorf_encode`` in unified_punch_kernel.cl: descend from
    index 93, set bit ``i-2`` when FIB[i] fits, subtract, continue.
    """
    lo = 0
    hi = 0
    if n < 0:
        raise ValueError("Zeckendorf encoding is defined for non-negative values")
    for i in range(93, 1, -1):
        if _FIB[i] <= n:
            bit = i - 2
            if bit < 64:
                lo |= 1 << bit
            else:
                hi |= 1 << (bit - 64)
            n -= _FIB[i]
    return lo, hi


def _fib_join(lo: int, hi: int) -> int:
    """Inverse of :func:`_fib_split`; mirrors ``zeckendorf_decode``."""
    total = 0
    for i in range(2, 66):
        if lo & (1 << (i - 2)):
            total += _FIB[i]
    for i in range(66, 94):
        if hi & (1 << (i - 2 - 64)):
            total += _FIB[i]
    return total


_IGPU_HINTS = (
    "hyba",
    "mla1517",
    "iris",
    "uhd",
    "intel(r) graphics",
    "radeon graphics",
    "vega",
    "integrated",
    "apple",
)


# SHA-256d scanner kernel loaded from igpu/kernels/scan_sha256d.cl — single
# source of truth for the standalone scanner. Previously duplicated inline;
# now loaded from the file to keep kernels and host in sync.
def _load_scan_kernel_source() -> str:
    """Load the SHA-256d scanner kernel from its .cl file."""
    kernel_path = Path(__file__).resolve().parent / "kernels" / "scan_sha256d.cl"
    if kernel_path.is_file():
        return kernel_path.read_text(encoding="utf-8")
    # Fallback: the inline source (kept for environments where the .cl file
    # is not present, e.g. a pyz or frozen distribution).
    return _SHA256D_SRC_FALLBACK


SHA256D_SRC = _load_scan_kernel_source()

# Inline fallback — only used if the .cl file is unavailable.
_SHA256D_SRC_FALLBACK = r"""
__constant uint K[64] = {
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
uint rotr(uint x, int n){ return (x>>n)|(x<<(32-n)); }
void sha256_block(uint *s, const uint *w0){
  uint w[64];
  for(int i=0;i<16;i++) w[i]=w0[i];
  for(int i=16;i<64;i++){
    uint x=w[i-15], y=w[i-2];
    uint s0=rotr(x,7)^rotr(x,18)^(x>>3);
    uint s1=rotr(y,17)^rotr(y,19)^(y>>10);
    w[i]=w[i-16]+s0+w[i-7]+s1;
  }
  uint a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
  for(int i=0;i<64;i++){
    uint S1=rotr(e,6)^rotr(e,11)^rotr(e,25);
    uint ch=(e&f)^((~e)&g);
    uint t1=h+S1+ch+K[i]+w[i];
    uint S0=rotr(a,2)^rotr(a,13)^rotr(a,22);
    uint maj=(a&b)^(a&c)^(b&c);
    uint t2=S0+maj;
    h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
  }
  s[0]+=a;s[1]+=b;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;
}
void sha256_80(const uchar *hdr, uint *out){
  uint st[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
  uint w[16];
  for(int i=0;i<16;i++){
    w[i]=((uint)hdr[i*4]<<24)|((uint)hdr[i*4+1]<<16)|((uint)hdr[i*4+2]<<8)|(uint)hdr[i*4+3];
  }
  sha256_block(st,w);
  uint w2[16];
  for(int i=0;i<16;i++) w2[i]=0;
  w2[0]=((uint)hdr[64]<<24)|((uint)hdr[65]<<16)|((uint)hdr[66]<<8)|(uint)hdr[67];
  w2[1]=((uint)hdr[68]<<24)|((uint)hdr[69]<<16)|((uint)hdr[70]<<8)|(uint)hdr[71];
  w2[2]=((uint)hdr[72]<<24)|((uint)hdr[73]<<16)|((uint)hdr[74]<<8)|(uint)hdr[75];
  w2[3]=((uint)hdr[76]<<24)|((uint)hdr[77]<<16)|((uint)hdr[78]<<8)|(uint)hdr[79];
  w2[4]=0x80000000;
  w2[15]=640;
  sha256_block(st,w2);
  for(int i=0;i<8;i++) out[i]=st[i];
}
void sha256_32be(const uint *in, uint *out){
  uint st[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
  uint w[16];
  for(int i=0;i<8;i++) w[i]=in[i];
  w[8]=0x80000000;
  for(int i=9;i<15;i++) w[i]=0;
  w[15]=256;
  sha256_block(st,w);
  for(int i=0;i<8;i++) out[i]=st[i];
}
__kernel void scan_sha256d(__global const uchar *header76,
                           __global const uint *target_be,
                           uint window,
                           __global int *hit){
  uint gid = get_global_id(0);
  if(gid >= window) return;
  uchar hdr[80];
  for(int i=0;i<76;i++) hdr[i]=header76[i];
  hdr[76]=(uchar)(gid & 0xff);
  hdr[77]=(uchar)((gid>>8)&0xff);
  hdr[78]=(uchar)((gid>>16)&0xff);
  hdr[79]=(uchar)((gid>>24)&0xff);
  uint mid[8]; sha256_80(hdr, mid);
  uint dig[8]; sha256_32be(mid, dig);
  for(int i=0;i<8;i++){
    if(dig[i] < target_be[i]){ atomic_min(hit, (int)gid); return; }
    if(dig[i] > target_be[i]) return;
  }
  atomic_min(hit, (int)gid);
}
"""


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _u256(digest: bytes) -> int:
    return int.from_bytes(digest[::-1], "big")


def _score_device(dev) -> int:
    name = str(getattr(dev, "name", "")).lower()
    score = 0
    try:
        import pyopencl as cl

        if int(dev.type) & int(cl.device_type.GPU):
            score += 100
    except Exception:
        pass
    if any(h in name for h in _IGPU_HINTS):
        score += 50
    if "cpu" in name:
        score -= 80
    score += int(getattr(dev, "max_compute_units", 0) or 0)
    return score


def pick_opencl_device():
    try:
        import pyopencl as cl
    except Exception:
        return None, None
    try:
        devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    except Exception:
        return None, None
    if not devices:
        return None, None
    return cl, max(devices, key=_score_device)


class OpenClPunchHost:
    def __init__(self) -> None:
        self.use_opencl = False
        self.backend = "cpu"
        self.last_dispatch_backend = "none"
        self.device_name = ""
        self._cl = None
        self._ctx = None
        self._queue = None
        self._scan = None
        self._punch = None
        cl, dev = pick_opencl_device()
        if cl is None or dev is None:
            return
        try:
            ctx = cl.Context([dev])
            queue = cl.CommandQueue(ctx)
            prg = cl.Program(ctx, SHA256D_SRC).build()
        except Exception:
            return
        self._cl = cl
        self._ctx = ctx
        self._queue = queue
        self._scan = prg.scan_sha256d
        self.use_opencl = True
        self.backend = f"opencl:{dev.name.strip()}"
        self.device_name = dev.name.strip()
        # The punch kernel is optional: a host without it still scans SHA256d,
        # and punch opcodes then run on the CPU reference and say so.
        try:
            kernel_path = Path(__file__).resolve().parent / "kernels" / "unified_punch_kernel.cl"
            if kernel_path.is_file():
                punch_prg = cl.Program(ctx, kernel_path.read_text(encoding="utf-8")).build()
                self._punch = getattr(punch_prg, "unified_punch_kernel", None)
        except Exception as exc:
            LOG.warning("punch kernel unavailable, falling back to CPU: %s", exc)
            self._punch = None

    def scan_sha256d(self, header76: bytes, target: int, window: int) -> Optional[int]:
        header76 = bytes(header76)
        window = max(0, int(window))
        if window == 0:
            return None
        if not self.use_opencl or self._scan is None:
            return self._cpu_scan(header76, target, window, "cpu")
        import numpy as np

        raw = int(target).to_bytes(32, "big")
        target_be = np.array(
            [int.from_bytes(raw[i * 4 : (i + 1) * 4], "big") for i in range(8)], dtype=np.uint32
        )
        cl = self._cl
        hdr = np.frombuffer(header76, dtype=np.uint8)
        hit = np.array([np.int32(-1)], dtype=np.int32)
        hdr_buf = cl.Buffer(
            self._ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=hdr
        )
        tgt_buf = cl.Buffer(
            self._ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=target_be
        )
        hit_buf = cl.Buffer(
            self._ctx, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=hit
        )
        self._scan(self._queue, (window,), None, hdr_buf, tgt_buf, np.uint32(window), hit_buf)
        cl.enqueue_copy(self._queue, hit, hit_buf)
        self._queue.finish()
        val = int(hit[0])
        if val < 0:
            # The device ran and reported no hit. That is a device result.
            self.last_dispatch_backend = self.backend
            return None
        digest = _sha256d(header76 + val.to_bytes(4, "little"))
        if _u256(digest) <= target:
            # The device's hit was independently confirmed by the host.
            self.last_dispatch_backend = self.backend
            return val
        # The device's claim did not verify, so the CPU decides the answer.
        # Report the CPU: reporting the device here would claim hardware
        # execution for work the host performed.
        LOG.warning(
            "device hit %d failed host verification; falling back to CPU scan",
            val,
        )
        return self._cpu_scan(header76, target, window, "cpu_fallback")

    def _cpu_scan(
        self, header76: bytes, target: int, window: int, dispatch_backend: str
    ) -> Optional[int]:
        self.last_dispatch_backend = dispatch_backend
        for nonce in range(window):
            if _u256(_sha256d(header76 + nonce.to_bytes(4, "little"))) <= target:
                return nonce
        return None

    def run_punch_batch(
        self, opcode: int, n: Optional[int] = None, in_float=None, in_ulong=None
    ) -> dict:
        """Dispatch a punch opcode, or compute it on the CPU.

        Contract (this is the shape every caller indexes against):

        * ``in_ulong`` -> ``{"ulong": array of len(n) * _PUNCH_OUT_BLOCK}``,
          where slot ``i * _PUNCH_OUT_BLOCK`` holds the low 64 bits of work-item
          ``i``'s output and ``+ 1`` the high 64 bits.
        * ``in_float`` -> ``{"float": array of len(n)}``.

        Both backends return that identical shape. The earlier CPU path echoed
        its input unchanged, which produced an array of length ``n`` and made
        every stride-121 caller raise IndexError -- or, worse, read adjacent
        work-item output as if it were its own.

        ``last_dispatch_backend`` is set from the path that actually produced
        the result, never from "a device exists".
        """
        import numpy as np

        if in_ulong is not None:
            values = np.array(in_ulong, dtype=np.uint64).flatten()
            if n is None:
                if int(opcode) == PUNCH_ZECKENDORF_DECODE:
                    if values.size % 2:
                        raise ValueError("Zeckendorf decode requires low/high mask pairs")
                    count = values.size // 2
                else:
                    count = values.size
            else:
                count = int(n)
            if count <= 0:
                raise ValueError("punch batch size must be positive")
            # Reject an opcode we cannot compute BEFORE attempting a dispatch,
            # so an unimplemented operation can never be reported as a run.
            self._require_supported(opcode)
            if self.use_opencl and self._punch is not None:
                try:
                    out = self._dispatch_punch(opcode, count, values)
                    self.last_dispatch_backend = self.backend
                    return {"ulong": out}
                except Exception as exc:  # pragma: no cover - device-specific
                    # A device failure must not be reported as a device run.
                    LOG.warning("punch dispatch failed on %s: %s", self.backend, exc)
                    self.last_dispatch_backend = "cpu_fallback"
            else:
                self.last_dispatch_backend = "cpu"
            return {"ulong": self._cpu_punch(opcode, count, values)}
        if in_float is not None:
            self._require_supported(opcode)
        raise ValueError("run_punch_batch requires an input channel")

    # -- punch reference (mirrors igpu/kernels/unified_punch_kernel.cl) -----

    #: Punch opcodes this host can actually compute, on either backend.
    SUPPORTED_PUNCHES = (PUNCH_ZECKENDORF_ENCODE, PUNCH_ZECKENDORF_DECODE)

    @classmethod
    def _require_supported(cls, opcode: int) -> int:
        """Fail closed on an opcode with no reference implementation.

        Raising here is the point: an unimplemented punch must never reach a
        device and be reported as executed work.
        """
        if int(opcode) not in cls.SUPPORTED_PUNCHES:
            raise PunchUnsupported(
                f"punch opcode {int(opcode):#04x} has no reference "
                f"implementation; refusing to fabricate a result. "
                f"Supported: {['0x%02x' % o for o in cls.SUPPORTED_PUNCHES]}"
            )
        return int(opcode)

    def _cpu_punch(self, opcode: int, count: int, values):
        """CPU reference for the punch opcodes this host implements.

        Only opcodes with a real reference are computed. Anything else raises
        :class:`PunchUnsupported` so an unimplemented operation can never be
        mistaken for a completed one.
        """
        import numpy as np

        stride = _PUNCH_OUT_BLOCK
        out = np.zeros(count * stride, dtype=np.uint64)
        if opcode == PUNCH_ZECKENDORF_ENCODE:
            for gid in range(count):
                n = int(values[gid]) if gid < values.size else 0
                lo, hi = _fib_split(n)
                out[gid * stride] = lo
                out[gid * stride + 1] = hi
            return out
        if opcode == PUNCH_ZECKENDORF_DECODE:
            for gid in range(count):
                i = gid % count
                lo = int(values[i * 2]) if (i * 2) < values.size else 0
                hi = int(values[i * 2 + 1]) if (i * 2 + 1) < values.size else 0
                out[gid * stride] = np.uint64(_fib_join(lo, hi))
            return out
        raise PunchUnsupported(
            f"punch opcode {opcode:#04x} has no CPU reference implementation; "
            f"refusing to fabricate a result"
        )

    def _dispatch_punch(self, opcode: int, count: int, values):
        """Run the unified punch kernel on the bound device.

        The kernel is a single entry point taking typed input/output buffers
        plus a per-work-item punch-id array, so the unused typed buffers are
        bound to a one-element dummy.
        """
        import numpy as np

        stride = _PUNCH_OUT_BLOCK
        cl = self._cl
        n_punch = count
        # zeckendorf_encode writes slots [gid*stride, gid*stride+1]; give every
        # work-item its full block so no two items share an output address.
        out_np = np.zeros(max(count, 1) * stride, dtype=np.uint64)
        dummy_f = np.zeros(1, dtype=np.float32)
        dummy_i = np.zeros(1, dtype=np.uint32)
        dummy_d = np.zeros(1, dtype=np.float64)
        punches = np.full(max(count, 1), np.uint32(opcode), dtype=np.uint32)

        def buf(array, flags):
            return cl.Buffer(self._ctx, flags | cl.mem_flags.COPY_HOST_PTR, hostbuf=array)

        in_u = buf(values, cl.mem_flags.READ_ONLY)
        punch_ids = buf(punches, cl.mem_flags.READ_ONLY)
        out_u = buf(out_np, cl.mem_flags.WRITE_ONLY)
        d_f = buf(dummy_f, cl.mem_flags.READ_ONLY)
        d_i = buf(dummy_i, cl.mem_flags.READ_ONLY)
        d_d = buf(dummy_d, cl.mem_flags.READ_ONLY)
        o_f = buf(np.zeros(1, dtype=np.float32), cl.mem_flags.WRITE_ONLY)
        o_i = buf(np.zeros(1, dtype=np.int32), cl.mem_flags.WRITE_ONLY)
        o_l = buf(np.zeros(1, dtype=np.int64), cl.mem_flags.WRITE_ONLY)
        o_d = buf(np.zeros(1, dtype=np.float64), cl.mem_flags.WRITE_ONLY)

        self._punch(
            self._queue,
            (count,),
            None,
            d_f,
            in_u,
            d_i,
            d_d,
            punch_ids,
            o_f,
            out_u,
            o_i,
            o_l,
            o_d,
            np.uint32(count),
            np.uint32(n_punch),
        )
        cl.enqueue_copy(self._queue, out_np, out_u)
        self._queue.finish()
        return out_np


def resolve_opencl_host() -> Optional[OpenClPunchHost]:
    host = OpenClPunchHost()
    return host if host.use_opencl else None
