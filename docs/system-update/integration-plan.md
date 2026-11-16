# Four-phase integration: status against the verified codebase

## Phase 1 — Core ring and arithmetic unification: DONE

`src/chronus/core/` is the unified exact-arithmetic kernel: one import surface for ℤ[φ]/ℚ(√5) (`PhiElement`, `phi_power`, `verify_fold`), the metallic family (`MetallicElement`, `metallic_power`, `metallic_sequence`), Zeckendorf folding (`zeckendorf_encode/decode/increment`), limb encoding, and the universal scaling operator **`PVScale`** — every subsystem scales by advancing an exact PV index; coefficients materialize only at consumer boundaries. The honest qualification facade (`NOT_QUALIFIED` until a release-gate suite exists) is preserved. The purity gate blocks floating point from all of it, on every commit.

## Phase 2 — 32-lane polyhedral scheduler: DONE (software), RTL verified

- Lanes carry polyhedral identity: 12 dodecahedron face lanes + 20 icosahedron face-normal lanes (`polyhedral_lane`).
- Lane partitioning supports uniform and **Lucas-weighted strides** (`partition: "lucas"`) — lane boundaries advance by PV-scaled widths with exact disjoint coverage, tested.
- Traversal supports carry-free Zeckendorf stepping (`step: "zeckendorf"`), bijective and match-identical to binary order.
- The **unrolled 64-round bitwise SHA-256 engine** (`execution/asic_sha256.py`) is bit-identical to FIPS 180-4 and hashlib on standard vectors including the genesis header — the software reference for the silicon pipeline; selectable via `engine: "unrolled"`.
- RTL: the 32-lane carry-free fold array synthesizes in CI (8,095 pure-logic cells). The DEC router is implemented honestly as exact F₂₅₇ packet invariants (`ns_dec.PacketInvariant`) — no fluid-dynamics theatre.

## Phase 3 — Phyllotaxis storage and Theseus retrieval: DONE

Golden-angle lane distribution, per-tenant isolation, dedup, digest-verified reconstruction, multi-scale metallic lenses (golden/silver/bronze), and **PV scale lineage**: `scale_record` advances a record's PV index without touching content. Cassini/determinant parity is reported as metadata for companion-matrix states; arbitrary-record integrity remains digest + signature based.

## Phase 4 — Sovereign deployment and hermetic billing: DONE (software), provisioning pending

- Azure Bicep foundation compiles in CI; no subscription is authorized in this environment, so provisioning stays manual via the OIDC workflow.
- **`/billing/usage`** emits signed per-tenant usage receipts (Ed25519 over the usage digest, verifiable via `/verify`), process-local, explicitly not invoices. ML-DSA remains unimplemented and is reported as such.
- `/health` publishes the QiGPU surface inventory; `/console` renders live telemetry.

## Evidence

167/167 tests, 11/11 CI jobs, purity gate green, RTL testbenches pass. Details: `test-evidence.md`.
