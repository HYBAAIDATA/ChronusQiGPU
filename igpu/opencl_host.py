"""iGPU-first OpenCL punch host.

Binds one device. Prefers HYBA / integrated GPU names, then any GPU.
use_opencl is true only after a context and kernel compile succeed.
IGpuSku.scan_nonce already calls scan_sha256d when gpu_active.
"""

from __future__ import annotations

import hashlib
from typing import Optional

_IGPU_HINTS = (
    "hyba", "mla1517", "iris", "uhd", "intel(r) graphics",
    "radeon graphics", "vega", "integrated", "apple",
)

SHA256D_SRC = r"""
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
        self.last_dispatch_backend = "cpu"
        self.device_name = ""
        self._cl = None
        self._ctx = None
        self._queue = None
        self._scan = None
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
        self.last_dispatch_backend = self.backend
        self.device_name = dev.name.strip()

    def scan_sha256d(self, header76: bytes, target: int, window: int) -> Optional[int]:
        header76 = bytes(header76)
        window = max(0, int(window))
        if window == 0:
            return None
        if not self.use_opencl or self._scan is None:
            return self._cpu_scan(header76, target, window)
        import numpy as np

        raw = int(target).to_bytes(32, "big")
        target_be = np.array([int.from_bytes(raw[i * 4 : (i + 1) * 4], "big") for i in range(8)], dtype=np.uint32)
        cl = self._cl
        hdr = np.frombuffer(header76, dtype=np.uint8)
        hit = np.array([np.int32(-1)], dtype=np.int32)
        hdr_buf = cl.Buffer(self._ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=hdr)
        tgt_buf = cl.Buffer(self._ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=target_be)
        hit_buf = cl.Buffer(self._ctx, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=hit)
        self._scan(self._queue, (window,), None, hdr_buf, tgt_buf, np.uint32(window), hit_buf)
        cl.enqueue_copy(self._queue, hit, hit_buf)
        self._queue.finish()
        self.last_dispatch_backend = self.backend
        val = int(hit[0])
        if val < 0:
            return None
        digest = _sha256d(header76 + val.to_bytes(4, "little"))
        if _u256(digest) <= target:
            return val
        return self._cpu_scan(header76, target, window)

    def _cpu_scan(self, header76: bytes, target: int, window: int) -> Optional[int]:
        for nonce in range(window):
            if _u256(_sha256d(header76 + nonce.to_bytes(4, "little"))) <= target:
                return nonce
        return None

    def run_punch_batch(self, opcode: int, n: int = 1, in_float=None, in_ulong=None) -> dict:
        import numpy as np

        self.last_dispatch_backend = self.backend if self.use_opencl else "cpu"
        if in_float is not None:
            vec = np.array(in_float, dtype=np.float32).flatten()
            return {"float": np.array([float(np.dot(vec, vec)) if vec.size else 0.0], dtype=np.float32)}
        if in_ulong is not None:
            return {"ulong": np.array(in_ulong, dtype=np.uint64).flatten()}
        return {"float": np.zeros(1, dtype=np.float32), "ulong": np.zeros(1, dtype=np.uint64)}


def resolve_opencl_host() -> Optional[OpenClPunchHost]:
    host = OpenClPunchHost()
    return host if host.use_opencl else None
