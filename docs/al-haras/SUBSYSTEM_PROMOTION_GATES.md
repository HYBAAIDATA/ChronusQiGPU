# Subsystem promotion gates and evidence controls

This increment makes promotion state executable. A subsystem advances only when every cumulative requirement identifier has non-empty evidence. Pilot and production additionally require rollback evidence.

## Current declared states

| Subsystem | State | Boundary |
|---|---:|---|
| Guardian | CONTRACTED | Aggregate conjunction exists, but 18 independently signed/evaluated surfaces are not yet established. |
| Folded execution | RESEARCH | One reference path exists in Miner; the full FoldContract, planning-time enforcement, tamper verifier and residual-growth evidence are incomplete. |
| Pisot | RESEARCH | Exact diagonal-only truncation exists; general exact SVD over Q(sqrt(5)) is unsupported. |
| Identity | CONTRACTED | Schemas and verifier boundaries exist; real IdP/HSM operation is unestablished. |
| Witness | CONTRACTED | Receipt and verifier contracts exist; independent external operation is unestablished. |
| Schema | CONTRACTED | Python logical/transport contracts exist; C/OpenCL convergence and round-trip vectors are unestablished. |
| Mediation | CONTRACTED | Path and disposition policy exists; installation across all runtime entry points is unestablished. |

No subsystem is declared VERIFIED, PILOT, or PRODUCTION.

## Added controls

- Cumulative gates for Guardian, folded execution, Pisot, identity, witness, schema and mediation.
- Evidence-bound `ResultEnvelopeV2` with fold-mode/rehydration consistency, integrity gates, verdict/witness/backend verification callbacks, and tamper-evident signature.
- SQLite claim register: VERIFIED and above require verified envelopes; PRODUCTION additionally requires an independent review.
- Consolidated prohibited-claim scanner.
- Python AST and native-source no-float scanner for explicitly selected exact paths.
- Cross-backend conformance runner requiring at least two available backends and exact equality.
- Machine-readable current-state evidence manifest and CLI.

## Developer evidence

- 16 dependency-free tests pass across the combined local implementation.
- Promotion manifest evaluates successfully at the conservative states above.
- Python bytecode compilation passes.

## Promotion remains blocked

PR merge is not a substitute for subsystem promotion. CI check publication, owner approvals, native PRIME-DB recomputation, actual middleware installation, external anchors, real IdP/HSM operation, full conformance vectors, crash/power-loss exercises, physical hardware evidence, soak evidence and independent review remain open.
