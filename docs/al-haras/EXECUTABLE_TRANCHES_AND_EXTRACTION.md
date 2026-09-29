# Executable tranches, extraction, and schema v2 status

## Implemented in this branch

- Canonical `PRIMEObjectV2`, `FoldContract`, `OperatorContract`, `ResultReceipt`, `EvidenceObject`, `BackendCertificate`, `EnterprisePolicyContext`, and `HYBAModule` dataclasses.
- Object creation through an injected exact-math backend, conjunctive policy decisions, transactionally appended tenant/instance lineage, and invariant-gated proof creation.
- Model blob/card/evidence registry with approval evidence requirements and deterministic/nondeterministic training declarations.
- Evidence collection, immutable content-addressed vault reference, quality, ontology, and bounded agent-action helpers.
- Fold/operator registries and a receipt-producing executor with explicit rehydration count.
- Non-destructive extraction routing, four extraction stages, `mla1517-core` public API audit, environment-failure classifier, signed gate runner, thirteen sprint definitions (0–12), and release trains R0–R4.
- Refuted-claim register extended with the architecture review's verbatim claims.
- Repository-specific Makefiles and a GitHub Actions evidence-gate workflow that only invokes files present in the branch.

## Evidence

The combined local dependency-free suite passes 21 tests and bytecode compilation succeeds. The current promotion manifest remains conservative: Guardian, Identity, Witness, Schema and Mediation are CONTRACTED; Folded and Pisot remain RESEARCH.

## Not performed or claimed

- No files were moved or deleted from PYTHIA.
- No `mla1517-core` repository was created and no dependency was declared against an unpublished package.
- No history rewrite, import rewrite, prototype ownership transfer, or Stage 0–3 extraction was executed.
- The workflow does not fabricate strict-hardware, C/OpenCL/RTL, resilience, independent-witness, HSM, or external-system evidence.
- Existing repository CI remains authoritative in addition to the new focused evidence job.
