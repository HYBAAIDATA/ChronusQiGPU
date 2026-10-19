# TURING — production VQC pipeline

The canonical TURING computation path is implemented by
`turing_universal_quantum_computer.pipeline.VQCPipeline`. The canonical
production integration is the shared Turing binding created from
`aethel.enterprise.lifecycle.CompositionRoot` through
`ProductionSystemRelations.turing()`.

```text
request
-> capability analysis
-> representation choice
-> contract validation
-> compile/plan
-> chronus lane
-> execution
-> measurement
-> verification
-> shared THESEUS/OVID custody
-> post-custody semantic replay
```

Production startup is fail-closed. `ProductionOrganism.start()` now executes a
real two-qubit TURING voyage through this shared path and will not become ready
unless execution, computation certificate, witness, shared custody, readback,
and semantic replay all pass. The startup gate records its evidence in
`ProductionOrganism.status()["turing_startup_gate"]`. It is a software VQC
gate and makes no hardware or physical-QPU claim.

`SharedTuring` suppresses the pipeline's historical private custody flags so
production has one durable-truth authority, not two. It commits
`program -> result -> certificate -> witness -> pipeline_report -> replay`
and refuses production acceptance when the recovered result cannot reproduce
the computation certificate or the recovered witness no longer binds the same
execution.

This is an executable engineering contract. TURING owns VQC semantics and
mathematics; CHRONUS owns authorised heterogeneous execution; OVID owns
representation transformation; THESEUS owns durable custody. No subsystem may
manufacture evidence for another.

## Stage contract

| Stage | What it proves | Honest states |
|---|---|---|
| `request_validation` | Request is unambiguous and parseable | PASS / FAIL / REFUSED |
| `capability_analysis` | Claim boundary audited before execution | PASS / FAIL |
| `representation_choice` | An exact/declared representation covers the program | PASS / REFUSED |
| `contract_validation` | Program structure and bounded exact unitarity checks | PASS / FAIL / GATED |
| `compile_plan` | A shipped backend admitted the program | PASS / REFUSED |
| `chronus_lane` | Truthful substrate availability; presence is not execution evidence | GATED / UNAVAILABLE / READY / FAIL |
| `execution` | Backend executed and returned a truth-classed result | PASS / FAIL |
| `measurement` | Measurement surface recorded | PASS / FAIL |
| `verification` | Witness plus available independent differential checks | PASS / FAIL / GATED |
| `custody` | Program/result/witness/certificate committed to THESEUS when requested | PASS / FAIL / UNAVAILABLE / SKIPPED |
| `replay` | Custody recovered; program/result/witness/certificate bindings revalidated as one bundle | PASS / FAIL / SKIPPED |

The table describes the composable pipeline stages. On the shared production
path, successful computation additionally requires the post-custody
`turing_replay` binding to be PASS before control returns to the caller.

Verdicts remain `PASS`, `GATED`, `REFUSED`, or `FAIL`. `GATED` is not promoted
to PASS by optimistic defaults.

## Mathematical execution domains

TURING does not equate logical width with a dense `2^n` state vector.
Representations are admitted by mathematics:

- `dense_algebraic` — exact Clifford+T over `Q(sqrt(2)) + i Q(sqrt(2))`
  inside the declared amplitude budget;
- `tableau` — exact Clifford stabilizer evolution in O(n^2) bits, including
  wide registers such as 10,000 qubits when the program remains Clifford;
- `sparse_exact` — exact bounded-support states where runtime support remains
  within the declared budget;
- `closed_form` — exact formulas for admitted families that do not require a
  materialised state vector;
- reserved/unimplemented representations resolve `UNAVAILABLE`; they are not
  silently substituted.

No float truncation, hidden dense fallback, or simulated hardware identity is
permitted to widen one representation's mathematical domain.

## Stabilizer measurement production gate

`StabilizerState.measure()` uses the Aaronson-Gottesman random-measurement
update. For a measured `Z_q` with anticommuting stabilizer pivot `S_k`:

1. clear every other tableau row that anticommutes with `Z_q` by multiplying
   it by `S_k`;
2. **exclude the paired destabilizer `D_k` from that clearing operation** —
   `D_k` anticommutes with `S_k`, so multiplying them would create a `+-i`
   Pauli product outside the real-phase tableau;
