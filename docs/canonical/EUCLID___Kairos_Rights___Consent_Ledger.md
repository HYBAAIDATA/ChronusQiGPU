# EUCLID — Kairos Rights & Consent Ledger

**HYBA | EUCLID**

<aside>

**Status: implemented and internally verified.** The Kairos runtime now contains a fail-closed in-process rights and consent ledger for creator-scoped, hashed assets and explicitly authorised operations.

</aside>

## Implemented controls

- Creator-scoped grants bound to SHA-256 asset identifiers.
- Declared operation scopes and fail-closed authorization checks.
- Revocable grants with explicit post-revocation rejection.
- Audit export covering grant, authorisation, and revocation events.
- Rejection of undeclared operations and non-revocable grant changes.

## Verification

- **43/43** focused core, closure, CNS, interactive, Kairos world, runtime, transport, recovery, provider, and rights-ledger tests passed.
- **17/17** production-harness checks passed.
- Compilation passed.

## Boundary

This is an in-process technical rights ledger. It is not legal advice, identity verification, consent UX, a rights-management service, regulatory compliance certification, or external audit assurance.

## Custody

- **Baseline snapshot:** `EUCLID_SHARED_REPOSITORY_SNAPSHOT_20260718_2158.zip`
- **Baseline commit:** `a81fcfb755fbe2ddba014258d24b2f864a523d72`
- **Rights-ledger bundle SHA-256:** `3249aa7e43074ff21cb45523a830bbfb491f957442e6d7045613e2e3c6616f60`

[Kairos Rights and Consent Ledger evidence bundle](KAIROS_RIGHTS_LEDGER.zip)

Kairos Rights and Consent Ledger evidence bundle