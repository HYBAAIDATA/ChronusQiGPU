# Implementation assignment — CHRONUS consolidation, preservation and elevation

**Repository:** `HYBAAIENTERPRISE/HYBAEnterprise`, initially compare against `main` SHA `c4ea01fd1b82d411db3fd394c96fc143579b08b5`; pin the true exact HEAD at start and record any drift.

**Mission:** Consolidate CHRONUS into a single governed software-defined GPU and heterogeneous execution product, **preserving and elevating** the originally conceived mathematical graphics engine, independent native virtual iGPU, host GPU augmentation, exact geometry, resident Hendrix, ASIC-like hashing, Lucas/Pisot scales, QX/compiler/runtime and multi-workload services. Close implementation and evidence gaps instead of redefining objectives downwards. Do not absorb TURING VQC semantics, PYTHIA mining strategy, Kellogg tensor mathematics, OVID transformation, THESEUS custody, Geodesic indexing, AL HARAS authorization or Salamander healing authority.

## Governing sources — read before editing

1. [CHRONUS production constitution](https://app.notion.com/p/3f0bcc6fa49981ef9b12f67cab2d5f21)
2. [Enterprise architecture authority register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19)
3. [THESEUS custody manual](https://app.notion.com/p/3f0bcc6fa4998106bbd3f0438cfa393e)
4. [Chronus Workflows 01–08](https://app.notion.com/p/3f0bcc6fa49981ef9b12f67cab2d5f21) (children of constitution)
5. [Original Chronos graphical engine design](https://app.notion.com/p/047301c2d99943fa9359b0dbf5979c02)
6. [Mathematical reframe, substrate-agnosticism](https://app.notion.com/p/d37aaf2284c64c35a0671feee3ee616d)
7. [Historical revised code review and 8K claim reconciliation](https://app.notion.com/p/3efbcc6fa49980a89cedef61ffef38b0)

## Required current-head inventory

Produce a machine-readable census of all public and production-reachable entry points, import paths, modules, wheels, console scripts, versions, kernels, backends and distributed sources. Include `chronus/`, `chronos/`, `gpu/`, `packages/chronos-one-igpu/`, `chronus/packages/chronos-one-igpu/`, `chronus/packaging/`, `packaging/`, and their tests and consumers. Trace Turing, Tensor/Kellogg, PYTHIA/mining, EUCLID, THESEUS and AL HARAS integration.

Verify the actual status of the `reports/CHRONUS_CONSOLIDATION_REPORT.json` claims: on the inspected main SHA it asserts four trees were deleted even though `gpu/`, `chronos/`, `packages/chronos-one-igpu/`, and `chronus/packages/` remained. Investigate all `resident_hendrix.py` duplicates; five inspected copies shared a blob SHA while `chronus/resident_hendrix.py` differed. Use code/digest/behavior comparisons and import-resolution tests, not paths or names alone. Reconcile distributions including `packages/chronos-one-igpu/pyproject.toml` (`chronos-one-igpu` 3.11.3rc2), the nested `hyba-chronos-one-igpu` 1.0.0 and `hyba-chronus-igpu` 1.0.0. Respect owner first-public-release 1.0.0 policy while retaining internal lineage. Do not silently replace user interfaces or delete older package trees.

## Implementation scope

**A. Canonical architectural authority:** Correct contradictory OVID/THESEUS ownership in `chronus/README.md`, associated manifests, diagrams, docs and tests. OVID owns versioned transformation/fold/materialisation; THESEUS owns durable custody/journal/replay/provenance; Geodesic owns rebuildable search. Keep CHRONUS execution-only authority and TURING independent VQC identity. If a material design decision is required, submit a bounded proposal rather than changing the owner-controlled constitution.

**B. Single controlled product with two peer modes:** Native CHRONUS GPU must execute on a software/CPU substrate with no physical GPU prerequisite; host-GPU augmentation uses only measured/qualified physical backends and never silently substitutes an unapproved CPU. Preserve logical device contracts, compiler/ABI, memory, exactness, quotas, backend/device identity, receipts, latency and work counts. Treat CUDA, Metal, OpenCL, remote and ASIC as distinct per-workload capability lanes, not interchangeable claims.

**C. Mathematical graphics lineage:** Inventory and protect M32/icosahedron–dodecahedron geometry, QSDL parse/compile, Hamiltonian library, evolution, QX, reconstruction, PRISMA/geodesic render, actual supersampling, folded-memory, numerical validation and rollback. Compare original 8K/60fps, lighting, memory and mathematical claims against real workloads; preserve goals but mark unsupported performance/physics as not evidenced. Benchmark real render work against exact/conventional reference at matched precision and quality, counting end-to-end cost. Revalidate the historical ~4.887s one-sample 8K NumPy benchmark instead of importing it as current speed.

**D. Mining execution only:** Preserve PYTHIA-authorized 32 coarse directions → φ-weighted exact 11D → H4/600 → optional exact Hilbert itinerary → sealed Hendrix resident execution → independently verified SHA-256d. Preserve prepared midstate, fused check, lane scheduling and stale-work fencing/epoch cancellation. CHRONUS must not choose PYTHIA's mining search algorithm or create a share-acceptance claim; do not convert virtual lane counts or tensor TFLOPS into hashes/second. Require independent host candidate verification. Probe open PR #85 for device name/identity wiring but do not import unapproved external edits blindly.

**E. Production composition:** Demonstrate production-mode AL HARAS admission cannot be omitted, and mandatory operational evidence is committed via THESEUS with stable IDs, schema/producer versions, source digests, tenant/epoch/correlation IDs, backend identity, validated response, restart/replay. Current `RuntimeDaemon` accepts optional `admission_policy` and `custody`, and selects durable custody only for `constraints={"custody":"required"}`; determine if any production entry point bypasses mandatory policy and correct it without breaking explicitly supported development mode. OVID transformations remain separately versioned, reversible/bounded and verifiable. Salamander may diagnose/remediate only within authorization and rollback fences.

**F. Packaging/installability:** Elect the one canonical executable source and preserve requested historical/compatibility surfaces as tested facades or explicitly approved migration. Produce a package ownership manifest with no conflicting file ownership, precise dependency ranges, version provenance, complete wheel/sdist content and clean offline install matrix. Do not publish, merge, delete a public import or promote status without owner gate.

## Minimum adversarial tests and evidence

- Direct vs packaged source equivalence, import compatibility, exact-head clean installs and both product modes on a GPU-less host.
- Actual backend bind, known-answer device tests, CPU differential with exactness/precision declared, missing-driver and wrong-device fail-closed behavior, cancellation/timeout/device loss, resource pressure and sustained measurement for each physical lane.
- M32→11D→600 geometric invariants, exact rational/Q(φ) proof identities, sealed Hendrix immutability, tampered plan/hash/header/target rejection, no stale-job execution and accurate SHA-256d work accounting.
- QSDL→Hamiltonian→evolution→render outputs, multi-object semantics, 1 vs N samples/pixel, independent oracle, image precision/quality and reproducible measured memory/latency.
- Tenant isolation, AL HARAS deny, custody failure, tampered receipt, restart/replay with fresh process, retention and rollback; product mode and hardware identity retained across replay.
- CI/current-head statuses distinct from earlier PR evidence; preserve raw logs, commands, package hashes, diffs, faults and independent replay instructions.

## Deliverables / completion rule

Create one bounded CHRONUS implementation PR with code, tests, migration/compatibility map, canonical source and wheel manifest; a claim/evidence ledger for each workload and backend; reproducible exact-head qualification scripts; and a `CHRONUS_CLOSURE_DOSSIER.md` with what passed, failed, was missing, or was gated. Preserve one-to-one feature parity and avoid removing anything without replacing it and testing the replacement. Keep physical GPU performance, 8K target, accepted pool shares, quantum-advantage and production status **unavailable** unless separately qualified. Stop at owner gate for architecture, production, release or publication approval. **Do not self-certify.**
