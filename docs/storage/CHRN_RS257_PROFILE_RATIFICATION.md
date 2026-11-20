# CHRN RS(48,32) over GF(257) — Wire Profile Ratification

Profile ID: 0x00000002; profile version 1.1; CHRN header version 0x0100.
Status: FROZEN_FOR_RATIFICATION; formal owner signature and non-author QC pending.
PR: #201. First profile, no predecessor.
Owner-supplied closeout order: SHA-256 f7f9f5885b022791c7fdd9d3bac2d55d3f2b44a990347760f9cb588f8bd7f1b3 (19 November 2026).
Baseline: 93d6068f2c668f3f1106a9e6df204f37033fc163.
Previous evidence revision: e32b5c8f16ceb7be36895cca48765382cf1a0fb2.
The normative wire contract is Section 1, frozen for review; any subsequent incompatible amendment requires a new profile ID. The commit containing this record identifies the proposed frozen text. Do not substitute the implementation for this specification.

## 1. Frozen wire specification

All header integer fields are unsigned big endian. The 60-byte header is:
- offsets 0..3: literal ASCII CHRN;
- 4..5: version 0x0100; 6..7: flags 0x0001 (bit 0 set, all others zero);
- 8..15: original byte length N (uint64); 16..19: block size 256 (uint32);
- 20..23: parameter 2 (uint32); 24..55: SHA-256 of the complete original bytes;
- 56..59: CRC-32C of bytes 0..55, reflected polynomial 0x82F63B78, initial register and final XOR 0xffffffff, each octet processed least-significant bit first. CRC result serialized big endian.

Partition original bytes consecutively into blocks of length L=min(256,remaining). Empty input has no blocks. For each nonempty block, for lane a=0..7 and data symbol j=0..31, d[a,j]=source[8*j+a] if 8*j+a<L, otherwise 0 (virtual shortening; NEVER persist these zero bytes). RS code is systematic over GF(257): the unique polynomial P_a of degree at most 31 satisfying P_a(j+1)=d[a,j] for j=0..31. Parity row r=0..15 is P_a(33+r) reduced to its canonical integer 0..256. Arithmetic is exact modulo 257.

Serialize the L original systematic bytes in unchanged source order. Append 16 rows of nine bytes each. For row r, slot i=0..7 holds parity of lane (i+L) mod 8. Each slot is exactly nine bits, most significant bit first, concatenated with no separators or padding. The 72-bit row is serialized most significant octet first. The value 256 is 100000000 in binary; values 257..511 are invalid received labels, never valid encodings. Append blocks in source order. Body length is N+144*ceil(N/256); full frame length adds 60. No trailing bytes.

Recovery: with intact header and exact body length, correct at most eight differing symbols per lane using the existing AL HARAS Berlekamp–Welch decoder. Count invalid received parity labels against that same radius, substituting zero for decoding and comparing original raw labels to the regenerated canonical codeword. Data symbols must reconstruct to 0..255 and virtual shortened symbols to zero. Recompute parity and reject any lane exceeding radius. Reconstruct all blocks and verify original SHA-256 before releasing any bytes or recovery positions. Absolute corrected physical byte offsets are differences from the canonical regenerated wire body; symbol positions are (zero-based block, lane, codeword index). Clean iff no altered body bytes; otherwise corrected. The header is not recoverable: reject unsupported version/magic/flag/parameter/block size, CRC mismatch, truncation, wrong exact length, or digest mismatch with a CorruptFrameError subclass; no payload on rejection. Rejection-only profiles and legacy decoders remain distinct and fail on recovery flag 1.

Guaranteed fault class: at most eight changed RS symbols per lane; a contiguous burst of up to 64 body bytes is within that bound even at a shortened-block or data/parity boundary. A 65-byte burst entirely in systematic data with every byte changed is outside radius and rejected, subject to the intact digest. Longer mixed, parity-only or cross-block bursts may be within radius and must not be categorically rejected. No authentication, entire-shard recovery or physical-media guarantee. THESEUS custody and XOR shard recovery remain separate.

