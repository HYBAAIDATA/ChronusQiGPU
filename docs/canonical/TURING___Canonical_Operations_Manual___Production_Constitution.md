# TURING — Canonical Operations Manual & Production Constitution

<aside>

**CANONICAL / OWNER-CONTROLLED.** This is the governing operational manual for Turing, the HYBA Virtual Quantum Computer. It must be consulted before any material Turing architecture, execution model, representation, algorithm, backend, benchmark, claim, package, release, deployment, evidence, security, or production-readiness change. No person or agent may modify, supersede, reinterpret, or promote a conflicting record without explicit approval from Andre Taylor-Morris.

</aside>

## 1. Canonical identity

Turing is the independent HYBA Virtual Quantum Computer. It is a computer in its own right, not an intelligence authority, not a mining composition root, and not merely a generic Chronus accelerator backend.

Turing owns the semantics and contracts of its VQC execution model: state representation, circuit/operation semantics, measurement, expectation, Hamiltonian evolution, exactness/tolerance boundaries, representation selection, verification, checkpoint/replay semantics, and evidence describing what kind of quantum computation was actually performed.

## 2. Turing may use the enterprise triad

Turing is explicitly permitted to consume the services of **OVID, THESEUS, and CHRONUS** without transferring Turing's semantic authority to them.

### OVID → representation / transformation service

Turing may use OVID for:

- reversible fold/materialise operations;
- representation transformations;
- state preparation and regeneration transforms;
- algebraic encoding/decoding where independently verified;
- PULVINI-related transformation paths where the authority boundary permits;
- reversible checkpoint representation changes.

OVID does not redefine quantum/VQC semantics. A transformed Turing state must preserve the declared Turing contract and verification invariants.

### THESEUS → durable custody / continuity service

Turing may use THESEUS for:

- durable VQC checkpoints;
- circuit/program/state custody;
- replica management;
- journals and lineage;
- restart continuity;
- recovery and replay;
- content-addressed evidence and provenance;
- quotas and durable execution records.

THESEUS does not decide quantum semantics, algorithmic correctness, or representation validity. It preserves and recovers the state Turing declares valid.

### CHRONUS → execution / acceleration service

Turing may use Chronus for:

- CPU/iGPU/GPU/remote accelerator execution;
- heterogeneous backend routing;
- tensor/statevector/stabilizer kernel acceleration;
- memory and device placement;
- physical-device evidence and execution receipts;
- future FPGA/ASIC/HYBA silicon execution.

Chronus does not redefine Turing's circuit semantics, measurement model, or VQC truth. It executes a Turing-declared workload under a verified backend contract.

## 3. Shared THESEUS record plane

Turing uses the same THESEUS custody/provenance service as other HYBA organs. Turing VQC records must therefore remain interoperable with the common operational-record contract while retaining Turing-specific semantics and validation.

A Turing durable record may include circuit/program identity, representation class, logical-qubit count, depth/circuit class, exactness/tolerance, OVID transform lineage, Chronus backend/device identity, measurement/verification result, checkpoint/replay state and evidence status.

THESEUS custody never turns a Turing record into a generic storage fact: Turing remains the semantic validator of VQC state and result correctness.

