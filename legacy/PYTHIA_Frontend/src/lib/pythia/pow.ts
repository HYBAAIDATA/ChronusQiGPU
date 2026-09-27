/** SHA-256d, compact target, 80-byte headers. Consensus path only. */

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
  0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
  0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
  0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
  0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
  0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
]);

const IV = new Uint32Array([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
  0x5be0cd19,
]);

function rotr(x: number, n: number) {
  return ((x >>> n) | (x << (32 - n))) >>> 0;
}

function compress(state: Uint32Array, block: Uint32Array, w: Uint32Array) {
  for (let i = 0; i < 16; i++) w[i] = block[i]!;
  for (let i = 16; i < 64; i++) {
    const x = w[i - 15]!;
    const y = w[i - 2]!;
    const s0 = rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3);
    const s1 = rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10);
    w[i] = (w[i - 16]! + s0 + w[i - 7]! + s1) >>> 0;
  }
  let a = state[0]!,
    b = state[1]!,
    c = state[2]!,
    d = state[3]!,
    e = state[4]!,
    f = state[5]!,
    g = state[6]!,
    h = state[7]!;
  for (let i = 0; i < 64; i++) {
    const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
    const ch = (e & f) ^ (~e & g);
    const temp1 = (h + S1 + ch + K[i]! + w[i]!) >>> 0;
    const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
    const maj = (a & b) ^ (a & c) ^ (b & c);
    const temp2 = (S0 + maj) >>> 0;
    h = g;
    g = f;
    f = e;
    e = (d + temp1) >>> 0;
    d = c;
    c = b;
    b = a;
    a = (temp1 + temp2) >>> 0;
  }
  state[0] = (state[0]! + a) >>> 0;
  state[1] = (state[1]! + b) >>> 0;
  state[2] = (state[2]! + c) >>> 0;
  state[3] = (state[3]! + d) >>> 0;
  state[4] = (state[4]! + e) >>> 0;
  state[5] = (state[5]! + f) >>> 0;
  state[6] = (state[6]! + g) >>> 0;
  state[7] = (state[7]! + h) >>> 0;
}

function writeBE(out: Uint32Array, bytes: Uint8Array, off: number) {
  for (let i = 0; i < 16; i++) {
    const j = off + i * 4;
    out[i] =
      ((bytes[j]! << 24) | (bytes[j + 1]! << 16) | (bytes[j + 2]! << 8) | bytes[j + 3]!) >>> 0;
  }
}

function storeHash(state: Uint32Array, out: Uint8Array) {
  for (let i = 0; i < 8; i++) {
    const v = state[i]!;
    const j = i * 4;
    out[j] = (v >>> 24) & 0xff;
    out[j + 1] = (v >>> 16) & 0xff;
    out[j + 2] = (v >>> 8) & 0xff;
    out[j + 3] = v & 0xff;
  }
}

const wScratch = new Uint32Array(64);
const blockScratch = new Uint32Array(16);
const stateScratch = new Uint32Array(8);
const pad80 = new Uint8Array(128);
const mid32 = new Uint8Array(32);

export function sha256(data: Uint8Array, out: Uint8Array = new Uint8Array(32)): Uint8Array {
  stateScratch.set(IV);
  const len = data.length;
  const bitLen = len * 8;
  let off = 0;
  while (off + 64 <= len) {
    writeBE(blockScratch, data, off);
    compress(stateScratch, blockScratch, wScratch);
    off += 64;
  }
  const rem = len - off;
  const pad = pad80;
  pad.fill(0);
  pad.set(data.subarray(off), 0);
  pad[rem] = 0x80;
  const padLen = rem + 1 <= 56 ? 64 : 128;
  const view = new DataView(pad.buffer, pad.byteOffset, padLen);
  view.setUint32(padLen - 4, bitLen, false);
  for (let i = 0; i < padLen; i += 64) {
    writeBE(blockScratch, pad, i);
    compress(stateScratch, blockScratch, wScratch);
  }
  storeHash(stateScratch, out);
  return out;
}

export function sha256d(data: Uint8Array, out: Uint8Array = new Uint8Array(32)): Uint8Array {
  sha256(data, mid32);
  return sha256(mid32, out);
}

export function digestToInt(digest: Uint8Array): bigint {
  let n = 0n;
  for (let i = 31; i >= 0; i--) n = (n << 8n) + BigInt(digest[i]!);
  return n;
}

export function digestToDisplayHex(digest: Uint8Array): string {
  let s = "";
  for (let i = 31; i >= 0; i--) s += digest[i]!.toString(16).padStart(2, "0");
  return s;
}

export function hexToBytes(hex: string): Uint8Array {
  const h = hex.replace(/^0x/i, "").replace(/\s/g, "");
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export function bytesToHex(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += bytes[i]!.toString(16).padStart(2, "0");
  return s;
}

export function compactToTarget(bits: number): bigint {
  const exp = bits >>> 24;
  const mant = bits & 0xffffff;
  if (exp <= 3) return BigInt(mant) >> BigInt(8 * (3 - exp));
  return BigInt(mant) << BigInt(8 * (exp - 3));
}

export function targetToCompact(target: bigint): number {
  if (target <= 0n) return 0;
  let hex = target.toString(16);
  if (hex.length & 1) hex = "0" + hex;
  let exp = hex.length / 2;
  let mantHex = hex.slice(0, 6);
  if (parseInt(mantHex.slice(0, 2), 16) & 0x80) {
    mantHex = "00" + mantHex.slice(0, 4);
    exp += 1;
  }
  return ((exp << 24) | parseInt(mantHex.padEnd(6, "0"), 16)) >>> 0;
}

export function writeUint32LE(buf: Uint8Array, offset: number, value: number) {
  buf[offset] = value & 0xff;
  buf[offset + 1] = (value >>> 8) & 0xff;
  buf[offset + 2] = (value >>> 16) & 0xff;
  buf[offset + 3] = (value >>> 24) & 0xff;
}

export function readUint32LE(buf: Uint8Array, offset: number): number {
  return (
    buf[offset]! |
    (buf[offset + 1]! << 8) |
    (buf[offset + 2]! << 16) |
    (buf[offset + 3]! << 24)
  ) >>> 0;
}

export const GENESIS_HEADER_HEX =
  "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c";

export const GENESIS_HASH_DISPLAY =
  "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f";

export const GENESIS_BITS = 0x1d00ffff;

/** Easy demo target: ~1/256 of hashes pass. Not Bitcoin network difficulty. */
export const DEMO_TARGET = 1n << 248n;

export function meetsTarget(digest: Uint8Array, target: bigint): boolean {
  return digestToInt(digest) <= target;
}

export function denseReward(digest: Uint8Array, target: bigint): number {
  const h = digestToInt(digest);
  if (h > target || target === 0n) return 0;
  return Number((target - h) * 10000n / target) / 10000;
}

export class HeaderHasher {
  readonly header = new Uint8Array(80);
  readonly digest = new Uint8Array(32);

  load(bytes: Uint8Array) {
    this.header.set(bytes.subarray(0, 80));
  }

  setNonce(nonce: number) {
    writeUint32LE(this.header, 76, nonce >>> 0);
  }

  hash(): Uint8Array {
    return sha256d(this.header, this.digest);
  }
}

export function verifyGenesis(): { ok: boolean; got: string } {
  const header = hexToBytes(GENESIS_HEADER_HEX);
  const got = digestToDisplayHex(sha256d(header));
  return { ok: got === GENESIS_HASH_DISPLAY, got };
}

export function sha256Hex(text: string): string {
  return bytesToHex(sha256(new TextEncoder().encode(text)));
}
