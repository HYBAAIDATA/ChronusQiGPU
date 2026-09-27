// Bitcoin SHA-256d of exactly 80 bytes. One nonce/header per work-item.
// Integer-only OpenCL: no floating-point or geometric accept predicate.
//
// Two entry points:
//   bitcoin_sha256d          reference — recompresses the constant first
//                            block in every work-item (parity checks).
//   bitcoin_sha256d_midstate optimized — the host precomputes the first-block
//                            midstate once per header, so each work-item
//                            compresses only the nonce block and the final
//                            256-bit hash, then evaluates the consensus
//                            predicate (reversed digest < big-endian target)
//                            on-device. Per-item hit flags let the host pick
//                            the first winner in probe order without a
//                            Python digest scan. The host re-verifies any
//                            winner with hashlib before submission —
//                            double-SHA256 remains the sole accept authority.
__constant uint SHA_K[64] = {
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
inline uint rr(uint x, uint n) { return (x >> n) | (x << (32u-n)); }
inline void sha_init(uint *s) {
  s[0]=0x6a09e667; s[1]=0xbb67ae85; s[2]=0x3c6ef372; s[3]=0xa54ff53a;
  s[4]=0x510e527f; s[5]=0x9b05688c; s[6]=0x1f83d9ab; s[7]=0x5be0cd19;
}
inline void sha_block(uint *s, uint *w) {
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
inline uint load_be(__global const uchar *p) {
  return ((uint)p[0]<<24)|((uint)p[1]<<16)|((uint)p[2]<<8)|(uint)p[3];
}
__kernel void bitcoin_sha256d(__global const uchar *header,
                             __global const uint *nonces,
                             __global uchar *digests, uint count) {
  uint gid=get_global_id(0);
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

// Accept predicate: reversed digest (big-endian words) <= target (Bitcoin
// consensus is inclusive). Reversing the 32 digest bytes is a byteswap per
// state word, in reverse word order.
inline uint accept_less(uint *s, __global const uchar *target) {
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

__kernel void bitcoin_sha256d_midstate(__global const uchar *midstate,
                                       __global const uchar *header,
                                       __global const uchar *target,
                                       __global const uint *nonces,
                                       __global uchar *hits,
                                       uint count) {
  uint gid=get_global_id(0);
  if (gid>=count) return;
  uint s[8], w[64];
  for (int i=0;i<8;i++) s[i]=load_be(midstate+4*i);
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
  hits[gid]=accept_less(s,target);
}

// Contiguous-window grind: the device derives nonce = base_nonce + gid, so
// no nonce buffer is uploaded, and the first winning index is reduced
// on-device with atomic_min — the host reads back one uint instead of one
// flag per item. Scratch[0] must hold NO_HIT before launch (host writes it,
// 4 bytes). Winner selection is identical to the serial scan: smallest gid.
__kernel void bitcoin_sha256d_range(__global const uchar *midstate,
                                    __global const uchar *header,
                                    __global const uchar *target,
                                    uint base_nonce,
                                    __global uint *scratch,
                                    uint count) {
  uint gid=get_global_id(0);
  if (gid>=count) return;
  uint s[8], w[64];
  for (int i=0;i<8;i++) s[i]=load_be(midstate+4*i);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  uint n=base_nonce+gid;
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
  if (accept_less(s,target)) atomic_min(scratch, gid);
}

// Golden-stride traversal: nonce = (seed + gid * GOLDEN_STRIDE) mod 2^32,
// where GOLDEN_STRIDE = floor(phi^-1 * 2^32) = 0x9E3779B9 is odd, so the
// walk is a bijection over the whole nonce domain — the launch probes a
// phi-ordered slice of the space, every nonce exactly once across a full
// cycle, zero nonce upload. ASIC-style semantics: the device derives the
// sequence in-register, reduces the first winning probe index on-device
// (atomic_min), and pushes hit probe-indices into a GOLD_FIFO_DEPTH-deep
// FIFO (scratch[1] is the write counter — host reads scratch + fifo).
// GOLD_FIFO_DEPTH = fib(6) = 8 — a Lucas-pool constant, not a magic number.
// The host re-verifies every winner with hashlib before submission;
// double-SHA256 remains the sole accept authority.
#define GOLDEN_STRIDE 0x9E3779B9u
#define GOLD_FIFO_DEPTH 8u
__kernel void bitcoin_sha256d_gold(__global const uchar *midstate,
                                   __global const uchar *header,
                                   __global const uchar *target,
                                   uint seed,
                                   __global uint *scratch,
                                   __global uint *hit_fifo,
                                   uint count) {
  uint gid=get_global_id(0);
  if (gid>=count) return;
  uint s[8], w[64];
  for (int i=0;i<8;i++) s[i]=load_be(midstate+4*i);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  uint n=seed+gid*GOLDEN_STRIDE;
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
  if (accept_less(s,target)) {
    atomic_min(scratch, gid);
    uint slot=atomic_inc(&scratch[1]);
    if (slot<GOLD_FIFO_DEPTH) hit_fifo[slot]=gid;
  }
}

//   bitcoin_sha256d_m32      M32/Turing lane-order variant — the canonical
// solver walks nonce = base + order[step % 32] + 32*(step / 32): every
// 32-step epoch is a permuted contiguous block driven by a fixed 32-entry
// lane permutation (the Turing lane_order). This kernel reproduces that
// exact traversal on-device from a 32-byte lane LUT — zero nonce upload,
// one 4-byte readback, identical winner selection semantics to the serial
// scan (smallest step index wins via atomic_min on gid). Covering set is
// unchanged: every epoch still covers all 32 residues exactly once.
__kernel void bitcoin_sha256d_m32(__global const uchar *midstate,
                                  __global const uchar *header,
                                  __global const uchar *target,
                                  uint base_nonce,
                                  __global const uchar *lane_order,
                                  __global uint *scratch,
                                  uint count) {
  uint gid=get_global_id(0);
  if (gid>=count) return;
  uint s[8], w[64];
  for (int i=0;i<8;i++) s[i]=load_be(midstate+4*i);
  for (int i=0;i<16;i++) w[i]=0;
  for (int i=0;i<3;i++) w[i]=load_be(header+64+4*i);
  uint epoch=gid>>5;
  uint n=base_nonce+(uint)lane_order[gid&31u]+32u*epoch;
  w[3]=((n&255u)<<24)|((n&0xff00u)<<8)|((n>>8)&0xff00u)|(n>>24);
  w[4]=0x80000000u; w[15]=640u;
  sha_block(s,w);
  for (int i=0;i<8;i++) w[i]=s[i];
  for (int i=8;i<16;i++) w[i]=0;
  w[8]=0x80000000u; w[15]=256u;
  sha_init(s); sha_block(s,w);
  if (accept_less(s,target)) atomic_min(scratch, gid);
}
