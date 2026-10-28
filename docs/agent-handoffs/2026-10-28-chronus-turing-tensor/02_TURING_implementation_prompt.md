# Implementation assignment — TURING independent VQC consolidation and elevation

**Repository:** `HYBAAIENTERPRISE/HYBAEnterprise`; baseline inspected `main` SHA `c4ea01fd1b82d411db3fd394c96fc143579b08b5`. Resolve fresh HEAD and commit-bound audit before changes.

**Mission:** Preserve TURING as the independent HYBA Virtual Quantum Computer, consolidate duplicated or fragmented VQC implementations under one semantic authority, repair mathematical and execution-contract defects, integrate real CHRONUS execution where justified, and qualify exactness, measurement, representation, verification, THESEUS replay, OVID transformations and release artifacts. Do not demote TURING into a generic GPU adapter or grant it intelligence/mining/security/custody ownership. Do not confuse mathematical VQC verification with a physical quantum device.

## Canonical sources (read first)

- [TURING constitution](https://app.notion.com/p/3f0bcc6fa4998196a609f81164e73565)
- [Current authority register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19)
- [TURING Workflows 01–08](https://app.notion.com/p/3f0bcc6fa4998196a609f81164e73565) (children)
- [THESEUS manual](https://app.notion.com/p/3f0bcc6fa4998106bbd3f0438cfa393e)
- [14 Oct forensic audit, pinned historical commit 6688e83](https://app.notion.com/p/08d6c582eb1d44d58265a24e4b4301c8)
- [TURING source qualification](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/blob/main/turing_universal_quantum_computer/TURING-qualification.md)

## Baseline/lineage inventory

Enumerate all VQC implementations/imports across `turing_universal_quantum_computer/`, `turing_core.py`, `quantum/`, possible exact VQC and historical packages, `kellogg/` and consumer adapters. Identify canonical public API, support matrix, circuits, statevector, tableau/stabilizer, exact MPS/tensor network, symbolic/field, Hamiltonian, QFT, QAOA/VQE, measurement and checkpoint semantics. Preserve independently demonstrated features, with no duplicate source ownership. The canonical release states `hyba-turing-vqc` 1.0.0 and depends on `hyba-kellogg-tensor` for exact mathematics, while source qualification still records an installed-EUCLID acceptance HOLD. Reconcile any `Production/Stable` classifier with actual owner-approved qualification, not aspirational text.

## Mandatory forensic re-test before fixes

The October Notion audit documented 14 findings F01–F14 at an **older** repository/commit; these are test hypotheses, not proof current main fails. Reproduce each against current exact-head code, mark FIXED / STILL_FAILING / NOT_APPLICABLE / NOT_TESTED with exact evidence, and repair only confirmed defects. Specific mandatory negative controls:

1. Norm-preserving post-measurement collapse for |+⟩ and superpositions: exact normalisation or explicit fail-closed unsupported domain; never hide a defect via post-hoc probability renormalisation.
2. Von Neumann/reduced-state entanglement truth: distinguish Shannon Z-basis entropy from quantum entropy; CZ|++⟩ must not be certified separable based on computational basis probabilities alone.
3. Reject invalid/duplicate QFT qubits, nonintegral graph indices, repeated Pauli factors and unsupported operator domains before mutation.
4. Typed output contract shared between public pipeline and each backend; requested measurement/expectation/entanglement cannot disappear while execution is marked PASS. Mandatory independent differential GATED/ERROR/MISSING cannot turn into whole-run PASS.
5. Readout selection, qubit/resource accounting and tableau bit-size must reflect execution truth, with no silent truncation or fabricated RAM use.
6. Tableau, statevector, MPS and exact symbolic recovery must verify semantic state in addition to byte digests; restarted process must produce same declared measurements/results.
7. OVID transforms must be on an explicit versioned validated request path if claimed, not a decorative adapter; CHRONUS must perform real workload dispatch when claimed, not merely backend probing.
8. Physical-QPU refusal and attestation must fail closed; adapters cannot claim hardware root merely by self-declaration. Verify representation dominance map rather than universal supremacy claims.

## Preserve/elevate computational design

TURING owns circuit and state semantics, gate sets, measurement, expectation, exactness domains and tolerance budget; the representation planner must separate statevector, stabilizer, MPS/tensor-network, algebraic and transformed checkpoint forms by **width × depth × circuit class × non-Clifford content × entanglement × memory × precision × backend**. Verify deterministic and probabilistic measurement correctly. Test exact Clifford+T and the specifically supported 10,000-qubit bounded-entanglement GHZ/T/S journey under exact MPS with THESEUS custody/replay; never imply arbitrary dense 2^10000 amplitudes are materialized or all 10,000-qubit circuits are tractable. Preserve known-answer Bell/GHZ, QFT, Hamiltonians and admitted algorithms with independent oracles and negative domains.

## Govern integrations

- **Kellogg:** exact fields, MPS/MPO/TT mathematics and certificates, consumed through a documented dependency/adapter contract; no duplicate mathematical source files.
- **CHRONUS:** optional, versioned, actual execution/acceleration backend. Compare against TURING reference and preserve circuit/measurement semantics; CPU/GPU device identity, timing, cancellation, memory and resource evidence are separately bound.
- **OVID:** typed transformations/fold/materialisation with explicit inverse/residual/error and semantic equivalence checks. Not durable custody owner.
- **THESEUS:** versioned circuit/state/checkpoint/result/evidence objects and fresh-process verified recovery, replica/journal/rollback where supported. It preserves VQC records without determining their semantics.
- **AL HARAS:** admission/policy/authorization and claim gates, fail closed in production.
- **PYTHIA:** can request TURING workloads but retains mining strategy and pool truth; do not give TURING nonce acceptance authority.

## Release/evidence gates

Produce the ten-step Workflow 01 algorithm admission ledger, Workflow 02 representation dominance map, Workflow 03 CHRONUS backend differential certificate, Workflow 04 OVID round-trip proof, Workflow 05 THESEUS checkpoint/replay certificate, Workflow 06 precise scientific-claim packet, Workflow 07 clean build/SBOM/provenance/rollback record and Workflow 08 owner-controlled release/incident record.

Run clean wheel/sdist installation and executable exact-head tests in supported Python/OS matrices; independent mathematical oracles, property/adversarial testing, integration tests, cancellation/timeout/resource bounds, corruption/restart and signed evidence; distinguish local validation from CI and physical-QPU measurements. A failure, unsupported domain or missing mandatory evidence must fail closed. No quantum advantage, physical-QPU success, hardware speedup, general 10,000-qubit tractability or production release unless separately proven.

## Deliverables

A single bounded TURING PR (or separately reviewable defects if necessary), source and dependency ownership manifest, F01–F14 current-head re-test ledger, mathematical counterexample regressions, typed representation/backend/custody contracts, build/replay artifacts, publication gate and `TURING_CLOSURE_DOSSIER.md`. No merger into CHRONUS, no functionality removed without validated replacement, no owner-controlled Notion edits, no unapproved publication/tag/merge. Independent QC will certify or reject evidence; final promotion belongs to owner.