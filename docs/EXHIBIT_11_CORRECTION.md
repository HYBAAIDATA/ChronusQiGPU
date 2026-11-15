# Exhibit 11 — correction required before external use

Original assertion: **"FIPS 204 ML-DSA signature on every AL HARAS decision — Implemented — Independent test at T2."**

**Current evidence-scoped replacement:**

"Chronus V2 has an implemented Ed25519 signature and receipt-validation foundation. An ML-DSA-65 provider and dual-signature verification interface have been committed; ML-DSA execution depends on a compatible OpenSSL/cryptography stack. The system is not FIPS 204-qualified, Azure Managed HSM custody is not verified, and an independent T2 evaluation has not been completed. This claim is HELD pending verified Actions evidence, dual-signature interoperability, HSM integration and independent evaluator acceptance."

The code is not evidence that every AL HARAS decision is signed. AL HARAS call-site integration must be demonstrated independently. **Do not use the original Exhibit 11 statement in a deck or website.**

## Qualification requirements

- Both Ed25519 and ML-DSA-65 signatures validate over the same bound receipt.
- The ML-DSA-65 signature binds the Ed25519 signature through a domain-separated envelope.
- Public-key-only evaluator independently verifies a supplied receipt bundle.
- GitHub Actions signs/attests test evidence and verifier checks the attestation identity.
- Skipped/failed/unavailable tests and unverified CI evidence are UNQUALIFIED.
- Azure Managed HSM provider and policy authorization are demonstrated.
- AL HARAS decision signing is traced end-to-end with durable THESEUS custody.

No website, DNS, hosting or indexing changes have been made.
