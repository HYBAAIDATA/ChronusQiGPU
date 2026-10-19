"""Chronus-owned native SHA-256d mining execution: CUDA and Metal lanes.

OpenCL is one Chronus mining substrate, not the Chronus architecture. This
module gives the mining path the same first-class, independent execution
surfaces the tensor path gained — Chronus-owned kernels dispatched through
the vendor's own runtime:

* ``ChronusCudaSha256dHasher`` — CUDA C kernels (this file's
  ``_CUDA_SHA256D_SOURCE``) launched through CuPy's CUDA runtime binding.
  The kernel family ports ``chronus/kernels/bitcoin_sha256d.cl`` verbatim:
  same midstate contract, same on-device nonce derivation, same
  ``atomicMin`` first-winner reduction, same per-probe hit flags.
* ``ChronusMetalSha256dHasher`` — Metal shading-language kernels
  (``_METAL_SHA256D_HEADER`` + per-order bodies) compiled by MLX's
  ``mx.fast.metal_kernel``. Winner selection is the same smallest-probe-
  index semantics, carried by per-item hit flags.

Honesty contract — identical to ``mining.bitcoin_hasher.BitcoinHasher``:

* Binding is a capability proof, not an import check. The constructor runs
  the same self-check battery as the OpenCL lane (digest batch vs hashlib,
  midstate batch, contiguous range, golden stride) and *refuses to bind*
  when the device disagrees with the reference oracle.
* No silent substitution. These hashers never fall back to CPU or OpenCL:
  an absent runtime, a failed enumeration, or a failed self-check raises
  ``NativeSha256dUnavailable``. ``backend`` reports the substrate that
  actually hashed.
* The host re-verifies every device-reported winner with hashlib before it
  returns — double-SHA256 remains the sole accept authority on every lane.
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from mining.bitcoin_hasher import (
    GRIND_BATCH,
    M32_LAUNCH,
    M32_WINDOW_MAX,
    MAX_BATCH,
    MEM_SAFETY_FRACTION,
    BitcoinHasher,
    _snap_ladder_index,
    sha256_midstate,
)

_NO_HIT = 0xFFFFFFFF


class NativeSha256dUnavailable(RuntimeError):
    """The requested native mining runtime cannot execute — fail closed."""


@dataclass(frozen=True)
class NativeMiningProbe:
    """Observed availability of one native Chronus mining lane."""

    lane: str
    available: bool
    backend: str | None
    device: str | None
    probed_at: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "available": self.available,
            "backend": self.backend,
            "device": self.device,
            "probed_at": self.probed_at,
            "reason": self.reason,
            "opencl_required": False,
        }


def _load_cupy():
    from chronus.native_tensor import _load_cupy as _load

    return _load()


def _load_mlx():
    import mlx.core as mx

    return mx


# ──────────────────────────── CUDA kernels ──────────────────────────── #
# A verbatim port of chronus/kernels/bitcoin_sha256d.cl: one nonce (or one
# probe step) per thread, identical padding/midstate/accept math, identical
# winner semantics (atomic_min on the smallest probe index; per-probe hit
# flags for gold telemetry). The host re-verifies winners with hashlib.
_CUDA_SHA256D_SOURCE = r"""
typedef unsigned int uint;
typedef unsigned char uchar;
typedef unsigned long long ulong;
#define NO_HIT_INDEX 0xFFFFFFFFu
#define GOLDEN_STRIDE 0x9E3779B9u

__constant__ uint SHA_K[64] = {
  0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
  0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
  0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
  0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
  0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
  0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
  0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
  0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};
__device__ __forceinline__ uint rr(uint x, uint n) { return (x >> n) | (x << (32u - n)); }
__device__ __forceinline__ void sha_init(uint *s) {
  s[0]=0x6a09e667u; s[1]=0xbb67ae85u; s[2]=0x3c6ef372u; s[3]=0xa54ff53au;
  s[4]=0x510e527fu; s[5]=0x9b05688cu; s[6]=0x1f83d9abu; s[7]=0x5be0cd19u;
}
__device__ __forceinline__ void sha_block(uint *s, uint *w) {
  for (int i=16;i<64;i++) {
    uint x=w[i-15], y=w[i-2];
    w[i]=w[i-16]+(rr(x,7)^rr(x,18)^(x>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>10));
  }
  uint a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
  for (int i=0;i<64;i++) {
    uint t1=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^((~e)&g))+SHA_K[i]+w[i];
    uint t2=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c));
    h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
  }
  s[0]+=a;s[1]+=b;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;
}
__device__ __forceinline__ uint load_be(const uchar *p) {
  return ((uint)p[0]<<24)|((uint)p[1]<<16)|((uint)p[2]<<8)|(uint)p[3];
}
// Second-block + final-block compression shared by every grind variant:
// state enters at the midstate, nonce occupies word 3 of the tail block.
__device__ __forceinline__ void sha256d_tail(
    uint *s, const uchar *midstate, const uchar *header, uint n) {
  uint w[64];
  for (int i=0;i<8;i++) s[i]=load_be(midstate+4*i);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
}
// Accept predicate: reversed digest (big-endian words) <= target, inclusive.
__device__ __forceinline__ uint accept_less(const uint *s, const uchar *target) {
  for (int k=0;k<8;k++) {
    uint sv=s[7-k];
    uint rw=((sv&255u)<<24)|((sv&0xff00u)<<8)|((sv>>8)&0xff00u)|(sv>>24);
    uint tw=((uint)target[4*k]<<24)|((uint)target[4*k+1]<<16)
           |((uint)target[4*k+2]<<8)|(uint)target[4*k+3];
    if (rw<tw) return 1u;
    if (rw>tw) return 0u;
  }
  return 1u;
}