3. replace `D_k` with the old `S_k`;
4. replace `S_k` with `(-1)^outcome Z_q`.

The production differential suite uses an independent dense state-vector
reference with the same little-endian qubit convention, retains stabilizer
signs, checks exact measurement probabilities, forces both random outcomes,
checks symplectic tableau invariants, and continues Clifford evolution after
collapse. The former mathematical `xfail` is removed.

`tests/test_production_release_gate.py` fails the Turing release if any VQC
mathematics test is decorated with `xfail`.

## Execution-kind truthfulness

`taxonomy.ExecutionKind` distinguishes mathematical formalism, classical
reference, classical quantum simulation, TURING VQC execution,
quantum-inspired execution, hardware acceleration and physical QPU execution.

`PHYSICAL_QPU` is reachable only through `assert_measured_qpu` with a verified
completed provider job. It cannot be inferred from:

- the word quantum;
- a logical-qubit count;
- Grover terminology;
- a simulator result;
- accelerator presence;
- a GPU/OpenCL/CUDA/Metal device probe.

A hardware-class result without device-bound dispatch evidence remains
unverified hardware evidence.

## Enterprise transformation and custody

### OVID

`turing_universal_quantum_computer.transform` consumes OVID transformation and
requires digest-proven round-trip equivalence for exact transformations.
Mismatch is a refutation, not a degraded success.

### THESEUS

`turing_universal_quantum_computer.custody` and `aethel.enterprise` retain
program, result and witness evidence. Disaster-recovery replay now preserves
operational meaning:

- an `OperationalRecord` is read through `get_record()` and re-admitted through
  `put_record()`;
- producer identity, schema, evidence state, lineage, correlation IDs,
  dependencies and producer metadata therefore survive replay and are
  contract-validated again;
- plain byte custody objects remain plain byte objects;
- a destination unable to admit an operational contract fails rather than
  silently demoting it to anonymous bytes.

Final replay verification compares content digest and operational identity.
For TURING's shared production path it also replays the computation
certificate against the recovered canonical result and records that verdict as
the child `turing_replay` binding of the pipeline report.

## Verification surface

- exact gate/domain admission before execution;
- bounded exact `U†U = I` verification over the algebraic field;
- independent dense-vs-tableau differential tests at tractable widths;
- wide-register structural/invariant tests without densification;
- `RunWitness` issue + verification with overclaim rejection;
- exact differential cross-backend probes where a second backend admits;
- OVID round-trip verification;
- THESEUS integrity, tamper detection, recovery and semantic replay;
- claim-boundary tests preventing QPU/hardware self-assertion.

## Hardware evidence boundaries

These are not software defects and must not be faked closed:

- physical QPU: `UNAVAILABLE` until a real provider adapter and completed job
  evidence exist;
- CHRONUS VQC device kernel: `GATED`/`UNAVAILABLE` until a contracted kernel is
  bound and its dispatch is measured;
- GPU/iGPU/OpenCL/CUDA/Metal execution: evidence is device-bound and may only
  be claimed after an actual completed launch;
- the canonical exact MPS backend is implemented under a static Schmidt-bound
  admission contract (`representation.py`, `backends.mps`); this does not imply
  unrestricted MPS execution or completed release qualification. Other
  tensor-network paths require their own implemented and verified contracts.

TURING can be production-ready as an exact VQC without physical QPU hardware;
it simply cannot claim physical-QPU execution or hardware speedup without that
evidence.

## Required release commands

```bash
python -m pytest turing_universal_quantum_computer/tests/test_stabilizer_measurement.py -q
python -m pytest turing_universal_quantum_computer/tests/test_production_release_gate.py -q
python -m pytest tests/test_turing_production_pipeline.py -q
python -m pytest tests/test_hyba_prodrc_integration.py -q
python -m pytest tests/test_shared_system_relations_production.py -q
python -m pytest turing_universal_quantum_computer/tests -q
python scripts/import_audit.py
python scripts/import_graph.py cycles
python scripts/import_graph.py layers
```

A release is not production-evidenced until these execute on the exact release
commit. A GitHub Actions job with `runner_id=0` and `steps=[]` is infrastructure
unavailability, not passing or failing execution evidence.
