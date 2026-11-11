# AL HARAS (HYBA Security): security and compliance brief

**Status:** current. Replaces the earlier brief of the same name, whose accreditation, certification and latency claims were not supported by the code (see [the reconciliation record](AL_HARAS_NOTES_RECONCILIATION.md)). AL HARAS is **not release-qualified** ([release decision](../../RELEASE_DECISION_MCKINSEY_TECH.md)).

## The question this brief answers

What does AL HARAS check today, what evidence supports each check, and what is not covered?

## Answer in brief

- AL HARAS is the HYBA Security product. In this repository it is a Python library and an authenticated API (`/v1/al-haras`).
- It makes four computed checks before work is admitted. Each check runs on the request’s own data and returns a receipt signed twice: with Ed25519 and with ML-DSA-87 (FIPS 204, post-quantum).
- It holds **no** certification, accreditation or authorisation. That includes NCSC principle assessments, FedRAMP, DoD impact levels, FIPS 140-3 module validation, NIST algorithm validation (ACVP) and Common Criteria. No assessor has reviewed it. Implementing the FIPS 204 algorithm through a vetted library is not a validation.
- Keys are held in process memory unless environment-supplied seeds are configured (one for Ed25519, one for ML-DSA-87). No HSM or cloud KMS custody has been demonstrated.

## What is checked, and the evidence

| Check | What the code computes | Failure mode | Evidence |
|---|---|---|---|
| State consistency | The exact cellular-sheaf coboundary δ⁰s of the node or agent states on a graph, with orthogonal restriction maps. States agree iff δ⁰s = 0. The worst edge and the node or nodes whose removal restores agreement are reported. The nearest consistent state (projection onto H⁰) is the in-place repair. | Disagreement above the stated tolerance (default 0) means rejection. Malformed input returns HTTP 422. | `tests/test_al_haras_core_exact.py::TestSheafConsistency`, `tests/test_al_haras.py::TestInspect` |
| Trace repair | Reed–Solomon RS(48,32) over GF(257) with Berlekamp–Welch decoding. It corrects up to 8 corrupted bytes per 32-byte block in place, then checks the SHA-256 of the repaired trace. | More than 8 errors in a block is reported as uncorrectable. It is never reported as healed. | `TestReedSolomonHealing`, `TestTraceRepair` (drill and protect→repair round trip) |
| Expander certificate | The Paley graph P(257) is verified strongly regular pair by pair. Its spectrum follows exactly, and the Ramanujan bound is decided by an exact integer inequality. Random-walk mixing and connectivity after 30% vertex loss are also computed. | A failed check reports `RAMANUJAN_BOUND_NOT_MET`. | `TestPaleyExpander` |
| Decision receipts | Two signatures over the same canonical JSON: Ed25519 (RFC 8032) and ML-DSA-87 (FIPS 204, category 5) with the context string `chronus/al-haras/receipt/v1`, both from pyca/cryptography ≥ 48. A receipt verifies only if both do. Tests measure the FIPS 204 key and signature sizes and recompute the FIPS 204 message representative μ independently of the library. | Any change to the body, either signature, the algorithm label or a stripped post-quantum part means `verify → False`. Review records also pin both public keys. | `TestReceiptsAndDecisions`, `tests/test_al_haras_receipts_post_quantum.py` |

Supporting algebra, all exact: Fibonacci braid relations over ℤ[ζ₅], Lucas and Zeckendorf identities, and an elliptic-curve point count used as a payload fingerprint. The fingerprint is **not** an integrity control. Integrity comes from SHA-256 and the signed receipt.

Access control: every AL HARAS `POST` endpoint requires a tenant bearer token (`401` otherwise). The motto “Speak friend and enter or you shall not pass” is a product line, not a credential. Earlier code accepted that phrase as a passphrase. That has been removed.

## Further AL HARAS modules

Each module computes its result from its inputs and states its limits in its own docstring. None is deployed.

