# AL HARAS (HYBA Security): brief for security leaders

**Status:** current summary. The detailed brief is [docs/security/SECURITY_AND_COMPLIANCE_BRIEF.md](security/SECURITY_AND_COMPLIANCE_BRIEF.md). The claim-by-claim record is [docs/security/AL_HARAS_NOTES_RECONCILIATION.md](security/AL_HARAS_NOTES_RECONCILIATION.md). An earlier version of this page claimed NCSC “COMPLIANT/EXCEEDS” ratings, FedRAMP and IL6 readiness, ML-DSA-65 signing, PKCS#11 HSM custody, 38-nanosecond isolation and one-clock-cycle repair. The code and assessments supported none of them, so they were withdrawn. Post-quantum signing has since been implemented and tested: every receipt now also carries an ML-DSA-87 (FIPS 204) signature (item 3 below).

## Decision this page supports

Should AL HARAS be evaluated further, and on what evidence? Recommendation: evaluate it as a **pre-release security library**, not as an accredited product. Every result it returns can be reproduced from the tests named below.

## What you get today

1. **A consistency gate for multi-node or multi-agent state.** Supplied states are checked for exact agreement on a graph. This is the coboundary of a cellular sheaf. The disagreeing edge and the node responsible are named, and the nearest consistent state is computed.
2. **In-place trace repair.** Reed–Solomon coding over GF(257) corrects up to 8 corrupted bytes in every 32-byte block. The repair is confirmed by SHA-256, and overload is reported as uncorrectable.
3. **Signed decisions, classical and post-quantum.** Every admission decision carries two signatures over canonical JSON: Ed25519 and ML-DSA-87 (FIPS 204, category 5), both from pyca/cryptography. A receipt verifies only if both signatures do.
4. **Authenticated API.** AL HARAS `POST` endpoints require a tenant token.

## What you do not get today

- No certification, accreditation or authorisation of any kind, and no independent security assessment.
- No HSM or cloud-KMS custody. Signing keys live in process memory or come from environment-supplied seeds.
- No FIPS 140-3 validated module and no NIST ACVP vectors in CI yet; no zero-knowledge proofs; no hardware or TEMPEST protection.
- No content-based detection of prompt injection or malware.

## Evidence

```bash
python -m pytest -q tests/test_al_haras_core_exact.py tests/test_al_haras_receipts_post_quantum.py tests/test_al_haras.py
python benchmarks/benchmark_al_haras_security.py --json al-haras-measurements.json
```

Next step for an evaluator: run the commands above on the exact commit under review. Then compare the governance register at `GET /v1/al-haras/status` with your own control framework.
