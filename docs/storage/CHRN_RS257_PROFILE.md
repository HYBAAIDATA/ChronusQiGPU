# CHRN-RS257-INTERLEAVE — proposed profile 1.1 (CHRN-ECC-V11)

Owner-supplied review 2026-11-19; base CHRN v1.0 header unchanged (0x0100).
Parameter ID 0x00000002, flag bit 0 set, B=256. Explicit opt-in. This
standalone systematic wire recovery profile does not define discovery ID 1.
Old decoders reject flag 1. No keys, signature or authentication added.

## Geometry and canonical wire

AL HARAS owns the existing GF(257) systematic RS(48,32) encoder and
Berlekamp–Welch decoder. Each nonempty block of L=1..256 input bytes uses
eight lanes: byte i has lane i mod 8, symbol floor(i/8). Missing source
symbols in the final shortened block are virtual zeros (not stored and
required to remain zero after decoding). Each lane carries 16 parity symbols.
The original L bytes appear first. For each parity row j=0..15, serialize
eight nine-bit coefficients MSB first, lane (i+L) mod 8 for slot i=0..7,
as a nine-byte big-endian word. Coefficient 256 is representable. Width is
L+144; empty input has no body. A 256-byte block is 400 bytes (+56.25%),
or 460 bytes including the single frame header. The proposed 384-byte
body cannot represent GF(257) parity as arbitrary octets; the 9-bit format
is an explicit correction to the draft. No persisted padding. Tail
rotation preserves burst coverage at the systematic/parity boundary.
Physical media write amplification is not measured by serialization.

## Fault contract

With an intact header and exact framing length, at most eight changed
GF symbols per lane are correctable; every contiguous burst of up to 64
body bytes affects at most eight symbols in each lane, including
parity and partial-block boundaries. The geometry test enumerates every
tail length and byte start; the actual fault tests run against encoded
wire bytes. Invalid 9-bit coefficients >256 count as damaged symbols,
are substituted with a fixed field value for decoding, and are verified
against the regenerated canonical codeword. No modulo coercion of invalid
wire labels is accepted. Verify per-lane radius, virtual zero padding and
original SHA-256; failure returns no payload. Report absolute altered byte
offsets and (block,lane,symbol) positions only after whole-payload verification.

A 65-byte *systematic data* burst forces nine changed symbols into one
lane and is rejected (assuming every byte changes and intact digest).
Longer bursts are not categorically uncorrectable: parity packing and
cross-block distribution can leave every lane within radius. Outside
the guaranteed class no successful recovery is promised; the accepted
candidate must still meet the radius and digest checks. A SHA digest and
CRC do not authenticate against an actor who can rewrite the header.
Header corruption, lost bytes, entire shard loss or physical sector faults
are not covered by this intra-body damage profile. Existing XOR recovery
remains a separate custody layer.

## Evidence

Replay `python scripts/benchmarks/chrn_recovery_drill.py --output-dir /tmp/chrn-recovery`.
It corrupts the encoded wire directly: SHA-derived contiguous starts for
1..128 systematic bytes and three 64-byte mixed/parity cases; records actual
status, recovered positions, integrity, perf_counter_ns elapsed, input/output
hash, source SHA and environment. Golden vectors v5/v6 in
tests/vectors/chrn_rs257_v11.json preserve a separately derived full frame.
The drill is a software fault-injection measurement, not customer capacity
or deployed recovery. Commit the exact measured JSON under evidence/capacity
with its byte SHA-256 after observing the run; independent QC and owner
ratification of the corrected wire contract remain separate.

## Executed software recovery evidence

Exact source commit `a83f5f0b892e1bac9e818bcc4b525b12f502d113`, [recovery job](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/44594052261/job/135807458725): 49 focused tests passed, 67 verified recoveries (64 systematic, one mixed, two parity), 64 expected systematic rejections; all 131 trial outcomes matched. The measured JSON is committed at [e00b29a57362e6a5812f11e9b1462808cb38e7c3eddb4e3ef2e3bd66b2c9a120](../../evidence/capacity/chrn_recovery_e00b29a57362e6a5812f11e9b1462808cb38e7c3eddb4e3ef2e3bd66b2c9a120.json) and independently byte-hashed from the raw runner log before commit. It records timing and failure positions; physical sector recovery and customer capacity are not measured. Corrected profile ratification and independent QC remain open.
