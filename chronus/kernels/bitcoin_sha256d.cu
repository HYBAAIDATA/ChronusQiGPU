// Chronus-owned CUDA SHA-256d (80-byte Bitcoin header).
// Integer-only. One nonce per thread. Host re-verifies with hashlib.
// opencl_required = false — this path does not depend on OpenCL.

#include <stdint.h>

__device__ __constant__ uint32_t SHA_K[64] = {
  0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
  0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
  0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
  0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
  0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
  0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
  0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
  0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};

__device__ __forceinline__ uint32_t rr(uint32_t x, uint32_t n) {
  return (x >> n) | (x << (32u - n));
}

__device__ __forceinline__ void sha_init(uint32_t *s) {
  s[0]=0x6a09e667u; s[1]=0xbb67ae85u; s[2]=0x3c6ef372u; s[3]=0xa54ff53au;
  s[4]=0x510e527fu; s[5]=0x9b05688cu; s[6]=0x1f83d9abu; s[7]=0x5be0cd19u;
}

__device__ __forceinline__ void sha_block(uint32_t *s, uint32_t *w) {
  for (int i = 16; i < 64; ++i) {
    uint32_t x = w[i - 15], y = w[i - 2];
    w[i] = w[i - 16] + (rr(x, 7) ^ rr(x, 18) ^ (x >> 3))
         + w[i - 7] + (rr(y, 17) ^ rr(y, 19) ^ (y >> 10));
  }
  uint32_t a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
  for (int i = 0; i < 64; ++i) {
    uint32_t t1 = h + (rr(e,6)^rr(e,11)^rr(e,25)) + ((e&f)^((~e)&g)) + SHA_K[i] + w[i];
    uint32_t t2 = (rr(a,2)^rr(a,13)^rr(a,22)) + ((a&b)^(a&c)^(b&c));
    h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
  }
  s[0]+=a; s[1]+=b; s[2]+=c; s[3]+=d; s[4]+=e; s[5]+=f; s[6]+=g; s[7]+=h;
}

__device__ __forceinline__ uint32_t load_be(const unsigned char *p) {
  return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
       | ((uint32_t)p[2] << 8)  | (uint32_t)p[3];
}

// header: 80 bytes (shared). nonces: count uint32 LE. digests: count*32 bytes.
extern "C" __global__ void bitcoin_sha256d(
    const unsigned char* header,
    const unsigned int* nonces,
    unsigned char* digests,
    unsigned int count
) {
  unsigned int gid = blockIdx.x * blockDim.x + threadIdx.x;
  if (gid >= count) return;

  uint32_t s[8], w[64];
  sha_init(s);
  for (int i = 0; i < 16; ++i) w[i] = load_be(header + 4 * i);
  sha_block(s, w);

  for (int i = 0; i < 16; ++i) w[i] = 0;
  for (int i = 0; i < 3; ++i) w[i] = load_be(header + 64 + 4 * i);
  unsigned int n = nonces[gid];
  // Bitcoin header nonce is little-endian in bytes 76..79; SHA-256 words are BE.
  w[3] = ((n & 255u) << 24) | ((n & 0xff00u) << 8) | ((n >> 8) & 0xff00u) | (n >> 24);
  w[4] = 0x80000000u;
  w[15] = 640u;  // 80 bytes * 8 bits
  sha_block(s, w);

  // Second SHA-256 over the 32-byte mid digest
  uint32_t s2[8], w2[64];
  sha_init(s2);
  for (int i = 0; i < 16; ++i) w2[i] = 0;
  for (int i = 0; i < 8; ++i) w2[i] = s[i];
  w2[8] = 0x80000000u;
  w2[15] = 256u;
  sha_block(s2, w2);

  unsigned char* out = digests + gid * 32;
  for (int i = 0; i < 8; ++i) {
    uint32_t v = s2[i];
    out[4 * i + 0] = (unsigned char)((v >> 24) & 255u);
    out[4 * i + 1] = (unsigned char)((v >> 16) & 255u);
    out[4 * i + 2] = (unsigned char)((v >> 8) & 255u);
    out[4 * i + 3] = (unsigned char)(v & 255u);
  }
}
