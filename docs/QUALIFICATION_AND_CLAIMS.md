# Chronus V2 — Qualification and Claims Register

**Revision:** 15 November 2026. Implementation status and independent verification are distinct. Repository source and tests alone do not award a PASS.

| Claim | Implemented source | Verified CI artifact | Status |
| --- | --- | --- | --- |
| CO-001 Ed25519 signatures | `chronus.crypto.signers` | Unavailable | HELD |
| CO-002 Dual Ed25519 + ML-DSA-65 | Provider and verifier committed | Unavailable | HELD |
| RS-001 Signed receipt chain | `chronus.security.receipts` | Unavailable | HELD |
| RS-002 Deterministic durable replay | Not integrated with THESEUS | Unavailable | HELD |
| FN-001 Azure Managed HSM custody | Not integrated | Unavailable | HELD |
| FIPS 204 on every AL HARAS decision | Not integrated at call sites | Unavailable | HELD |
| TLS/mTLS, ML-KEM, FRI | No runtime evidence | Unavailable | HELD |
| NCSC/NIST/ISO accreditation | No accredited assessment | Unavailable | HELD |
| Measured FinOps savings | No measured baseline | Unavailable | HELD |

## Gate binding

The executable mapping in `chronus.core.claims.CLAIM_GATES` binds CO-001 to CO-SIGN; CO-002 to CO-SIGN and RS-RECEIPT; RS-001 to RS-RECEIPT and RS-REPLAY; RS-002 to RS-REPLAY and FN-CUSTODY; FN-001 to FN-CLAIMS and FN-CUSTODY. Any non-PASS gate or absent verified attestation makes the claim **held**.

## Evidence ownership

Actions runs tests and generates `test-evidence.json`, with test counts, Python version, cryptography version, OpenSSL version, SHA and run ID. Actions attests the file using GitHub provenance; the downstream evaluator must independently verify that attestation before consuming it. The CI evaluator currently **holds all product gates** until gate-specific attestations are implemented. A green pytest result alone never qualifies the product.

## External claims

Exhibit 11's FIPS 204 statement must use the correction in [EXHIBIT_11_CORRECTION.md](EXHIBIT_11_CORRECTION.md). No regulatory, deployment, hardware or commercial impact claim is verified by this repository baseline.
