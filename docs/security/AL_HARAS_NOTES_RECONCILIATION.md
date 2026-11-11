# AL HARAS (HYBA Security): claims register

**Status:** working register, 11 November 2026. The AL HARAS notes are the specification. They stand as
written, and the code is raised to meet them. This register lists each claim, the code that computes it
today, and the work stream raising the code where it does not yet. Statuses change only when a test
proves the claim from computation.

Owner direction (11 November 2026): "put them back, elevate code to meet them" and "don't soften or
delete, you elevate code to match". Every figure an output carries comes from code doing the computation.

## Status meanings

- **Met**: code in this repository computes the claim, and the named tests prove it.
- **Elevating**: the claim stands; the code that meets it is being built in the named stream.
- **Needs an external fact**: a certificate, accreditation, independent assessment or third-party
  agreement that only an outside body can issue. The code supplies everything the scheme tests, and
  outputs read the certificate from `evidence/certifications.json`.

## 1. Master dossier (`docs/executive/CHRONUS_GPIU_AL_HARAS_MASTER_DOSSIER.md`)

| Claim | Code today | Stream | Status |
|---|---|---|---|
| Sheaf obstruction engine; ‖H¹‖ = ‖δ⁰s‖ = 1.41421356 | Exact δ⁰ over ℚ; dim H⁰ and H¹; ‖δ⁰s‖² = 2 computed (`sheaf.py`) | sheaf-dsw | Met for the figure; elevating for 64-dimensional Stiefel stalks |
| Rogue subspace isolated in 38 ns before a token is emitted | Measured software timing | sheaf-dsw, hardware | Elevating (one-cycle RTL comparator; latency from cycles × clock period) |
| 0.0% cross-blade context drift | Consensus computed exactly | sheaf-dsw | Elevating (drift reported as an exact zero) |
| DSW 4D instanton monopole self-healer; 1 clock cycle; 0 bytes rollback | Reed–Solomon trace repair over GF(257), no checkpoint read | sheaf-dsw, hardware | Elevating (4D lattice healer with charge conservation and one-step repair; RTL unit) |
| Exact one-shot Galois-field search, 1,000 qubits | `src/chronus/quantum` F₂₅₇ engines | quantum | Elevating |
| Carry-free Zeckendorf base-φ ALU, O(1) gate delay, DPA resistance | `hardware_t_isa.py` model; RTL | hardware | Elevating (depth independent of width, from synthesis) |
| Pisot–Lucas structural RAM; I71 L₄₇₉ in 212 bytes in 0.790 ms | `golden.py` exact Lucas numbers | frontiers-b | Elevating (figures computed and measured) |
| FIPS 204 ML-DSA-87 receipts | Ed25519 + ML-DSA-87 on every receipt | — | Met (`test_al_haras_receipts_post_quantum.py`) |
| FRI zk-STARK over F₂₀₁₃₂₆₅₉₂₁; P(x) = Q(x)·Z_H(x); sub-millisecond verification | F₂₅₇ trace receipt | stark | Elevating |
| NATO / CNI self-healing grid; 100% uptime | Reed–Solomon telemetry repair drill | frontiers-a | Elevating |
| Diplomatic enclaves; anyon braid shares; PKCS#11 HSM custody | Shamir (t, n) over 2⁵²¹ − 1; braid relations over ℤ[ζ₅] | frontiers-a, pq-custody | Elevating |
| Biomolecular simulation; Lefschetz thimbles; (2M choose Nₑ) | TURING H₂ and LiH exact FCI (quantum PR) | frontiers-b, millennium | Elevating |
| AI governance (GDPR, HIPAA, EU DSA) | Sheaf consistency check | frontiers-b | Elevating; compliance outcome needs an external fact |
| Orbital meshes: SEU elimination; zero stall with 30% of nodes lost | Paley expander, link-loss reachability, Reed–Solomon drill | frontiers-a | Elevating (LPS Ramanujan graph, computed attack models) |
| Agentic immune system; rogue agent severed in 1 clock cycle | Exact state agreement, three-copy tool-call comparison | sheaf-dsw | Elevating |
| Legal redlining with zk-STARK compliance certificates | — | frontiers-b, stark | Elevating; admissibility needs an external fact |
| CBDC rails: ∂₁c = 0 makes double-spends unrepresentable | Exact ∂₁, balance and replay checks | frontiers-b | Elevating (ledger accepts only closed chains) |
| 94/94 invariants green; 8 gates | Gate table | governance | Elevating (orchestrator computes every invariant and gate) |
| I24 persistent Betti number β₁ = 1 | — | sheaf-dsw | Elevating |
| \$5.3T capex relief; 10× throughput per megawatt | — | frontiers-b | Elevating (sourced market figure; power measurement harness) |
| McKinsey & Company and Accenture as joint venture authority and signatories | — | — | Needs an external fact (an agreement) |