extern "C" __global__ void bitcoin_sha256d(
    const uchar *header, const uint *nonces, uchar *digests, uint count) {
  uint gid=blockIdx.x*blockDim.x+threadIdx.x;
  if (gid>=count) return;
  uint s[8], w[64];
  sha_init(s);
  for (int i=0;i<16;i++) w[i]=load_be(header+4*i);
  sha_block(s,w);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  uint n=nonces[gid];
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
  for (int i=0;i<8;i++) {
    digests[gid*32+4*i]=(uchar)(s[i]>>24);
    digests[gid*32+4*i+1]=(uchar)(s[i]>>16);
    digests[gid*32+4*i+2]=(uchar)(s[i]>>8);
    digests[gid*32+4*i+3]=(uchar)s[i];
  }
}

extern "C" __global__ void bitcoin_sha256d_midstate(
    const uchar *midstate, const uchar *header, const uchar *target,
    const uint *nonces, uchar *hits, uint count) {
  uint gid=blockIdx.x*blockDim.x+threadIdx.x;
  if (gid>=count) return;
  uint s[8];
  uint n=nonces[gid];
  sha256d_tail(s, midstate, header, n);
  hits[gid]=accept_less(s,target);
}

extern "C" __global__ void bitcoin_sha256d_range(
    const uchar *midstate, const uchar *header, const uchar *target,
    uint base_nonce, uint *scratch, uint count) {
  uint gid=blockIdx.x*blockDim.x+threadIdx.x;
  if (gid>=count) return;
  uint s[8];
  uint n=base_nonce+gid;
  sha256d_tail(s, midstate, header, n);
  if (accept_less(s,target)) atomicMin(scratch, gid);
}

extern "C" __global__ void bitcoin_sha256d_gold(
    const uchar *midstate, const uchar *header, const uchar *target,
    uint seed, uint *scratch, uchar *hit_flags, uint count) {
  uint gid=blockIdx.x*blockDim.x+threadIdx.x;
  if (gid>=count) return;
  hit_flags[gid]=0u;
  uint s[8];
  uint n=seed+gid*GOLDEN_STRIDE;
  sha256d_tail(s, midstate, header, n);
  if (accept_less(s,target)) {
    atomicMin(&scratch[0], gid);
    hit_flags[gid]=1u;
  }
}

extern "C" __global__ void bitcoin_sha256d_m32(
    const uchar *midstate, const uchar *header, const uchar *target,
    uint base_nonce, const uchar *lane_order, uint *scratch, uint count) {
  uint gid=blockIdx.x*blockDim.x+threadIdx.x;
  if (gid>=count) return;
  uint s[8];
  uint epoch=gid>>5;
  uint n=base_nonce+(uint)lane_order[gid&31u]+32u*epoch;
  sha256d_tail(s, midstate, header, n);
  if (accept_less(s,target)) atomicMin(scratch, gid);
}

extern "C" __global__ void bitcoin_sha256d_hendrix(
    const uchar *midstate, const uchar *header, const uchar *target,
    uint base_nonce, uint window, uint stride, uint position_base,
    uint *scratch, uint count) {
  uint gid=blockIdx.x*blockDim.x+threadIdx.x;
  if (gid>=count) return;
  uint s[8];
  ulong p=(ulong)position_base+(ulong)gid;
  uint n=base_nonce+(uint)((p*(ulong)stride)%(ulong)window);
  sha256d_tail(s, midstate, header, n);
  if (accept_less(s,target)) atomicMin(scratch, gid);
}
"""

# ──────────────────────────── Metal kernels ─────────────────────────── #
# The same work contract in Metal shading language, compiled by MLX's
# mx.fast.metal_kernel: `header` carries the constant table and helpers,
# `source` is the body of a function whose signature MLX generates from
# the input/output names and the thread_position_in_grid attribute.
# Winner selection keeps the serial-scan semantics — the smallest probe
# index wins — via per-item hit flags the host compacts deterministically.
_METAL_SHA256D_HEADER = r"""
#include <metal_stdlib>
using namespace metal;
#define GOLDEN_STRIDE 0x9E3779B9u
constant uint SHA_K[64] = {
  0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
  0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
  0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
  0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
  0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
  0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
  0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
  0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};
static inline uint rr(uint x, uint n) { return (x >> n) | (x << (32u - n)); }
static inline void sha_init(thread uint *s) {
  s[0]=0x6a09e667u; s[1]=0xbb67ae85u; s[2]=0x3c6ef372u; s[3]=0xa54ff53au;
  s[4]=0x510e527fu; s[5]=0x9b05688cu; s[6]=0x1f83d9abu; s[7]=0x5be0cd19u;
}
static inline void sha_block(thread uint *s, thread uint *w) {
  for (int i=16;i<64;i++) {
    uint x=w[i-15], y=w[i-2];
    w[i]=w[i-16]+(rr(x,7)^rr(x,18)^(x>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>10));
  }
  uint a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
  for (int i=0;i<64;i++) {
    uint t1=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^((~e)&g))+SHA_K[i]+w[i];
    uint t2=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c));
    h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
  }
  s[0]+=a;s[1]+=b;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;
}
static inline uint load_be(device const uchar *p) {
  return ((uint)p[0]<<24)|((uint)p[1]<<16)|((uint)p[2]<<8)|(uint)p[3];
}
static inline void sha256d_tail(
    thread uint *s, device const uchar *midstate,
    device const uchar *header, uint n) {
  uint w[64];
  for (int i=0;i<8;i++) s[i]=load_be(midstate+4*i);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
}
static inline uint accept_less(thread const uint *s, device const uchar *target) {
  for (int k=0;k<8;k++) {
    uint sv=s[7-k];
    uint rw=((sv&255u)<<24)|((sv&0xff00u)<<8)|((sv>>8)&0xff00u)|(sv>>24);
    uint tw=((uint)target[4*k]<<24)|((uint)target[4*k+1]<<16)
           |((uint)target[4*k+2]<<8)|(uint)target[4*k+3];
    if (rw<tw) return 1u;
    if (rw>tw) return 0u;
  }
  return 1u;
}
"""

# Full sha256d of the 80-byte header per nonce — the digest oracle lane.
_METAL_DIGEST_SOURCE = r"""
  uint gid = thread_position_in_grid.x;
  uint count = params[0];
  if (gid >= count) return;
  thread uint s[8];
  thread uint w[64];
  sha_init(s);
  for (int i=0;i<16;i++) w[i]=load_be(header+4*i);
  sha_block(s,w);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  uint n=nonces[gid];
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
  for (int i=0;i<8;i++) {
    digests[gid*32+4*i]=(uchar)(s[i]>>24);
    digests[gid*32+4*i+1]=(uchar)(s[i]>>16);
    digests[gid*32+4*i+2]=(uchar)(s[i]>>8);
    digests[gid*32+4*i+3]=(uchar)s[i];
  }
