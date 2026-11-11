# AL HARAS (HYBA Security): notes reconciled with the implementation

**Status:** controlling record for AL HARAS claims, alongside [`docs/claim-audit.md`](../claim-audit.md) and [`RELEASE_DECISION_MCKINSEY_TECH.md`](../../RELEASE_DECISION_MCKINSEY_TECH.md). Reviewed against GitHub `main` at `438e4093` (after PR #28) on 11 November 2026. AL HARAS remains **not release-qualified**.

## Conclusion

Every AL HARAS note in the repository now matches the code. Before this change, most AL HARAS results were fixed values or labels. Examples: a spectral value of 28.86; an obstruction norm of 1.4142 returned when a flag was set; “healing” that hashed the payload; a substring search for “MALICIOUS” that decided rejection; a fabricated `mldsa65_` signature; and status fields such as `FEDRAMP_HIGH_CERTIFIED`, `COMPLIANT_PASS`, `94/94_GREEN_CERTIFIED` and `KMS_BOUND_CUSTOMER_CUSTODY`.

The mechanisms the notes describe in mathematical terms now run as exact computations with tests: consistency of node states over a cellular sheaf, trace repair, an expander certificate, braid relations and signed receipts. Two withdrawn claims were investigated and then **implemented**, so they are reinstated with tests:

- **Post-quantum receipts.** Every receipt carries an ML-DSA-87 (FIPS 204) signature alongside Ed25519.
- **Authenticated API.** Every AL HARAS `POST` endpoint now requires a tenant token.

Claims that code cannot support were removed from the notes, the API and the UI. These include certifications, named military or government sites, clock-cycle latencies, McKinsey or Accenture authority, “production qualified” status and customer-held HSM custody.

## How to read the tables

- **Implemented**: code in this repository computes the claim’s mechanism, and the named tests cover it.
- **Corrected**: the note overstated what code can show. The note now states what is computed.
- **Withdrawn**: no implementation or evidence supports the claim. It was removed from the notes, the API and the UI.
- **Not implemented**: the claim describes future work and is labelled as such.

Evidence commands:

```bash
python -m pytest -q tests/test_al_haras_*.py tests/test_behavioral_sovereign_attestation.py
python scripts/ci/sovereign_attestation.py          # recomputes the AL HARAS checks
python benchmarks/benchmark_al_haras_security.py --json al-haras-measurements.json   # timings on your machine
```

## 1. Master dossier (`docs/executive/CHRONUS_GPIU_AL_HARAS_MASTER_DOSSIER.md`)

The section structure is kept. Each section is corrected in place.

| Claim in the note | Status | What the code does now | Evidence |
|---|---|---|---|
| McKinsey & Company and Accenture as “joint venture authority”; signatures by a “McKinsey of Tech” partner and Accenture Federal | Withdrawn | None. The style guide treats a McKinsey–Accenture standard as an internal quality bar only. | [Product style guide](../directives/PRODUCT_STYLE_GUIDE.md) |
| Target entities: NVIDIA, Palantir, NATO / Five Eyes | Withdrawn | No customer or partner is named without an agreement. | — |
| Sheaf obstruction engine; ‖H¹‖ = 1.41421356 | Implemented, corrected | Exact δ⁰ over ℚ with orthogonal and exact Householder restriction maps; dim H⁰ and dim H¹; worst edge, isolating node, nearest section. 1.41421356 = ‖δ⁰s‖ = √2 for (1, 0)/(0, 1) on one edge. | `test_al_haras_core_exact.py::TestSheafConsistency`; attestation pillar 1 |
| Isolation in 38 ns | Withdrawn | The figure was `hardware_cycles = 38` in `run_irrefutable_audit.py`. The audit now reports measured software timings. | `scripts/ci/run_irrefutable_audit.py` |
| 0.0% cross-blade drift | Withdrawn | Not measured. | — |
| DSW instanton healer; 1 clock cycle; 0 bytes rollback | Corrected | Reed–Solomon RS(48,32) over GF(257), Berlekamp–Welch; up to 8 bytes per block corrected in place, verified by SHA-256; `checkpoint_restore_used` is False. | `TestReedSolomonHealing`; `tests/test_al_haras.py` |
| NIST FIPS 204 ML-DSA-87 receipts | Implemented | Ed25519 + ML-DSA-87 over canonical JSON with FIPS 204 context `chronus/al-haras/receipt/v1`; both must verify. Sizes are checked against FIPS 204 Table 2 and μ is recomputed independently. Review records pin both keys. | `tests/test_al_haras_receipts_post_quantum.py` |
| FRI zk-STARK, line-rate verification | Not implemented | `zk_neural.py` issues an exact polynomial-identity trace receipt over F₂₅₇: not zero-knowledge, not succinct, no FRI. | `test_al_haras_hardware_zk_formal_exact.py` |
| NATO / CNI self-healing grid, 100% uptime | Corrected, partly withdrawn | Frontier 4: a Reed–Solomon trace-repair drill on telemetry. Deployment, NATO naming and uptime are withdrawn. | `test_al_haras_defense_frontiers_exact.py` |
| Diplomatic enclaves; named command centres; PKCS#11 HSM custody; “0 bytes” egress | Corrected, partly withdrawn | Shamir (t, n) over 2^521 − 1 with tamper-evident shares and joint Ed25519 authorisation. Sites, HSM custody and egress figures are withdrawn. | `test_al_haras_mpc_settlement_exact.py` |
| Biomolecular and oncology simulation | Not implemented | No such code exists. The v36 `LefschetzThimbleSignSolver` assigns Im S = 0. | — |
| AI governance compliance (GDPR, HIPAA, EU DSA) | Withdrawn | The consistency check is a mathematical tool, not a compliance outcome. | — |
| Orbital meshes: SEU elimination; zero stall with 30% of nodes blinded; LPS graph | Corrected, partly not implemented | `orbital_mesh.py` provides a certified Paley host graph, link-loss reachability, a Reed–Solomon upset drill and braid-word packets. The LPS graph is not implemented. | `test_al_haras_agentic_orbital_exact.py` |
| Agentic immune system; rogue agent severed in 1 clock cycle | Corrected | Exact state agreement with verified repair; three-copy tool-call comparison; a labelled prompt heuristic. | `test_al_haras_agentic_orbital_exact.py` |
| Legal redlining with court-admissible certificates | Not implemented | No clause engine exists. | — |
| CBDC rails: ∂₁c = 0 makes double-spends unrepresentable; mBridge / BIS Nexus | Corrected | Exact ∂₁ against declared net positions; a balance-based double-spend check and a replay check; neutral account labels; no finality or standing. | `test_al_haras_mpc_settlement_exact.py` |
| \$5.3T capex relief; 10× throughput per megawatt | Withdrawn (Chronus) | No source or measurement. | [Claim audit](../claim-audit.md) |
| 94/94 GREEN; 8 gates certified | Withdrawn | The gate table now gives each gate’s current status. | Dossier Part IV |
| I24 persistent Betti number β₁ = 1 | Not implemented | The earlier code returned a fixed value. | — |

## 2. Security brief, CISO brief and API responses

| Claim | Status | Now | Evidence |
|---|---|---|---|
| NCSC 14 principles “COMPLIANT/EXCEEDS” | Withdrawn | A register with every principle `NOT_ASSESSED` and repository evidence pointers. | `sovereign.py`; `GET /v1/al-haras/status` |
| FedRAMP High, DoD IL6 readiness | Withdrawn | No certification is held; the statement says so. | `test_hyperscaler_user_journeys.py` journey 3 |
| ML-DSA-65 signing | Implemented as ML-DSA-87 | See section 1. | as above |
| Customer-held PKCS#11 HSM custody | Not implemented; status computed | `ALHarasKMSCustodyManager` derives `status` from the provider used (`LOCAL_KEY_NOT_CUSTOMER_HELD` today), issues no PKCS#11 URI, and marks generated key references as placeholders. | `test_security_full_coverage.py`, `test_instant_provisioning.py` |
| “Speak friend and enter” as an access control | Corrected | It is the product motto only. Every `POST` requires a tenant bearer token (401 otherwise). | `tests/test_al_haras.py` |
| Fixed λ₂ = 28.86, 54.2% avalanche, 1.4142 on a flag, “MALICIOUS” substring | Corrected | Computed: Paley P(257) spectrum, measured avalanche on given inputs, exact δ⁰, computed rejection reasons. | `test_al_haras_core_exact.py` |

## 3. Module docstrings, SDK and frontier modules (`src/chronus/security/al_haras/`)

| Module (historical name) | Status | What it computes now | Tests |
|---|---|---|---|
| `engine.py` | Corrected | Legacy class names over the exact engines (sheaf, Reed–Solomon, Paley, braids, Hasse fingerprint, receipts) | `test_al_haras_core_exact.py` |
| `sovereign.py` (FedRAMP/NCSC statuses, `mldsa65_` signature) | Corrected | Governance register; signed inspections; OVID receipt chain | `test_al_haras.py` |
| `topological_os.py` (kernel; imported the v36 monolith at import time) | Corrected | Self-tests and admission by state; no v36 import | `test_security_full_coverage.py` |
| `agentic_immune.py`, `orbital_mesh.py`, `defense_frontiers.py` | Corrected | See section 1 | `test_al_haras_agentic_orbital_exact.py`, `test_al_haras_defense_frontiers_exact.py` |
| `threshold_mpc.py` (“topological anyon threshold MPC”) | Corrected | Shamir over 2^521 − 1 | `test_al_haras_mpc_settlement_exact.py` |
| `sovereign_settlement.py` (“homological CBDC settlement”) | Corrected | Exact boundary and balance checks | `test_al_haras_mpc_settlement_exact.py` |
| `holographic_qec.py` (“holographic QEC”) | Corrected | The [[5,1,3]] code, exactly | `test_al_haras_qec_dualrail_policy_exact.py` |
| `tempest_scrambler.py` (“TEMPEST emission scrambler”) | Corrected | Dual-rail identities and leakage-model arithmetic; no emissions measured | `test_al_haras_qec_dualrail_policy_exact.py` |
| `autonomous_roe.py` (“autonomous rules of engagement”) | Corrected | A signed completeness record that decides nothing; both signing keys pinned | `test_al_haras_qec_dualrail_policy_exact.py`, `test_al_haras_receipts_post_quantum.py` |
| `zk_neural.py` (“zk-ML”, “zk-STARK”) | Corrected | F₂₅₇ trace receipt (see section 1) | `test_al_haras_hardware_zk_formal_exact.py` |
| `hardware_t_isa.py` (“silicon ALU”, one cycle) | Corrected | A software model; `RTL_SEMANTICS` records which RTL operations match it | `test_al_haras_hardware_zk_formal_exact.py` |
| `formal_invariants.py` (“formally verified Lean 4”, Common Criteria tier) | Corrected | Executable exact checks; Lean is not compiled in CI | `test_al_haras_hardware_zk_formal_exact.py` |
| `millennium_security.py`, `millennium_unification.py` (Millennium Prize Problems; “Spectre impossible”; sub-nanosecond purge) | Corrected, partly not implemented | Exact Ollivier–Ricci curvature with certificates, a Hodge split, p-adic address sets and verified zeroisation. Picard–Lefschetz and “unification” return `NOT_IMPLEMENTED` (HTTP 501). | `test_al_haras_millennium_exact.py`, `test_millennium_security.py` |
| SDK docstrings (“line-rate FRI zk-STARK”, “silicon ALU”, an `SDA_PWSA` default packet) | Corrected | Neutral defaults; accurate descriptions | — |
| `chronus.security` package docstring (Pentagon, GCHQ, NATO) | Corrected | Lists what the package contains | — |

## 4. Formal and hardware sources

| Note | Status | Now |
|---|---|---|
| `formal/lean4/ChronusAlHaras.lean` | Corrected | Coboundary lemmas for the constant sheaf. Specification source; not compiled in CI. |
| `formal/lean4/SheafLaplacian.lean` (“machine-checked”, EAL7, DO-178C Level A, DSW one-cycle theorem) | Corrected | The header states that two proofs end in `sorry`, that the DSW structure assumes its conclusion, and that there is no CC or DO-178C claim. The Lean code is unchanged. |
| `hardware/rtl/t_isa_coprocessor.sv` | Corrected | Labelled an unverified sketch. Two logic bugs were fixed. Per-opcode agreement with the model is recorded; three opcodes do not match the model and are labelled. |

## 5. Scripts, attestation and benchmarks

| Note | Status | Now |
|---|---|---|
| `scripts/ci/run_irrefutable_audit.py` (38 ns) | Corrected | The AL HARAS section is measured. |
| `scripts/ci/sovereign_attestation.py` pillar 1 (instanton charge k = 1; “H¹ = 0” label) | Corrected | Six computed checks, including a disagreement that must give ‖δ⁰s‖² = 2 and a verified Reed–Solomon repair. Measured values are included. |
| Pillar 4 (“7 Millennium Prize security dualities”) | Corrected | Renamed `exact_checks_passed`; Picard–Lefschetz is listed under `not_implemented`. |
| `benchmarks/benchmark_al_haras_security.py` | Corrected | Measurement only, with no fixed figures. |

## 6. Runner infrastructure (`infra/runners/al-haras/`, `docs/sovereign-hardening.md` §3)

| Claim | Status | Now |
|---|---|---|
| Pre-job hook verifies pinned LSM programs | Implemented | The bootstrap checks object hashes against a manifest, attaches the LSM programs and writes a root-owned attestation. The hook checks the attestation, the manifest and the live LSM list. |
| “Cryptographic” receipt | Corrected | The receipt holds SHA-256 digests and is explicitly unsigned. The job template signs it with build provenance. |
| Registration runs as the runner user | Implemented | `+`-prefixed root steps; the token is read from a root-only file and never placed in the unit environment. |
| Nothing persists between jobs | Implemented | Hooks are root-owned; the runner is rebuilt each cycle; `PrivateTmp`, `RemoveIPC` and control-group kill are set. |
| Hardware or kernel root of trust | Withdrawn | No TPM, SEV-SNP or TDX evidence is collected. |
| Runner group `sovereign-compute` for this repository | Corrected | Runner groups are organisation-only, so routing uses labels. |

Evidence: `tests/test_al_haras_runner_scripts.py`. A real host is still needed to validate the LSM objects and bpftool fields.

## 7. Frontend, static pages and demos

| Note | Status | Now |
|---|---|---|
| Governance screen (called five missing client methods; certification chips) | Corrected | Calls the authenticated AL HARAS API, renders computed results and shows both receipt signatures. Type-checked, SSR and client checks pass. |
| `frontend/public/sovereign-dashboard.html`, `chronus-observatory.html` | Corrected | Labelled as static illustrations; certification chips relabelled. |
| Root prototypes (`al_haras_security_module.py`, `al_haras_sovereign_edition.py`, `al_haras_topological_os.py`) | Corrected | Thin demos over the real engines; not deleted. |
| `docs/HYPERSCALER_DATA_CONNECTOR_AND_USER_JOURNEYS.md` (AL HARAS lines) | Corrected | Signing, repair and consistency lines match the code. |

## 8. AL HARAS fields in Chronus connectors and onboarding

| Claim | Status | Now | Tests |
|---|---|---|---|
| Ingress rejection by “MALICIOUS” substring and fabricated vectors | Corrected | Computed reasons: supplied states that disagree, a configured test marker, or a requested drill | `test_zero_copy_connectors.py` |
| `al_haras_security_custody`: `H1_VORTEX_FREE_NORM_0.0`, `CUSTOMER_HELD_HSM_PKCS11`, `mldsa65_…` | Corrected | The sheaf check is reported as not evaluated when no states are supplied; custody comes from the binding; a verified Ed25519 + ML-DSA-87 receipt is included. | `test_zero_copy_connectors.py` |
| Onboarding `al_haras_kms_status = KMS_BOUND_CUSTOMER_CUSTODY` | Corrected | Computed from the binding: `LOCAL_KEY_NOT_CUSTOMER_HELD` | `test_instant_provisioning.py` |

## 9. Findings outside AL HARAS (recorded, not changed here)

- `chronus.security.signers.MLDSASigner` is not ML-DSA: verification depends on the private seed ([claim audit](../claim-audit.md)). AL HARAS no longer relies on it. Recommended fix: back it with pyca/cryptography ML-DSA, as the AL HARAS receipts and the v36 signer now are.
- `ZeroCopyConnectorManager` benchmarks substitute fixed figures when a measured time is below 1 ms (for example `scan_ms = 120.81`), and quote dataset sizes and compression ratios that nothing measures. These are Chronus claims under the claim audit.
- Historical directives under `docs/directives/` and the `archive/` tree are preserved unchanged by owner rule. They are not evidence.