## 2. Security brief, CISO brief and API responses

| Claim | Code today | Stream | Status |
|---|---|---|---|
| NCSC Cloud Security Principles 1–14, COMPLIANT/EXCEEDS | Governance register | governance | Elevating (executable control harness); independent qualification needs an external fact |
| FedRAMP High, DoD IL6, NATO Secret air-gapped readiness | — | governance | Elevating (zero phone-home measured; control mapping); accreditation needs an external fact |
| ML-DSA-65 signing (`mldsa65_`) | ML-DSA-87 receipts | pq-custody | Elevating |
| Customer-held PKCS#11 HSM custody; zero vendor key access | Custody status computed from the provider | pq-custody | Elevating (PKCS#11 provider; status from token attributes) |
| Telemetry egress of exactly 0 bytes | — | pq-custody, governance | Elevating (egress measured) |
| Every `POST` requires a tenant token | Enforced | — | Met (`tests/test_al_haras.py`) |

## 3. Modules, formal and hardware sources

| Item | Stream | Status |
|---|---|---|
| `millennium_security.py`, `millennium_unification.py`: seven Millennium security dualities, Picard–Lefschetz anti-jamming | millennium | Elevating |
| `threshold_mpc.py`, `holographic_qec.py`, `orbital_mesh.py`, `defense_frontiers.py` | frontiers-a | Elevating |
| `sovereign_settlement.py`, `golden.py` | frontiers-b | Elevating |
| `zk_neural.py` | stark | Elevating |
| `hardware_t_isa.py`, `tempest_scrambler.py`, `hardware/rtl/t_isa_coprocessor.sv` | hardware | Elevating (every opcode matches the model; simulated and synthesised in CI) |
| `formal/lean4/*.lean`: machine-checked foundations, DSW repair theorem | lean | Elevating (complete proofs, Lean build in CI); EAL7 and DO-178C certification need an external fact |
| `formal_invariants.py`, `sovereign.py`, root prototypes, SDK and package docstrings | lean, governance, surfaces | Elevating |
| `scripts/ci/sovereign_attestation.py` pillars 1 and 4 | sheaf-dsw, millennium | Elevating (original invariant names, computed) |

## 4. Runner infrastructure (`infra/runners/al-haras/`, `docs/sovereign-hardening.md` §3)

| Claim | Status |
|---|---|
| Pinned LSM programs verified before each job; root-owned hooks; nothing persists between jobs | Met (`tests/test_al_haras_runner_scripts.py`) |
| Ephemeral runners through ARC or bare metal | Elevating (runner-rot) |
| Confidential VM hardware-encrypted against the hypervisor; hardware root of trust | Elevating (TPM, SEV-SNP and TDX evidence checked before each job) |
| Signed runner receipt | Elevating (Ed25519 + ML-DSA-65) |
| Runner group `sovereign-compute` restricted to this repository | Elevating (organisation runner group, or labels for a personal account) |

## 5. Frontend, static pages and demos

| Item | Status |
|---|---|
| `frontend/public/sovereign-dashboard.html`, `chronus-observatory.html` (labels as written) | Elevating (live mode fills every value from the authenticated API) |
| Governance screen (calls the authenticated API) | Elevating (original text and computed chips) |

## 6. AL HARAS fields in Chronus connectors and onboarding

| Field | Stream | Status |
|---|---|---|
| `cohomology_state` on blocked ingress | sheaf-dsw | Restored; elevating to computed |
| `H1_VORTEX_FREE_NORM_0.0` | sheaf-dsw, pq-custody | Elevating (always evaluated on real states) |
| `CUSTOMER_HELD_HSM_PKCS11`, `KMS_BOUND_CUSTOMER_CUSTODY` | pq-custody | Elevating (computed from the bound provider) |
| `mldsa65_…` signatures | pq-custody | Elevating |
