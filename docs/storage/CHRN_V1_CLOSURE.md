# CHRN v1 closure — proposed framing profile, discovery contract HOLD

Source: owner draft 1.0.0 and storage/capacity work order supplied 2026-11-19.
Baseline: 93d6068f2c668f3f1106a9e6df204f37033fc163. Read mandatory AGENTS.md.
Work-order attachment SHA-256: a14deab10a721e87de4354d75bd93be5b39d6bf562fe33c67412113b3dd88d1f.

## Implemented work

- New src/chronus/storage/chrn_frame.py: the 60-byte CHRN header, explicit block parameter injection, CRC-32C, original SHA-256, exact original length, and typed rejection without partial return. Existing CPRM public API and historical artifacts remain unchanged.
- Proposed framing conventions: big-endian, fixed encoded width as an exact function of block input length, no padding, flags zero. Flag 1 is explicitly refused pending a specified recovery profile; reserved flags fail. Final block length derives from orig_len modulo block_size, including zero remainder for exact multiples.
- The caller must supply a trusted parameter implementation; no production parameter is registered and no legacy fallback exists. The test-only reference prime-symbol parameter uses ID 0xfffffffe and B=256, deliberately distinct from canonical ID 1. Its vectors test framing, not the discovery.
- Existing prime codec maps octets to successive primes as 16-bit words; prime_product supports unordered label sets, not byte streams; ring_codec uses separate cyclotomic coefficients. Neither is authority for the missing discovery transform. Existing erasure/self-healing are separate THESEUS custody mechanisms, not CHRN parity.
- Hash and CRC check accidental corruption, not authentication: a party able to replace the header and digest can forge a self-consistent frame.

## Decisions not authorised by the draft

Actual prime basis, E/D, parameter 1, B, canonical serialization and recovery mode remain unspecified. The proposed framing conventions must be accepted or revised before product interoperability. Do not manufacture canonical vectors or mark A1 complete. A variable-length transform would also require an explicit body delimiting specification. Owner must supply or identify the authoritative discovery document and golden vectors; OVID owns the transformation contract, Chronus executes and THESEUS retains evidence.

## Acceptance

Existing main CI collects tests/test_chrn_frame.py. Provisional known-answer vectors are deliberately NOT the required tests/vectors/encoding_v1.json. Customer capacity, successful recovery and hardware measurements remain unavailable for CHRN. No old measurements are relabelled. No release claims changed.

Phase A precedes B–G under the work order. Independent review, current CI results, artifact signing and all deployment qualification remain pending.