See [THESEUS — Canonical Custody, Operational Records & Continuity Service](https://app.notion.com/p/THESEUS-Canonical-Custody-Operational-Records-Continuity-Service-3f0bcc6fa4998106bbd3f0438cfa393e?pvs=21).

## 4. Canonical composition

`Turing request → capability/representation analysis → contract validation → optional OVID transformation → admission → backend planning → Chronus execution where applicable → Turing verification/measurement → THESEUS custody/checkpoint/evidence → result → replay/recovery`

Geodesic may also be consumed for search/indexing/search-space transformation where explicitly contracted; it remains outside custody and does not become Turing's semantic authority.

## 5. Owner approval required

Explicit owner approval is mandatory before changes to:

- Turing identity, scope, architecture, composition root, or authority;
- the Turing↔OVID, Turing↔THESEUS, or Turing↔Chronus contracts;
- state model, gate/operation semantics, measurement semantics, exactness definition, or representation authority;
- production-ready status or supported production workload classes;
- any claim of quantum advantage, QPU execution, universal scale, logical-qubit capacity, compression, speedup, or hardware superiority;
- benchmark methodology or reference baselines;
- supported physical backend classes for production;
- release/provenance/signing policy;
- security or custody requirements;
- this manual or any owner-controlled Turing document.

## 6. Execution truth taxonomy

Every result must distinguish:

- mathematical quantum formalism;
- classical exact/reference computation;
- classical quantum simulation;
- Turing VQC execution;
- quantum-inspired method;
- hardware-accelerated classical/VQC execution;
- physical quantum/QPU execution.

These categories must never be collapsed. A quantum name, Grover-style formalism, logical-qubit count, or simulator output is not evidence of physical QPU execution.

## 7. Representation governance

Turing may support multiple representations including statevector, stabilizer, tensor-network/MPS, symbolic/algebraic, folded/checkpoint representations and future representations.

For every representation:

- declare valid circuit/state domain;
- declare exactness/approximation contract;
- verify conversion in/out;
- fail closed outside the supported domain;
- preserve provenance of conversions;
- benchmark crossover/dominance rather than assuming a universal winner.

Automatic representation selection becomes production authority only after its planner is itself tested against the representation-dominance map and cannot silently weaken semantics.

## 8. Evidence doctrine

- `MEASURED`, `UNAVAILABLE`, `MISSING`, `GATED`, `REFUTED` remain distinct.
- Software verification is not physical-QPU evidence.
- Logical qubits are always accompanied by representation, circuit class, depth, non-Clifford content, entanglement structure, backend and memory/runtime conditions.
- Performance comparisons preserve the same mathematical problem, precision/exactness, circuit semantics and output validation.
- Negative representation/algorithm results remain part of the evidence.

## 9. Production-readiness domains

Turing production readiness is assessed separately for:

- execution semantics and formal specification;
- representation correctness;
- compiler/planner correctness;
- backend conformance;
- Chronus hardware execution where used;
- OVID transformation correctness where used;
- THESEUS checkpoint/recovery/custody correctness where used;
- measurement/result verification;
- checkpoint/replay determinism;
- security/provenance;
- package/release reproducibility;
- operator/API/CLI surface.

## 10. Constitutional rule

If code, Notion, a PR description, an agent memory, benchmark narrative or historical Turing/Pythagoras record conflicts with this manual, the conflict is raised for owner review. Historical lineage is preserved, but it may not silently redefine current Turing authority.

[Turing Workflow 01 — VQC Capability & Algorithm Admission](Turing%20Workflow%2001%20%E2%80%94%20VQC%20Capability%20&%20Algorithm%20Ad%203f0bcc6fa49981db88bee50b81623cc1.md)

[Turing Workflow 02 — Representation Certification & Dominance Map](Turing%20Workflow%2002%20%E2%80%94%20Representation%20Certification%20%203f0bcc6fa49981599847f450154b9e35.md)

[Turing Workflow 03 — Chronus Backend Execution Certification](Turing%20Workflow%2003%20%E2%80%94%20Chronus%20Backend%20Execution%20Cer%203f0bcc6fa49981a186c0d5314bec7a6d.md)

[Turing Workflow 04 — OVID Transformation & Fold Contract](Turing%20Workflow%2004%20%E2%80%94%20OVID%20Transformation%20&%20Fold%20Co%203f0bcc6fa499812591aedb9a32251b30.md)

[Turing Workflow 05 — THESEUS Custody, Checkpoint, Recovery & Replay](Turing%20Workflow%2005%20%E2%80%94%20THESEUS%20Custody,%20Checkpoint,%20%203f0bcc6fa49981319a02e9fa2ad83ab1.md)

[Turing Workflow 06 — Benchmark, Scientific Claim & Quantum Claim Promotion](Turing%20Workflow%2006%20%E2%80%94%20Benchmark,%20Scientific%20Claim%20&%203f0bcc6fa49981e49888cde8e024729e.md)

[Turing Workflow 07 — Release, Package & Provenance](Turing%20Workflow%2007%20%E2%80%94%20Release,%20Package%20&%20Provenance%203f0bcc6fa4998101b0cbc8e8ba3a8a98.md)

[Turing Workflow 08 — Change Control, Incident & Owner Approval](Turing%20Workflow%2008%20%E2%80%94%20Change%20Control,%20Incident%20&%20Ow%203f0bcc6fa49981dfbe1cf48ec1fb120f.md)