## 2. Capacity reconciliation

For N>0 exact frame bytes W(N)=60+N+144*ceil(N/256).
Full-block body: 144/256=9/16=56.25% redundancy, 400/256=25/16=1.5625 encoded/source ratio. Payload/encoded body=16/25=64%; equivalently 36% of full-block encoded body is parity. A single full block with header is 460 bytes, source/wire=64/115; expansion=204/256=79.6875%. Short tails may have larger overhead (one byte source yields 205 total bytes). Empty frame is 60 bytes; ratio undefined.
For a hypothetical pre-ECC fixed-width payload reduction factor R (not established by this profile), a comparable full-block body factor after parity is (16/25)*R, before framing/metadata. If R=11.5, the arithmetic is 184/25=7.36, NOT a measured capacity result.
Canonical register claims/register.json RS-WORK says "11.5x verified work", state held; gate bench.verified_work. The storage research closeout dated 2026-11-16 explicitly forbids construing it as retained or physical compression. Verdict RE-SCOPED: profile 2 makes no capacity gain claim and cannot promote RS-WORK or discovery parameter 1. The held work claim remains unchanged, requiring a separate equal-correctness workload benchmark including all overhead. No inference of physical allocated bytes or physical latency.

## 3. Independent QC

Required: a non-author reviewer receives Section 1 and only source input hex, independently derives the entire frame (including CRC and parity) before seeing expected output, then compares byte-for-byte with tests/vectors/chrn_rs257_v11.json. Record identity, method, exact reviewed commit, generated frame digest, mismatch count, evidence and PASS/FAIL. Re-run the software drill against the reviewed profile. The separate stdlib-only author-created reconstruction gate is reproducible technical evidence, NOT a substitute for this reviewer. Do not count a code-quality bot comment or author-run tests as approval.

## 4. Gates

| Gate | Status |
|---|---|
| Prior-head CI | PASS, e32b5c8f16ceb7be36895cca48765382cf1a0fb2: all seven triggered workflows green; conditional SLSA attestation skipped |
| Exact wire text | Frozen for ratification in this record |
| Formal owner ratification | PENDING; no signature manufactured |
| Capacity reconciliation | PASS, re-scoped; RS-WORK held |
| Independent non-author reconstruction | PENDING |
| Final-head CI and drill | Re-run required on this record's revision |
| CHRN-RECOVERY | OPEN until all applicable gates pass |
| Production qualification | HOLD |
| Discovery parameter 1 | OPEN |

## 5. Signatures and evidence

Ratifier: PENDING owner attestation to Section 1 and Section 2. QC: PENDING named non-author attestation.
Historical measured run at a83f5f0b892e1bac9e818bcc4b525b12f502d113: 49/49 focused tests, 131/131 trials, 67 verified/64 expected rejection. p50 39.135 ms, p95 43.056 ms, p99 44.250 ms: **software fault injection, GitHub-hosted Linux x86-64, Python 3.13.18, not physical media**. Raw JSON in evidence/capacity/chrn_recovery_e00b29a57362e6a5812f11e9b1462808cb38e7c3eddb4e3ef2e3bd66b2c9a120.json. Subsequent results must be retained separately.

## 6. Closure statement

CHRN-RECOVERY is implemented and measured but remains OPEN pending the gates in Section 4. Upon their PASS, it closes as an engineering blocker: AL HARAS supplies correction, Chronus executes the protected representation, OVID governs the transformation contract, THESEUS provides durable custody. Recovery no longer blocks only after that recorded acceptance.

Excluded: physical-media latency, discovery parameter 1, canonical capacity promotion and broader storage qualification. Production remains HOLD.
Failure path: if any required gate fails or lacks evidence, CHRN-RECOVERY remains OPEN; name the unmet gate, never claim partial closure.
