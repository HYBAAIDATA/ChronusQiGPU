# Implementation assignment — Tensor / Kellogg consolidation and elevation

**Repository:** `HYBAAIENTERPRISE/HYBAEnterprise` (inspected SHA `c4ea01fd1b82d411db3fd394c96fc143579b08b5`; re-resolve exact HEAD).

**Mission:** Consolidate HYBA Tensor into an evidence-bound **logical tensor execution and verification interface**, preserving the deep exact quantum/tensor mathematical capabilities of **Kellogg** and July Geodesic Tensor/PULVINI work while using **CHRONUS solely as heterogeneous execution substrate**. Reconcile duplicate implementations, restore missing algorithms rather than delete capabilities, enforce precision and memory contracts, and produce clean reproducible packages and evidence. Do not fold Kellogg's mathematical authority into CHRONUS, TURING or the general logical router.

## Source hierarchy and documents

- [Enterprise authority register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19)
- [CHRONUS constitution](https://app.notion.com/p/3f0bcc6fa49981ef9b12f67cab2d5f21)
- [THESEUS shared custody manual (Tensor section)](https://app.notion.com/p/3f0bcc6fa4998106bbd3f0438cfa393e)
- [Geodesic Tensor + PULVINI V3 engineering record, 24 July](https://app.notion.com/p/ffd11e5552144c30ad38a5aaab0b5fcb)
- [Kellogg tensor convergence record](https://app.notion.com/p/c1df99715bbd4d569c77a6bac0540507)
- [Canonical `tensor/` logical package record](https://app.notion.com/p/60581e09bd08425aa4c5e27d989654c7)
- [July Geodesic Tensor convergence record](https://app.notion.com/p/c2f8e65369cb440996f6f3532f08bfb1)
- Current [`tensor/README.md`](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/blob/main/tensor/README.md), [`kellogg/CAPABILITY_MANIFEST.json`](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/blob/main/kellogg/CAPABILITY_MANIFEST.json) and package catalog.

**Crucial source distinction:** The canonical enterprise register grants no generic tensor reinterpretation of OVID/THESEUS. `tensor/` owns the logical typed operation contract, routing and verification; Kellogg owns exact tensor algebra, MPS/TT/MPO and relevant mathematical certificates; CHRONUS executes qualified workloads; OVID transforms/folds/materialises under typed contracts; PULVINI owns separately attributed folding representation; THESEUS owns durable records and restart; Geodesic owns search/indexing; TURING retains VQC semantics; PYTHIA retains mining strategy. Historical July ownership wording is provenance, not authority to transfer custody or VQC.

## Inventory and single ownership

Trace `tensor/`, `kellogg/`, `gpu/tensor.py` and `gpu/`, `chronus/tensor_compute.py`, Chronus native/portable tensor adapters, `turing_universal_quantum_computer/`, `python_backend/core_modules/` and the physical package outputs. Inventory public and internal entry points, duplicated math, precision coercions, implicit fallbacks, dead imports, unsafe serialization, bulk unfolds, and package file conflicts. Preserve one source of truth per exact algorithm, typed facade and backend. Do not delete compatibility paths without tested approved replacement.

Reconcile product naming in the package catalog rather than silently assuming a new `tensor` registry identity. `hyba-kellogg-tensor` is the exact maths distribution; the catalog describes `hyba-chronus-tensor` as planned, not yet scaffolded. Decide which source files are emitted by each approved product, with zero shared installed-file ownership and complete isolated wheel tests. Any material public package identity decision is owner-gated.

## Elevation and exactness scope

**Logical contracts:** Shape/rank/dtype/precision/exactness/error residual/memory cap/device-backend identity/cancellation/timeout/lineage/tenant/receipt. Reject invalid dimensions, truncation, implicit complex→real coercion, unsafe aliasing, overflows, unbounded resource requests and non-finite values before effects. Required explicit backend must fail closed; automatic selection may use documented lawful alternatives with actual backend recorded. Separate software, native-device and diagnostic/synthetic performance truths.

**Kellogg mathematics:** Preserve and certify exact rings/fields (`Z`, `Q`, `Q(i)`, `Q(sqrt2)`, `Q(zeta8)`, `Z[φ]`, `Q(φ)`, `GF(2)` as actually admitted), complex-preserving TT/MPS/MPO operations, decomposition/reconstruction, contractions and Hamiltonian MPO, bounded evolution, topology and persistence comparisons, quantum Fisher/natural gradient, phase/interference/measurement, certificates and exact solver domains. No silent float substitution in exact mode; approximation must carry quality/error budget and unit tests against independent reference.

**PULVINI/Geodesic legacy elevation:** Preserve selectively reconstructing `unfold_partial` independent of full unfold, folded representation and invertibility/error contracts, geodesic scheduling metrics, memory hierarchy, topological integrity, data-motion accounting and transparent resource budgets. Historical claims such as automatic 11.5× compression, ideal geodesics or GPU performance are targets or narrow observations until real-payload, matched-baseline evidence supports them. Representation compression is never inferred from a symbolic dimension ratio alone. Do not assume the 2026 reference GPU database means the device ran.

**Execution and orchestration:** Concrete typed Tensor request→router→Kellogg validated operation→CHRONUS CPU or explicitly chosen GPU/Metal/OpenCL/CUDA backend→independent verification→OVID optional transformation→THESEUS durable receipt/recovery, under AL HARAS admission. Verify outputs and receipt match actual run. Cover Turing consumer contracts for state semantics and PYTHIA mining advisory only; a tensor TFLOPS measurement must never convert into SHA256d H/s or a pool/share claim.

**Custody/provenance:** Stable tenant/run/object ID, input/output hash, schema/version, dtype/shape, backend/device, precision/error, environment, attempts/epochs, producer, replay command, evidence digest and required durable THESEUS verification; corruption or mismatched semantics after restore fails closed. Only OVID transforms representations; no unreviewed proprietary codec or pickle as a default interchange format.

## Minimum gates

- Cross-backend exact-vs-approximate differential, complex-phase preservation, TT/MPS/MPO known-answer and randomized property tests, contraction/evolution unit checks and tensor topology invariants.
- Real limited memory checks and cancellation, overflow, safe serialization, denials and faulty backend substitution tests, plus asymmetric and odd shapes, sparse/dense, edge dtype and tight residual budgets.
- Measure `op_count`, elapsed wall clock, setup, transfers, materialisation, effective TFLOPS (when appropriately defined), memory, accuracy and per-device identity. Preserve null when unavailable; no invented hashrate.
- PULVINI selective unfold negative test where full `unfold` is prohibited; roundtrip and repeated cycle error bounds, adversarial metadata corruption.
- Clean independent install of Kellogg + logical Tensor and optional Chronus backend from exact build artifact; no duplicate installed files or namespace takeover; fresh-process THESEUS replay.
- Validate old July test results as historical only. Rerun on current main and preserve failures, not update expected results to fit broken code.

## Deliverables

One scoped PR with canonical source/ABI/module map, feature-retention/compatibility evidence, exact math and backend regression suites, ownership-reconciled package manifest, measured production-dossier artifacts and `TENSOR_KELLOGG_CLOSURE_DOSSIER.md`. Return all unverified claims as MISSING/UNAVAILABLE/GATED. No removing features without proven replacements; no unapproved architectural or product renaming, merging, publication or production promotion. Independent reviewer tests all final installed artefacts.