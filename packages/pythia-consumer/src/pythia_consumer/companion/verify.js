/* PYTHIA receipt verifier — JavaScript port of pythia_consumer/verify.py
 * (contract v2). Runs fully client-side: BigInt arithmetic plus a
 * self-contained SHA-256, so receipts verify on an iPhone over plain-LAN
 * http or after the page is saved — no Web Crypto, no server round-trip,
 * no trust in us required.
 *
 * Verification levels mirror the Python contract:
 *   structural          — required fields + invariants
 *   canonical_binding   — token re-derived from coordinate_masks+context_id
 *   provenance          — "unsupported" (no signature trust model exists)
 *
 * JSON caveat (honest): values above 2^53-1 must be emitted as decimal
 * strings by the producer — JSON.parse would silently round them. String
 * forms are accepted for canonical_int; a rounded Number fails the
 * canonical_derivation check rather than passing falsely.
 */
"use strict";

const PythiaVerify = (() => {

const _TOKEN_RE = /^ZECK-[0-9a-fA-F]{16}$/;
const _MASK64 = (1n << 64n) - 1n;
const _PRIME_BUCKETS = [
  2n, 3n, 5n, 7n, 11n, 13n, 17n, 19n, 23n, 29n, 31n, 37n, 41n,
  43n, 47n, 53n, 59n, 61n, 67n, 71n, 73n, 79n, 83n, 89n, 97n,
];
const _DIMS = 11;
const _MAX_INDEX = 100000;  // practical bound; recursion is O(log n)

/* ---------------- exact integer math (BigInt) ---------------- */

function fibonacci(n) {
  n = BigInt(n);
  if (n < 0n) throw new RangeError("fibonacci index must be non-negative");
  if (n > BigInt(_MAX_INDEX)) throw new RangeError("index beyond practical bound");
  const pair = (k) => {
    if (k === 0n) return [0n, 1n];
    const [a, b] = pair(k >> 1n);
    const c = a * (2n * b - a);
    const d = a * a + b * b;
    return (k & 1n) ? [d, c + d] : [c, d];
  };
  return pair(n)[0];
}

function lucas(n) {
  n = BigInt(n);
  if (n < 0n) throw new RangeError("lucas index must be non-negative");
  if (n === 0n) return 2n;
  return fibonacci(n - 1n) + fibonacci(n + 1n);
}

function cassini_holds(n) {
  n = BigInt(n);
  if (n < 0n) throw new RangeError("cassini index must be non-negative");
  const parity = (n % 2n === 0n) ? 1n : -1n;
  const L = lucas(n), F = fibonacci(n);
  return L * L - 5n * F * F === 4n * parity;
}

function zeckendorf(n) {
  n = BigInt(n);
  if (n <= 0n) throw new RangeError("zeckendorf requires a positive integer");
  const indices = [];
  let i = 2n;
  while (fibonacci(i + 1n) <= n) i += 1n;
  while (n) {
    while (fibonacci(i) > n) i -= 1n;
    indices.push(Number(i));
    n -= fibonacci(i);
    i -= 1n;
  }
  return indices;
}

function zeckendorf_legal(indices) {
  const s = [...indices].sort((a, b) => a - b);
  if (new Set(indices).size !== indices.length) return false;
  for (let k = 0; k + 1 < s.length; k++) if (s[k + 1] - s[k] < 2) return false;
  return true;
}

/* ---------------- SHA-256 (self-contained, sync) ---------------- */

const _K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);
const _rr = (x, n) => ((x >>> n) | (x << (32 - n))) >>> 0;

function sha256Bytes(data /* Uint8Array */) {
  const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                             0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const bitLenHi = Math.floor(data.length / 0x20000000);
  const bitLenLo = (data.length * 8) >>> 0;
  const padded = new Uint8Array(Math.ceil((data.length + 9) / 64) * 64);
  padded.set(data);
  padded[data.length] = 0x80;
  const dv = new DataView(padded.buffer);
  dv.setUint32(padded.length - 8, bitLenHi);
  dv.setUint32(padded.length - 4, bitLenLo);
  const w = new Uint32Array(64);
  for (let off = 0; off < padded.length; off += 64) {
    for (let t = 0; t < 16; t++) w[t] = dv.getUint32(off + t * 4);
    for (let t = 16; t < 64; t++) {
      const s0 = _rr(w[t - 15], 7) ^ _rr(w[t - 15], 18) ^ (w[t - 15] >>> 3);
      const s1 = _rr(w[t - 2], 17) ^ _rr(w[t - 2], 19) ^ (w[t - 2] >>> 10);
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let t = 0; t < 64; t++) {
      const S1 = _rr(e, 6) ^ _rr(e, 11) ^ _rr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (h + S1 + ch + _K[t] + w[t]) >>> 0;
      const S0 = _rr(a, 2) ^ _rr(a, 13) ^ _rr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0;
      d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0; H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
    H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0; H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
  }
  const out = new Uint8Array(32);
  const odv = new DataView(out.buffer);
  for (let i = 0; i < 8; i++) odv.setUint32(i * 4, H[i]);
  return out;
}

function utf8Bytes(s) {
  if (typeof TextEncoder !== "undefined") return new TextEncoder().encode(s);
  const out = [];
  for (let i = 0; i < s.length; i++) {
    let c = s.codePointAt(i);
    if (c > 0xFFFF) i++;
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xC0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xF0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return new Uint8Array(out);
}

/* ---------------- canonical fold ---------------- */

function _maskMaxK(mask) {  // mask: BigInt, highest set bit index
  return mask ? BigInt(mask.toString(2).length - 1) : 0n;
}

function _maskProducible(mask) {  // mask: BigInt
  return (mask >> 25n) === 0n && (mask & 0b11n) === 0n && (mask & (mask << 1n)) === 0n;
}

function canonical_accumulator(coordinate_masks, context_id) {
  let acc = 0n;
  for (const m0 of coordinate_masks) {
    const m = BigInt(m0);
    const mk = _maskMaxK(m);
    if (mk >= BigInt(_PRIME_BUCKETS.length)) {
      throw new RangeError(`coordinate mask ${m} exceeds the 25 prime buckets`);
    }
    acc = ((acc * 31n) + (m ^ _PRIME_BUCKETS[Number(mk)])) & _MASK64;
  }
  if (context_id) {
    const digest = sha256Bytes(utf8Bytes(context_id));
    let ctx = 0n;
    for (let i = 0; i < 8; i++) ctx = (ctx << 8n) | BigInt(digest[i]);
    acc = ((acc * 31n) + ctx) & _MASK64;
  }
  return acc;
}

/* ---------------- receipt contract ---------------- */

const _isInt = (v) => typeof v === "number" && Number.isInteger(v);

/* Exact-integer coercion: accepts safe-int Numbers and decimal strings.
 * Returns {ok, value:BigInt} — a rounded Number above 2^53 still yields a
 * value, but it will fail canonical_derivation honestly downstream. */
function _asBig(v) {
  if (_isInt(v)) return { ok: true, value: BigInt(v) };
  if (typeof v === "string" && /^(0|[1-9]\d*)$/.test(v)) return { ok: true, value: BigInt(v) };
  return { ok: false, value: 0n };
}

/* Receipt-aware JSON parse. JSON.parse rounds integer literals above
 * 2^53-1 — real canonical_int values are 64-bit and would silently lose
 * precision. Quoting every >=16-digit literal preserves it as a decimal
 * string for _asBig. Blast radius is honest: a crafted receipt can only
 * turn a false-pass into a parse error, never the reverse. */
function parse_receipt(text) {
  return JSON.parse(text.replace(/([:\[,]\s*)(-?\d{16,})(?=[\s,\]}])/g, '$1"$2"'));
}

const _check = (name, ok, detail = "") =>
  ({ check: name, result: ok ? "pass" : "fail", passed: !!ok, detail });
const _skipped = (name, detail) =>
  ({ check: name, result: "skipped", passed: false, detail });

function verify_receipt(receipt) {
  const checks = [];
  const verdict = { schema: "pythia.consumer.verdict/2", checks };
  if (receipt === null || typeof receipt !== "object" || Array.isArray(receipt)) {
    checks.push(_check("receipt_shape", false, "receipt must be a JSON object"));
    return _finish(verdict);
  }

  const token = receipt.token_hex;
  const mask = receipt.non_adjacent_mask;
  const coordMasks = receipt.coordinate_masks;
  const contextId = receipt.context_id;
  const canonical = _asBig(receipt.canonical_int);

  let reqOk = true;
  const ok = (cond, name, detail) => { checks.push(_check(name, cond, detail)); reqOk = reqOk && cond; };

  ok(typeof token === "string", "required:token_hex", "string required");
  ok(_isInt(mask) && mask >= 0 && mask <= 0x7FF, "required:non_adjacent_mask", "int in [0,2047] required");
  ok(canonical.ok && canonical.value >= 0n && canonical.value <= _MASK64,
     "required:canonical_int", "int (or decimal string) in [0,18446744073709551615] required");
  ok(Array.isArray(coordMasks) && coordMasks.length === _DIMS && coordMasks.every(_isInt),
     "required:coordinate_masks", `list of exactly ${_DIMS} ints required`);
  ok(typeof contextId === "string", "required:context_id", "string required");

  if (reqOk) {
    checks.push(_check("token_format", _TOKEN_RE.test(token), "expected 'ZECK-' + 16 hex chars"));
    checks.push(_check("non_adjacent_mask", (mask & (mask << 1)) === 0,
                       "mask & (mask << 1) == 0 required"));
    checks.push(_check("coordinate_masks_producible",
                       coordMasks.every((m) => _maskProducible(BigInt(m))),
                       "bits restricted to [2,24], non-adjacent, per coordinate"));
    checks.push(_check("token_canonical_binding",
                       token === `ZECK-${canonical.value.toString(16).toUpperCase().padStart(16, "0")}`,
                       "token must equal canonical_int as ZECK-%016X"));
    try {
      const derived = canonical_accumulator(coordMasks.map(BigInt), contextId);
      checks.push(_check("canonical_derivation", derived === canonical.value,
                         "coordinate_masks + context_id fold must equal canonical_int"));
    } catch (e) {
      checks.push(_check("canonical_derivation", false, String(e.message || e)));
    }
  } else {
    for (const name of ["token_format", "non_adjacent_mask", "coordinate_masks_producible",
                        "token_canonical_binding", "canonical_derivation"]) {
      checks.push(_skipped(name, "required-field prerequisite failed"));
    }
  }

  const alias = receipt.token;
  if (reqOk && alias !== undefined) {
    checks.push(_check("token_alias_consistent", alias === token,
                       "'token' must equal 'token_hex' when both present"));
  }

  const indices = receipt.zeckendorf_indices, value = receipt.zeckendorf_value;
  if (indices !== undefined) {
    const legal = Array.isArray(indices) && indices.every((i) => _isInt(i) && i >= 2) &&
                  zeckendorf_legal(indices);
    checks.push(_check("zeckendorf_indices", legal, "non-adjacent Fibonacci indices required"));
    if (legal && value !== undefined) {
      const sum = indices.reduce((s, i) => s + fibonacci(i), 0n);
      checks.push(_check("zeckendorf_value", _asBig(value).ok && sum === _asBig(value).value,
                         "indices must sum to the declared value"));
    }
  } else if (value !== undefined) {
    if (_asBig(value).ok && _asBig(value).value > 0n) {
      checks.push(_check("zeckendorf_value", true,
                         `decomposition ${zeckendorf(_asBig(value).value)} recomputed`));
    } else {
      checks.push(_check("zeckendorf_value", false, "positive integer required"));
    }
  }

  (receipt.cassini_ledger || []).forEach((row, idx) => {
    let okRow = false, detail = "";
    try {
      const [i0, fp0, fi0, fn0, parity0] = row;
      const i = BigInt(i0), fp = BigInt(fp0), fi = BigInt(fi0), fn = BigInt(fn0), parity = BigInt(parity0);
      okRow = fibonacci(i - 1n) === fp && fibonacci(i) === fi && fibonacci(i + 1n) === fn &&
              parity === ((i % 2n === 0n) ? 1n : -1n) && fp * fn - fi * fi === parity;
    } catch (e) {
      detail = `malformed row: ${e.message || e}`;
    }
    checks.push(_check(`cassini_ledger[${idx}]`, okRow,
                       detail || "F_{i-1}·F_{i+1} − F_i² == (-1)^i"));
  });

  const ladder = receipt.lucas_ladder;
  if (ladder !== undefined && ladder !== null && typeof ladder === "object") {
    for (const [k, v] of Object.entries(ladder)) {
      try {
        checks.push(_check(`lucas_ladder[${k}]`, lucas(BigInt(k)) === BigInt(v), ""));
      } catch (e) {
        checks.push(_check(`lucas_ladder[${k}]`, false, String(e.message || e)));
      }
    }
  }

  return _finish(verdict);
}

/* ---------------- receipt minting (parity with mint.py) ---------------- */

function data_coordinate_masks(data /* Uint8Array */) {
  const digest = sha256Bytes(data);
  let value = 0n;
  for (const b of digest) value = (value << 8n) | BigInt(b);
  const masks = [];
  for (let d = 0; d < _DIMS; d++) {
    const chunk = value & ((1n << 22n) - 1n);
    value >>= 22n;
    let m = 0n;
    for (let i = 0n; i < 11n; i++) m |= ((chunk >> i) & 1n) << (2n * i + 2n);
    masks.push(Number(m));
  }
  return masks;
}

function mint_receipt({ context_id = "", coordinate_masks = null, data = null, producer_version = "js" } = {}) {
  let derivation;
  if (coordinate_masks == null) {
    if (data != null) {
      coordinate_masks = data_coordinate_masks(data instanceof Uint8Array ? data : utf8Bytes(data));
      derivation = "sha256-data";
    } else {
      coordinate_masks = new Array(_DIMS).fill(0);
      derivation = "zero-masks";
    }
  } else {
    derivation = "explicit";
  }
  if (coordinate_masks.length !== _DIMS || !coordinate_masks.every((m) => _isInt(m) && m >= 0)) {
    throw new RangeError(`coordinate_masks must be ${_DIMS} non-negative ints`);
  }
  const canonical = canonical_accumulator(coordinate_masks.map(BigInt), context_id);
  let decoupling = 0;
  for (let i = 0n; i < 6n; i++) decoupling |= Number((canonical >> i) & 1n) << (2 * Number(i));
  return {
    token_hex: `ZECK-${canonical.toString(16).toUpperCase().padStart(16, "0")}`,
    non_adjacent_mask: decoupling,
    canonical_int: canonical.toString(10),  // string keeps 64-bit exactness
    coordinate_masks: [...coordinate_masks],
    context_id,
    producer: {
      distribution: "hyba-pythia-consumer",
      version: producer_version,
      derivation,
      provenance: "unsupported — minted receipts prove the fold, not origin",
    },
  };
}

/* Canonical wire form: canonical_int must be a bare integer literal — the
 * Python contract rejects a quoted string and naive JSON.parse rounds one
 * above 2^53. receipt_json() emits the string field unquoted so the text
 * verifies exactly under BOTH implementations. */
function receipt_json(receipt, space = 1) {
  return JSON.stringify(receipt, null, space)
    .replace(/"canonical_int": "(\d+)"/g, '"canonical_int": $1');
}

function _finish(verdict) {
  const checks = verdict.checks;
  const passedAll = checks.length > 0 && checks.every((c) => c.result === "pass");
  const binding = checks.some((c) => c.check === "canonical_derivation" && c.result === "pass");
  verdict.verdict = passedAll ? "pass" : "fail";
  verdict.levels = {
    structural: passedAll,
    canonical_binding: !!(binding && passedAll),
    provenance_authentication: "unsupported",
  };
  verdict.verification_level = (binding && passedAll) ? "canonical_binding" : "structural";
  verdict.custody_proof = false;
  return verdict;
}

return {
  fibonacci, lucas, cassini_holds, zeckendorf, zeckendorf_legal,
  canonical_accumulator, verify_receipt, parse_receipt, sha256Bytes, utf8Bytes,
  data_coordinate_masks, mint_receipt, receipt_json,
};
})();

if (typeof window !== "undefined") window.PythiaVerify = PythiaVerify;
if (typeof module !== "undefined" && module.exports) module.exports = PythiaVerify;