"""

# Explicit nonce list: per-item hit flag (identical accept predicate).
_METAL_BATCH_SOURCE = r"""
  uint gid = thread_position_in_grid.x;
  uint count = params[0];
  if (gid >= count) return;
  hits[gid] = 0u;
  thread uint s[8];
  uint n = nonces[gid];
  sha256d_tail(s, midstate, header, n);
  hits[gid] = accept_less(s, target);
"""

# Contiguous window: nonce = base + gid.
_METAL_RANGE_SOURCE = r"""
  uint gid = thread_position_in_grid.x;
  uint count = params[1];
  if (gid >= count) return;
  hits[gid] = 0u;
  thread uint s[8];
  uint n = params[0] + gid;
  sha256d_tail(s, midstate, header, n);
  hits[gid] = accept_less(s, target);
"""

# M32 lane order: nonce = base + lanes[gid & 31] + 32*(gid >> 5).
_METAL_M32_SOURCE = r"""
  uint gid = thread_position_in_grid.x;
  uint count = params[1];
  if (gid >= count) return;
  hits[gid] = 0u;
  thread uint s[8];
  uint n = params[0] + (uint)lanes[gid & 31u] + 32u * (gid >> 5);
  sha256d_tail(s, midstate, header, n);
  hits[gid] = accept_less(s, target);
"""

# Golden stride: nonce = seed + gid * GOLDEN_STRIDE (odd — a 2^32 bijection).
_METAL_GOLD_SOURCE = r"""
  uint gid = thread_position_in_grid.x;
  uint count = params[1];
  if (gid >= count) return;
  hits[gid] = 0u;
  thread uint s[8];
  uint n = params[0] + gid * GOLDEN_STRIDE;
  sha256d_tail(s, midstate, header, n);
  hits[gid] = accept_less(s, target);
"""

# Hendrix schedule: position p = position_base + gid visits
# nonce = base + (p * stride) % window; the product is taken in 64 bits.
_METAL_HENDRIX_SOURCE = r"""
  uint gid = thread_position_in_grid.x;
  uint count = params[4];
  if (gid >= count) return;
  hits[gid] = 0u;
  thread uint s[8];
  uint base_nonce = params[0];
  uint window = params[1];
  uint stride = params[2];
  uint position_base = params[3];
  ulong p = (ulong)position_base + (ulong)gid;
  uint n = base_nonce + (uint)((p * (ulong)stride) % (ulong)window);
  sha256d_tail(s, midstate, header, n);
  hits[gid] = accept_less(s, target);