| Module | What it computes | Not established | Tests |
|---|---|---|---|
| `agentic_immune.py` | Exact state agreement across an agent pipeline, with located and verified repair; tool calls admitted only if three copies of the arguments agree exactly. Prompt screening is a labelled pattern heuristic. | Detection of prompt injection from text | `tests/test_al_haras_agentic_orbital_exact.py` |
| `orbital_mesh.py` | A satellite mesh on an exactly certified Paley host graph; reachability after hashed or targeted link loss; a Reed–Solomon upset drill under an explicit flux assumption | Radiation immunity; delivery guarantees under a fixed share of lost links; the LPS graph | `tests/test_al_haras_agentic_orbital_exact.py` |
| `defense_frontiers.py` | Four demonstrations: swarm agreement under bounded noise, signed stream receipts, exact normal-shock relations, Reed–Solomon trace repair | CFD, STARK/FRI proofs, any deployment | `tests/test_al_haras_defense_frontiers_exact.py` |
| `threshold_mpc.py` | Shamir (t, n) sharing over F_P with P = 2^521 − 1; tamper-evident shares; joint Ed25519 authorisation | Multi-party computation, threshold signatures, HSM custody | `tests/test_al_haras_mpc_settlement_exact.py` |
| `sovereign_settlement.py` | Exact boundary ∂₁ of a transfer batch against declared net positions; balance-based double-spend and replay checks | Connection to any payment system; finality; regulatory standing | `tests/test_al_haras_mpc_settlement_exact.py` |
| `zk_neural.py` | An exact polynomial-identity trace receipt over F₂₅₇ for a toy layer | Zero knowledge, succinctness, FRI | `tests/test_al_haras_hardware_zk_formal_exact.py` |
| `hardware_t_isa.py` | A software model of a proposed RISC-V coprocessor extension over ℤ[ζ₅], with per-register error correction | Any hardware run, synthesis or timing | `tests/test_al_haras_hardware_zk_formal_exact.py` |
| `formal_invariants.py` | Executable exact checks behind the Lean notes | Machine-checked proofs in CI | `tests/test_al_haras_hardware_zk_formal_exact.py` |
| `holographic_qec.py` | The [[5,1,3]] stabilizer code, exactly (one pentagon of the HaPPY construction) | Larger tilings; any physics beyond this tensor | `tests/test_al_haras_qec_dualrail_policy_exact.py` |
| `tempest_scrambler.py` | Dual-rail encoding identities and leakage-model arithmetic | Any emission measurement or TEMPEST protection | `tests/test_al_haras_qec_dualrail_policy_exact.py` |
| `autonomous_roe.py` | Completeness of a review record against required criteria, signed; decides nothing | Any automated decision | `tests/test_al_haras_qec_dualrail_policy_exact.py` |
| `millennium_security.py`, `millennium_unification.py` | Exact Ollivier–Ricci curvature with certificates, a Hodge split of a trace, p-adic address-set relations, in-place zeroisation | Anything about the Millennium Prize Problems; two routes answer `NOT_IMPLEMENTED` | `tests/test_al_haras_millennium_exact.py` |

## UK NCSC Cloud Security Principles: register, not an assessment

The API returns this register at `GET /v1/al-haras/status` and from `SovereignGovernanceEngine.audit_sovereign_compliance`. Every principle is **NOT ASSESSED**. The register lists repository evidence for each principle, where any exists. It is a starting point for an assessor, not a compliance statement.

| # | Principle | Repository evidence (not an assessment) |
|---|---|---|
| 1 | Data in transit protection | None in this repository; TLS termination is a deployment responsibility |
| 2 | Asset protection and resilience | Reed–Solomon trace repair; content-addressed receipts |
| 3 | Separation between customers | Tenant-scoped tokens in `src/chronus/service/auth_middleware.py` |
| 4 | Governance framework | `docs/claim-audit.md`, release decision, this record |
| 5 | Operational security | CI tests, static analysis, dependency audit |
| 6 | Personnel security | None |
| 7 | Secure development | CI, `AGENTS.md` |
| 8 | Supply chain security | Pinned GitHub Actions; `pip-audit` |
| 9 | Secure user management | `auth_middleware.py` |
| 10 | Identity and authentication | `auth_middleware.py` |
| 11 | External interface protection | Request validation and size limits on the AL HARAS API |
| 12 | Secure service administration | None |
| 13 | Audit information and alerting for customers | Decision receipts signed with Ed25519 and ML-DSA-87 |
| 14 | Secure use of the service | None |

## Not implemented, and not claimed

- Hardware enforcement, an operating-system kernel, or clock-cycle or nanosecond latencies. Timings come only from `benchmarks/benchmark_al_haras_security.py` on the machine that runs it.
- A FIPS 140-3 validated cryptographic module, and NIST ACVP test vectors for ML-DSA-87 in CI. The older ML-DSA module in `chronus.security.signers` is not a FIPS 204 implementation ([claim audit](../claim-audit.md)); AL HARAS does not use it.
- HSM, PKCS#11 or cloud-KMS key custody.
- Detection of prompt injection or malware from content. The consistency check compares supplied states; it does not classify text.
- The Lubotzky–Phillips–Sarnak graph on PSL₂(F₂₅₇), TEMPEST/RF emission protection, and any customer, partner or government deployment.

## How to verify

```bash
python -m pytest -q tests/test_al_haras_core_exact.py tests/test_al_haras_receipts_post_quantum.py tests/test_al_haras.py
python -m pytest -q tests/test_al_haras_*_exact.py tests/test_al_haras_runner_scripts.py
python benchmarks/benchmark_al_haras_security.py --json al-haras-measurements.json
```