"""


def _rotr32(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


class _NativeSha256dHasher:
    """The shared host-side work contract for native mining lanes.

    Substrates implement ``_upload_job``/``_upload_target``/``_launch``/
    ``_digest_batch``/``_device_caps``; every public method here owns the
    same validation, midstate caching, chunking, winner mapping and
    hashlib re-verification the OpenCL lane performs. A device hit that
    fails the reference recheck raises — on every substrate.
    """

    backend = "native"
    _CLOCK_SOURCE = "perf_counter"

    def __init__(self) -> None:
        self.kernel_ms = 0.0
        self.launches = 0
        self.device = "unbound"
        self.fallback_reason: Optional[str] = None
        self._gold_device_run = "NOT_RUN"
        self.grind_batch = GRIND_BATCH
        self.m32_launch = M32_LAUNCH
        self.m32_window_max = M32_WINDOW_MAX
        self.launch_config: dict[str, Any] = {
            "basis": "policy_default",
            "grind_batch": GRIND_BATCH,
            "m32_launch": M32_LAUNCH,
            "m32_window_max": M32_WINDOW_MAX,
        }
        self._cached_header: Optional[bytes] = None
        self._cached_target: Optional[bytes] = None

    GOLDEN_STRIDE = BitcoinHasher.GOLDEN_STRIDE
    GOLD_FIFO_DEPTH = BitcoinHasher.GOLD_FIFO_DEPTH

    @staticmethod
    def gold_seed(header80: bytes, target_be: bytes) -> int:
        return BitcoinHasher.gold_seed(header80, target_be)

    # ── substrate hooks ────────────────────────────────────────────────
    def _upload_job(self, midstate: bytes, header80: bytes) -> None:
        raise NotImplementedError

    def _upload_target(self, target_be: bytes) -> None:
        raise NotImplementedError

    def _digest_batch(self, header80: bytes, nonces: np.ndarray) -> np.ndarray:
        """Return (n, 32) uint8 digests computed on the device."""
        raise NotImplementedError

    def _launch(
        self, order: str, count: int, params: dict[str, Any]
    ) -> tuple[Optional[int], Optional[np.ndarray]]:
        """Dispatch one grind window.

        ``order`` is one of ``batch`` (params["nonces"]), ``contiguous``
        (params["base_nonce"]), ``m32`` (params["base_nonce"],
        params["lane_order"]), ``gold`` (params["seed"]) or ``hendrix``
        (params["base_nonce"], ["window"], ["stride"], ["position_base"]).
        Returns ``(winner_gid | None, hit_flags | None)``; hit flags are
        required for ``batch`` and ``gold`` telemetry.
        """
        raise NotImplementedError

    # ── validation identical to BitcoinHasher ──────────────────────────
    @staticmethod
    def _validate_nonces(nonces) -> np.ndarray:
        """Same vectorized bounds check as BitcoinHasher._validate_nonces."""
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

    @staticmethod
    def _cpu_hash_into(blob: bytearray, nonce: int) -> bytes:
        return BitcoinHasher._cpu_hash_into(blob, nonce)

    def _prepare_job(self, header80: bytes, target_be: bytes) -> None:
        if header80 != self._cached_header:
            self._upload_job(sha256_midstate(header80[:64]), header80)
            self._cached_header = header80
        if target_be != self._cached_target:
            self._upload_target(target_be)
            self._cached_target = target_be

    def _verify_winner(
        self, header80: bytes, target_be: bytes, nonce: int
    ) -> bytes:
        """The sole accept authority — hashlib — re-checks the device hit."""
        blob = header80[:76] + struct.pack("<I", np.uint32(nonce & 0xFFFFFFFF))
        digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        if digest[::-1] <= target_be:
            return digest
        raise RuntimeError(
            "device reported a hit that fails the hashlib recheck "
            f"(nonce {nonce}) — refusing to accept"
        )

    def _winner_nonce(self, order: str, gid: int, params: dict[str, Any]) -> int:
        """Probe index → the nonce the device hashed, per the order rule."""
        if order == "batch":
            return int(params["nonces"][gid]) & 0xFFFFFFFF
        if order == "contiguous":
            return (int(params["base_nonce"]) + gid) & 0xFFFFFFFF
        if order == "m32":
            lanes = params["lane_order"]
            return (
                int(params["base_nonce"]) + int(lanes[gid % 32]) + 32 * (gid // 32)
            ) & 0xFFFFFFFF
        if order == "gold":
            return (int(params["seed"]) + gid * self.GOLDEN_STRIDE) & 0xFFFFFFFF
        if order == "hendrix":
            base = int(params["base_nonce"]) & 0xFFFFFFFF
            window, stride, position = (
                int(params["window"]),
                int(params["stride"]),
                int(params["position_base"]),
            )
            return (base + ((position + gid) * stride) % window) & 0xFFFFFFFF
        raise ValueError(f"unknown grind order {order!r}")

    # ── public surface identical to BitcoinHasher ──────────────────────
    def hash_batch(self, header, nonces):
        if len(header) != 80:
            raise ValueError("header must be exactly 80 bytes")
        nonce_array = self._validate_nonces(nonces)
        if nonce_array.size > MAX_BATCH:
            raise ValueError("batch exceeds 65536 nonces")
        if nonce_array.size == 0:
            return []
        out = self._digest_batch(header, nonce_array)
        return [row.tobytes() for row in np.asarray(out, dtype=np.uint8)]

    def _grind_batch_collect(self, header80, target_be, nonce_array, hit_cap):
        n = int(nonce_array.size)
        self._prepare_job(header80, target_be)
        winner_gid, flags = self._launch("batch", n, {"nonces": nonce_array})
        if flags is None:
            raise NativeSha256dUnavailable(
                "batch grind requires per-probe hit flags from the device"
            )
        flagged = (
            [int(nonce_array[i]) for i in np.flatnonzero(flags)[:hit_cap]]
            if hit_cap
            else []
        )
        if winner_gid is None:
            return None, None, n, flagged
        nonce = self._winner_nonce("batch", winner_gid, {"nonces": nonce_array})
        digest = self._verify_winner(header80, target_be, nonce)
        return nonce, digest, n, flagged

    def grind_target_batch(self, header80, target_be, nonces):
        """Explicit nonce list with the accept predicate on the device."""
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        nonce_array = self._validate_nonces(nonces)
        n = int(nonce_array.size)
        if n > self.grind_batch:
            raise ValueError(f"batch exceeds {self.grind_batch} nonces")
        if n == 0:
            return None, None, 0
        winner, digest, hashed, _hits = self._grind_batch_collect(
            header80, target_be, nonce_array, 0
        )
        return winner, digest, hashed

    def grind_target_range(self, header80, target_be, base_nonce, count):
        """Contiguous window; the device derives nonce = base + gid."""
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        count = int(count)
        base_nonce = int(base_nonce) & 0xFFFFFFFF
        if count <= 0:
            return None, None, 0
        if count > self.grind_batch:
            raise ValueError(f"window exceeds {self.grind_batch} nonces")
        self._prepare_job(header80, target_be)
        params = {"base_nonce": base_nonce}
        winner_gid, _flags = self._launch("contiguous", count, params)
        if winner_gid is None:
            return None, None, count
        nonce = self._winner_nonce("contiguous", winner_gid, params)
        digest = self._verify_winner(header80, target_be, nonce)
        return nonce, digest, count

    def grind_target_range_chunked(
        self, header80, target_be, base_nonce, count, stop_on_first: bool = True
    ):
        """Grind ``count`` nonces in device-sized chunks, covering the span."""
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        total = int(count)
        if total <= 0:
            return None, None, 0
        base = int(base_nonce) & 0xFFFFFFFF
        limit = max(1, int(self.grind_batch))
        hashes = 0
        remaining = total
        offset = 0
        while remaining > 0:
            take = min(limit, remaining)
            win_nonce, win_digest, done = self.grind_target_range(
                header80, target_be, (base + offset) & 0xFFFFFFFF, take
            )
            hashes += int(done or 0)
            if win_nonce is not None:
                if not stop_on_first:
                    return win_nonce, win_digest, hashes
                return win_nonce, win_digest, hashes
            offset += take
            remaining -= take
        return None, None, hashes

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        """M32/Turing lane-order grind with on-device nonce derivation."""
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
        if count > self.m32_window_max:
            raise ValueError(f"window exceeds {self.m32_window_max} nonces")
        base_nonce = int(base_nonce) & 0xFFFFFFFF
        self._prepare_job(header80, target_be)
        done = 0
        while done < count:
            take = min(self.m32_launch, count - done)
            launch_base = (base_nonce + done) & 0xFFFFFFFF
            params = {"base_nonce": launch_base, "lane_order": lanes}
            winner_gid, _flags = self._launch("m32", take, params)
            if winner_gid is not None:
                nonce = self._winner_nonce("m32", winner_gid, params)
                digest = self._verify_winner(header80, target_be, nonce)
                return nonce, digest, done + take
            done += take
        return None, None, count

    @property
    def hendrix_on_device(self) -> bool:
        return self._has_order("hendrix")

    def _has_order(self, order: str) -> bool:
        raise NotImplementedError

    def grind_target_hendrix(
        self, header80, target_be, base_nonce, window, stride, position, count
    ):
        """Hendrix coprime-stride schedule grind — bijection of the window."""
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be 32 bytes")
        window, stride, position, count = (
            int(window),
            int(stride),
            int(position),
            int(count),
        )
        if not 0 < window <= 1 << 32:
            raise ValueError("window must be in (0, 2^32]")
        if math.gcd(stride, window) != 1:
            raise ValueError("stride must be coprime to the window")
        if position < 0 or count < 0 or position + count > window:
            raise ValueError("positions must lie inside the window's schedule")
        if count == 0:
            return None, None, 0
        base_nonce = int(base_nonce) & 0xFFFFFFFF
        if not self.hendrix_on_device:
            # A native lane without the hendrix arm walks the same schedule
            # through the batch grind — identical covering set and order.
            hashes = 0
            done = 0
            while done < count:
                take = min(self.grind_batch, count - done)
                positions = np.arange(position + done, position + done + take, dtype=np.uint64)
                chunk = (
                    np.uint64(base_nonce)
                    + (positions * np.uint64(stride)) % np.uint64(window)
                ) & np.uint64(0xFFFFFFFF)
                winner, digest, hashed = self.grind_target_batch(
                    header80, target_be, chunk.astype(np.uint32, copy=False)
                )
                hashes += hashed
                if winner is not None:
                    return winner, digest, hashes
                done += take
            return None, None, hashes
        self._prepare_job(header80, target_be)
        done = 0
        while done < count:
            take = min(self.m32_launch, count - done)
            params = {
                "base_nonce": base_nonce,
                "window": window & 0xFFFFFFFF,
                "stride": stride % window,
                "position_base": position + done,
            }
            winner_gid, _flags = self._launch("hendrix", take, params)
            if winner_gid is not None:
                nonce = self._winner_nonce("hendrix", winner_gid, params)
                digest = self._verify_winner(header80, target_be, nonce)
                return nonce, digest, done + take
            done += take
        return None, None, count

    def grind_target_gold(self, header80, target_be, count, seed=None):
        """Golden-stride grind — a φ-ordered bijection of the nonce domain."""
        if len(header80) != 80:
            raise ValueError("header must be exactly 80 bytes")
        if len(target_be) != 32:
            raise ValueError("target must be exactly 32 bytes")
        count = int(count)
        if count <= 0:
            return None, None, 0, []
        if count > self.grind_batch:
            raise ValueError(f"window exceeds {self.grind_batch} nonces")
        if seed is None:
            seed = self.gold_seed(header80, target_be)
        seed = int(seed) & 0xFFFFFFFF
        self._prepare_job(header80, target_be)
        params = {"seed": seed}
        winner_gid, flags = self._launch("gold", count, params)
        if flags is None:
            raise NativeSha256dUnavailable(
                "gold grind requires per-probe hit flags from the device"
            )
        stride = self.GOLDEN_STRIDE
        hit_gids = np.flatnonzero(flags)[: self.GOLD_FIFO_DEPTH]
        hit_nonces = [int((seed + int(g) * stride) & 0xFFFFFFFF) for g in hit_gids]
        if winner_gid is None:
            return None, None, count, hit_nonces
        nonce = self._winner_nonce("gold", winner_gid, params)
        digest = self._verify_winner(header80, target_be, nonce)
        return nonce, digest, count, hit_nonces

    # ── bind-time self-check: the elevation gate ───────────────────────
    def _run_self_check(self) -> None:
        """Refuse to bind a device that disagrees with hashlib.

        The same battery the OpenCL lane runs: digest batch, midstate batch
        with the accept predicate, contiguous range, and the golden-stride
        arm. A lane that cannot prove agreement is never reported.
        """
        header = bytes(range(80))
        nonces = [0, 1, 0x12345678, 0xFFFFFFFF]
        expected = [BitcoinHasher._cpu_hash(header, n) for n in nonces]
        if self.hash_batch(header, nonces) != expected:
            raise NativeSha256dUnavailable(
                f"{self.backend} SHA-256d digest self-check failed"
            )
        win, dig, count = self.grind_target_batch(header, b"\xff" * 32, nonces)
        if (win, dig, count) != (nonces[0], expected[0], len(nonces)):
            raise NativeSha256dUnavailable(
                f"{self.backend} target-batch self-check failed"
            )
        if self._has_order("contiguous"):
            win, dig, count = self.grind_target_range(header, b"\xff" * 32, 0, len(nonces))
            if (win, dig, count) != (nonces[0], expected[0], len(nonces)):
                raise NativeSha256dUnavailable(
                    f"{self.backend} range self-check failed"
                )
        if self._has_order("gold"):
            gold_win, gold_dig, gold_n, _hits = self.grind_target_gold(
                header, b"\xff" * 32, 4, seed=0
            )
            exp_nonce = 0 & 0xFFFFFFFF
            if gold_win != exp_nonce or gold_dig != expected[0] or gold_n != 4:
                raise NativeSha256dUnavailable(
                    f"{self.backend} golden-stride self-check failed"
                )
            self._gold_device_run = "PASS"

    def silicon_status(self) -> dict:
        return {
            "kernel": "bitcoin_sha256d_gold",
            "device_run": self._gold_device_run,
            "backend": self.backend,
            "device": self.device,
            "fifo_depth": self.GOLD_FIFO_DEPTH,
            "fifo_depth_basis": "fib(6) — derived from the Lucas pool",
            "theorem_proven": False,
        }

    def telemetry(self) -> dict:
        return {
            "backend": self.backend,
            "device": self.device,
            "kernel_ms": self.kernel_ms,
            "kernel_time_ns": int(self.kernel_ms * 1e6),
            "clock_source": self._CLOCK_SOURCE if self.kernel_ms > 0 else "none",
            "launches": self.launches,
            "launch_config": dict(self.launch_config),
            "fallback_reason": self.fallback_reason,
            "opencl_required": False,
        }


# ════════════════════════════ CUDA lane ═══════════════════════════════ #


class ChronusCudaSha256dHasher(_NativeSha256dHasher):
    """Chronus-owned CUDA C SHA-256d kernels on a physical CUDA device.

    Bound through CuPy's CUDA runtime; the kernels themselves are Chronus
    CUDA C (``_CUDA_SHA256D_SOURCE``) — a verbatim port of the OpenCL work
    contract including the ``atomicMin`` first-winner reduction. Device
    timing uses CUDA events; there is no CPU or OpenCL fallback path in
    this class.
    """

    backend = "cuda"
    _CLOCK_SOURCE = "cuda_event"
    _KERNEL_NAMES = (
        "bitcoin_sha256d",
        "bitcoin_sha256d_midstate",
        "bitcoin_sha256d_range",
        "bitcoin_sha256d_gold",
        "bitcoin_sha256d_m32",
        "bitcoin_sha256d_hendrix",
    )
    _THREADS = 256

    def __init__(self, device_index: Optional[int] = None) -> None:
        super().__init__()
        try:
            from chronus.native_tensor import (
                _best_cuda_device,
                _cupy_property,
                _decode_device_name,
            )

            cp = _load_cupy()
            if device_index is None:
                index, props = _best_cuda_device(cp)
            else:
                index = int(device_index)
                props = dict(cp.cuda.runtime.getDeviceProperties(index))
            device = cp.cuda.Device(index)
            device.use()
            kernels = {
                name: cp.RawKernel(
                    _CUDA_SHA256D_SOURCE, name, options=("--std=c++11",)
                )
                for name in self._KERNEL_NAMES
            }
        except NativeSha256dUnavailable:
            raise
        except Exception as exc:
            raise NativeSha256dUnavailable(
                f"CUDA sha256d lane unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        self.cp = cp
        self._device = device
        self._kernels = kernels
        self.device = _decode_device_name(
            _cupy_property(props, "name", f"cuda:{index}")
        )
        self.device_id = f"cuda:{index}:{self.device}"
        self._derive_launch_sizes(props)
        self._alloc_buffers()
        # The self-check runs on the real kernels — a disagreeing device
        # never binds. It propagates as NativeSha256dUnavailable/RuntimeError.
        try:
            self._run_self_check()
        except NativeSha256dUnavailable:
            raise
        except Exception as exc:
            raise NativeSha256dUnavailable(
                f"CUDA sha256d self-check failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _derive_launch_sizes(self, props: dict) -> None:
        """Launch caps from the measured device memory, snapped to the ladder.

        CUDA exposes ``totalGlobalMem`` but no separate per-allocation cap
        query through the runtime API — the memory floor uses it for both
        bounds and ``max_alloc_basis`` says so honestly.
        """
        try:
            from chronus.native_tensor import _cupy_property

            global_mem = int(_cupy_property(props, "totalGlobalMem", 0) or 0)
        except Exception:
            global_mem = 0
        if global_mem <= 0:
            self.launch_config["reason"] = "device limits unmeasurable"
            return
        mem_floor = int(global_mem * MEM_SAFETY_FRACTION)
        batch_items = mem_floor // 5  # 4B nonce + 1B hit per batch item
        self.grind_batch = _snap_ladder_index(min(GRIND_BATCH, batch_items), 320, GRIND_BATCH)
        m32_epochs = mem_floor // 32
        self.m32_launch = 32 * _snap_ladder_index(
            min(M32_LAUNCH // 32, m32_epochs), 10, M32_LAUNCH // 32
        )
        self.m32_window_max = 32 * _snap_ladder_index(
            min(M32_WINDOW_MAX // 32, m32_epochs), 10, M32_WINDOW_MAX // 32
        )
        self.launch_config = {
            "basis": "measured_device_limits",
            "global_mem": global_mem,
            "max_alloc_basis": "totalGlobalMem (CUDA exposes no per-alloc cap)",
            "safety_fraction": MEM_SAFETY_FRACTION,
            "grind_batch": self.grind_batch,
            "m32_launch": self.m32_launch,
            "m32_window_max": self.m32_window_max,
        }

    def _alloc_buffers(self) -> None:
        cp = self.cp
        self._buf_mid = cp.empty(32, dtype=cp.uint8)
        self._buf_header = cp.empty(80, dtype=cp.uint8)
        self._buf_target = cp.empty(32, dtype=cp.uint8)
        self._buf_nonce = cp.empty(self.grind_batch, dtype=cp.uint32)
        self._buf_hits = cp.empty(self.grind_batch, dtype=cp.uint8)
        self._buf_scratch = cp.empty(2, dtype=cp.uint32)
        self._buf_lanes = cp.empty(32, dtype=cp.uint8)
        self._buf_gold_fifo = cp.empty(self.grind_batch, dtype=cp.uint8)

    # ── substrate hooks ────────────────────────────────────────────────
    def _upload_job(self, midstate: bytes, header80: bytes) -> None:
        self._buf_mid.set(np.frombuffer(midstate, np.uint8))
        self._buf_header.set(np.frombuffer(header80, np.uint8))

    def _upload_target(self, target_be: bytes) -> None:
        self._buf_target.set(np.frombuffer(target_be, np.uint8))

    def _has_order(self, order: str) -> bool:
        return order in {
            "batch",
            "contiguous",
            "m32",
            "gold",
            "hendrix",
        }

    def _run_kernel(self, name: str, count: int, args: tuple) -> None:
        threads = self._THREADS
        blocks = (int(count) + threads - 1) // threads
        with self._device:
            started = self.cp.cuda.Event(enable_timing=True)
            ended = self.cp.cuda.Event(enable_timing=True)
            started.record()
            self._kernels[name]((blocks,), (threads,), args)
            ended.record()
            ended.synchronize()
            try:
                self.kernel_ms += float(
                    self.cp.cuda.get_elapsed_time(started, ended)
                )
            except Exception:
                pass
        self.launches += 1

    def _digest_batch(self, header80: bytes, nonces: np.ndarray) -> np.ndarray:
        cp = self.cp
        n = int(nonces.size)
        with self._device:
            hb = cp.asarray(np.frombuffer(header80, np.uint8))
            nb = cp.asarray(nonces)
            ob = cp.empty(n * 32, dtype=cp.uint8)
        self._run_kernel(
            "bitcoin_sha256d",
            n,
            (hb, nb, ob, np.uint32(n)),
        )
        return np.asarray(ob.get()).reshape(n, 32)

    def _launch(
        self, order: str, count: int, params: dict[str, Any]
    ) -> tuple[Optional[int], Optional[np.ndarray]]:
        if order == "batch":
            nonces = np.asarray(params["nonces"], dtype=np.uint32)
            with self._device:
                self._buf_nonce[:count].set(nonces)
            self._run_kernel(
                "bitcoin_sha256d_midstate",
                count,
                (
                    self._buf_mid,
                    self._buf_header,
                    self._buf_target,
                    self._buf_nonce,
                    self._buf_hits,
                    np.uint32(count),
                ),
            )
            flags = np.asarray(self._buf_hits[:count].get())
            set_flags = np.flatnonzero(flags)
            winner_gid = int(set_flags[0]) if set_flags.size else None
            return winner_gid, flags

        with self._device:
            self._buf_scratch.set(
                np.array([_NO_HIT, 0], dtype=np.uint32)
            )
        flags: Optional[np.ndarray] = None
        if order == "contiguous":
            args = (
                self._buf_mid,
                self._buf_header,
                self._buf_target,
                np.uint32(params["base_nonce"]),
                self._buf_scratch,
                np.uint32(count),
            )
            self._run_kernel("bitcoin_sha256d_range", count, args)
        elif order == "m32":
            lanes = np.asarray(params["lane_order"], dtype=np.uint8)
            with self._device:
                self._buf_lanes.set(lanes)
            args = (
                self._buf_mid,
                self._buf_header,
                self._buf_target,
                np.uint32(params["base_nonce"]),
                self._buf_lanes,
                self._buf_scratch,
                np.uint32(count),
            )
            self._run_kernel("bitcoin_sha256d_m32", count, args)
        elif order == "gold":
            args = (
                self._buf_mid,
                self._buf_header,
                self._buf_target,
                np.uint32(params["seed"]),
                self._buf_scratch,
                self._buf_gold_fifo,
                np.uint32(count),
            )
            self._run_kernel("bitcoin_sha256d_gold", count, args)
            flags = np.asarray(self._buf_gold_fifo[:count].get())
        elif order == "hendrix":
            args = (
                self._buf_mid,
                self._buf_header,
                self._buf_target,
                np.uint32(params["base_nonce"]),
                np.uint32(params["window"]),
                np.uint32(params["stride"]),
                np.uint32(params["position_base"]),
                self._buf_scratch,
                np.uint32(count),
            )
            self._run_kernel("bitcoin_sha256d_hendrix", count, args)
        else:
            raise ValueError(f"unknown grind order {order!r}")
        scratch = np.asarray(self._buf_scratch[:1].get())
        gid = int(scratch[0])
        return (None if gid == _NO_HIT else gid), flags


# ════════════════════════════ Metal lane ══════════════════════════════ #


class ChronusMetalSha256dHasher(_NativeSha256dHasher):
    """Chronus-owned Metal SHA-256d kernels on Apple GPU hardware via MLX.

    ``mx.fast.metal_kernel`` compiles ``_METAL_SHA256D_HEADER`` + the
    per-order bodies and dispatches them on the selected MLX GPU device.
    Winner selection is the serial-scan rule (smallest probe index) carried
    by per-item hit flags; timing is measured wall time around the
    evaluated launch — ``clock_source`` reports ``perf_counter`` honestly.
    """

    backend = "metal"
    _CLOCK_SOURCE = "perf_counter"
    _THREADGROUP = 256

    def __init__(self) -> None:
        super().__init__()
        import platform

        if platform.system() != "Darwin":
            raise NativeSha256dUnavailable(
                "Metal sha256d lane requires Darwin (Apple GPU)"
            )
        try:
            mx = _load_mlx()
            if "gpu" not in str(mx.default_device()).lower():
                raise NativeSha256dUnavailable(
                    "MLX is importable but its active device is not a GPU"
                )
            probe_value = mx.array([1], dtype=mx.uint32) + mx.array(
                [1], dtype=mx.uint32
            )
            mx.eval(probe_value)
            self.mx = mx
            self._mx_device = str(mx.default_device())
            kernels = {
                "digest": mx.fast.metal_kernel(
                    name="chronus_sha256d_digest",
                    input_names=["header", "nonces", "params"],
                    output_names=["digests"],
                    source=_METAL_DIGEST_SOURCE,
                    header=_METAL_SHA256D_HEADER,
                ),
                "batch": mx.fast.metal_kernel(
                    name="chronus_sha256d_batch",
                    input_names=["midstate", "header", "target", "nonces", "params"],
                    output_names=["hits"],
                    source=_METAL_BATCH_SOURCE,
                    header=_METAL_SHA256D_HEADER,
                ),
                "contiguous": mx.fast.metal_kernel(
                    name="chronus_sha256d_range",
                    input_names=["midstate", "header", "target", "params"],
                    output_names=["hits"],
                    source=_METAL_RANGE_SOURCE,
                    header=_METAL_SHA256D_HEADER,
                ),
                "m32": mx.fast.metal_kernel(
                    name="chronus_sha256d_m32",
                    input_names=["midstate", "header", "target", "lanes", "params"],
                    output_names=["hits"],
                    source=_METAL_M32_SOURCE,
                    header=_METAL_SHA256D_HEADER,
                ),
                "gold": mx.fast.metal_kernel(
                    name="chronus_sha256d_gold",
                    input_names=["midstate", "header", "target", "params"],
                    output_names=["hits"],
                    source=_METAL_GOLD_SOURCE,
                    header=_METAL_SHA256D_HEADER,
                ),
                "hendrix": mx.fast.metal_kernel(
                    name="chronus_sha256d_hendrix",
                    input_names=["midstate", "header", "target", "params"],
                    output_names=["hits"],
                    source=_METAL_HENDRIX_SOURCE,
                    header=_METAL_SHA256D_HEADER,
                ),
            }
        except NativeSha256dUnavailable:
            raise
        except Exception as exc:
            raise NativeSha256dUnavailable(
                f"Metal sha256d lane unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        self._kernels = kernels
        machine = platform.machine() or "unknown"
        self.device = f"Apple {machine}"
        self.device_id = f"metal:{machine}:{self._mx_device}"
        self.launch_config["reason"] = (
            "MLX does not expose device memory limits; policy defaults stand"
        )
        try:
            self._run_self_check()
        except NativeSha256dUnavailable:
            raise
        except Exception as exc:
            raise NativeSha256dUnavailable(
                f"Metal sha256d self-check failed: {type(exc).__name__}: {exc}"
            ) from exc

    # ── substrate hooks ────────────────────────────────────────────────
    def _upload_job(self, midstate: bytes, header80: bytes) -> None:
        mx = self.mx
        self._mx_mid = mx.array(np.frombuffer(midstate, np.uint8))
        self._mx_header = mx.array(np.frombuffer(header80, np.uint8))

    def _upload_target(self, target_be: bytes) -> None:
        self._mx_target = self.mx.array(np.frombuffer(target_be, np.uint8))

    def _has_order(self, order: str) -> bool:
        return order in self._kernels

    def _eval_kernel(self, key: str, inputs: list, count: int) -> np.ndarray:
        mx = self.mx
        started = time.perf_counter_ns()
        outputs = self._kernels[key](
            inputs=inputs,
            grid=(int(count), 1, 1),
            threadgroup=(min(self._THREADGROUP, max(1, int(count))), 1, 1),
            output_shapes=[(int(count),)],
            output_dtypes=[mx.uint8],
        )
        mx.eval(outputs[0])
        self.kernel_ms += (time.perf_counter_ns() - started) / 1e6
        self.launches += 1
        return np.asarray(outputs[0], dtype=np.uint8)

    def _digest_batch(self, header80: bytes, nonces: np.ndarray) -> np.ndarray:
        mx = self.mx
        n = int(nonces.size)
        inputs = [
            mx.array(np.frombuffer(header80, np.uint8)),
            mx.array(np.asarray(nonces, dtype=np.uint32)),
            mx.array(np.array([n], dtype=np.uint32)),
        ]
        started = time.perf_counter_ns()
        outputs = self._kernels["digest"](
            inputs=inputs,
            grid=(n, 1, 1),
            threadgroup=(min(self._THREADGROUP, max(1, n)), 1, 1),
            output_shapes=[(n * 32,)],
            output_dtypes=[mx.uint8],
        )
        mx.eval(outputs[0])
        self.kernel_ms += (time.perf_counter_ns() - started) / 1e6
        self.launches += 1
        return np.asarray(outputs[0], dtype=np.uint8).reshape(n, 32)

    def _launch(
        self, order: str, count: int, params: dict[str, Any]
    ) -> tuple[Optional[int], Optional[np.ndarray]]:
        mx = self.mx

        def p32(*values: int) -> Any:
            return mx.array(np.array(values, dtype=np.uint32))

        if order == "batch":
            inputs = [
                self._mx_mid,
                self._mx_header,
                self._mx_target,
                mx.array(np.asarray(params["nonces"], dtype=np.uint32)),
                p32(count),
            ]
        elif order == "contiguous":
            inputs = [
                self._mx_mid,
                self._mx_header,
                self._mx_target,
                p32(params["base_nonce"], count),
            ]
        elif order == "m32":
            inputs = [
                self._mx_mid,
                self._mx_header,
                self._mx_target,
                mx.array(np.asarray(params["lane_order"], dtype=np.uint8)),
                p32(params["base_nonce"], count),
            ]
        elif order == "gold":
            inputs = [
                self._mx_mid,
                self._mx_header,
                self._mx_target,
                p32(params["seed"], count),
            ]
        elif order == "hendrix":
            inputs = [
                self._mx_mid,
                self._mx_header,
                self._mx_target,
                p32(
                    params["base_nonce"],
                    params["window"],
                    params["stride"],
                    params["position_base"],
                    count,
                ),
            ]
        else:
            raise ValueError(f"unknown grind order {order!r}")
        flags = self._eval_kernel(order, inputs, count)
        set_flags = np.flatnonzero(flags)
        winner_gid = int(set_flags[0]) if set_flags.size else None
        return winner_gid, flags


# ═══════════════════════════ probes / factory ═════════════════════════ #


def probe_cuda_mining() -> NativeMiningProbe:
    """Measured CUDA lane availability — binding a hasher is the probe."""
    try:
        hasher = ChronusCudaSha256dHasher()
    except Exception as exc:
        return NativeMiningProbe(
            lane="cuda",
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"CUDA mining probe failed: {type(exc).__name__}: {exc}",
        )
    return NativeMiningProbe(
        lane="cuda",
        available=True,
        backend=hasher.backend,
        device=hasher.device,
        probed_at=time.time(),
        reason="CUDA device bound; kernel self-checks passed",
    )


def probe_metal_mining() -> NativeMiningProbe:
    """Measured Metal lane availability — binding a hasher is the probe."""
    try:
        hasher = ChronusMetalSha256dHasher()
    except Exception as exc:
        return NativeMiningProbe(
            lane="metal",
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"Metal mining probe failed: {type(exc).__name__}: {exc}",
        )
    return NativeMiningProbe(
        lane="metal",
        available=True,
        backend=hasher.backend,
        device=hasher.device,
        probed_at=time.time(),
        reason="Metal device bound; kernel self-checks passed",
    )


__all__ = [
    "ChronusCudaSha256dHasher",
    "ChronusMetalSha256dHasher",
    "NativeMiningProbe",
    "NativeSha256dUnavailable",
    "probe_cuda_mining",
    "probe_metal_mining",
]
