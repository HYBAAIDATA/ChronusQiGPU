# TURING_VQC_CALLER_CONTRACT.md

## Purpose

This is the caller contract for `turing_universal_quantum_computer` (the Turing
Virtual Quantum Computer, "the VQC"). It states what a caller may ask for, what
they receive, what they may repeat externally, and what is refused.

The contract exists because the VQC is an exact-algebra substrate on classical
hardware, and the failure mode that matters is not a wrong amplitude — it is a
**true amplitude attached to an untrue claim**. Everything below is therefore
written in terms of claim strength, not just return values.

Scope: the `backends`, `capabilities`, `certificates` and `console` modules, and
the exact engines they dispatch to (`stabilizer`, `hilbert`, `quantum_walk`,
`annealing`, `turing_core.ten_thousand`). Mining consensus is explicitly out of
scope; see `STRICT_QUANTUM_BOUNDARY.md`.

## 1. Layers and who may call what

| Layer | Entry point | Who calls it |
| --- | --- | --- |
| Capability | `capabilities.capability_report()` | operators, docs, CI claim audit |
| Selection | `backends.select_backend(program)` | any caller that must know *why* a program ran where it did |
| Execution | `backends.execute(program, **options)` | application code |
| Console | `console.QuantumConsole` / `turing-vqc` | operators, demos, support |
| Certification | `certificates.issue_witness(...)` | any caller that must attach evidence to a result |
| Hardware | `backends.QPUBackend` | only when a provider adapter is registered |

Callers must not import engine modules directly to bypass admission. The
registry is the only supported entry point, because it is the only place that
applies the domain checks.

## 2. What a caller receives

Every execution returns an `ExecutionResult` carrying:

- `backend` — which engine answered;
- `execution_class` — how the answer was produced (`exact_algebraic`,
  `exact_symbolic`, `bounded_exact`, `approximate`, `hardware`);
- `truth_class` — what the caller may believe (`exact`, `approximate`,
  `refused`, `unexecuted`);
- `materialised` — whether a dense state vector exists for this result;
- `program_digest` — SHA-256 over the canonical program;
- `measured_qpu` — true **only** for a completed provider job;
- `payload` — backend-specific exact values.

Exact representation examples (admission remains backend-specific):

- **dense_algebraic** — universal Clifford+T with amplitudes in
  `Q(sqrt(2)) + i*Q(sqrt(2))`. Bounded by `max_amplitudes`; exposes the full
  amplitude list.
- **tableau** — the Clifford state as its stabilizer tableau, `O(n^2)` tableau bits, exact
  at any width including `n = 10_000`. Gates, shot sampling, measurement
  distributions, marginals, expectation values and entanglement are all
  available. It has no amplitude list, and neither does hardware.

- **mps_exact** — canonical Clifford+T execution over `Q(zeta_8)` when the
  static Schmidt bound stays within `chi_max` at every cut. The representation
  planner and registry bind this backend; it is not currently a typed-facade
  target. Source presence is not independent release qualification.

`materialised = False` is **not** a degraded mode. It is the correct
representation for that state class.

## 3. Refusal semantics

Refusal is a supported outcome, not an error path.

- A program outside every backend's exact domain is refused with the reason
  from the nearest backend. `execute` raises `StatevectorTooLargeError`
  (a `MemoryError` subclass).
- A non-Clifford gate outside the dense materialisation budget requires another
  admitted exact representation. The canonical registry includes `mps_exact`
  under its static Schmidt bound; tableau alone does not admit non-Clifford
  gates. If no exact backend admits, the program is refused, never truncated
  or answered by a hidden dense fallback. The typed facade has narrower bindings.
- `max_amplitudes` is enforced at construction and at admission. There is no
  path that silently reduces precision.

Callers **must** surface the refusal reason. Collapsing a refusal into a
generic error destroys the contract's only useful signal.

## 4. Sampling and readout

- `shots` samples the exact Born distribution. The distribution is exact; the
  draw is a labelled classical sampling of it.
- A fixed `seed` supports replay within the qualified environment. Cross-version
  or cross-platform bitstream identity requires retained evidence, not assumption.
- `readout=[...]` selects which qubits are wired to detectors, as on a device.
  Bitstring keys follow the order of `readout`.
- Reading out more than `StabilizerBackend.READOUT_LIMIT` qubits is refused:
  sequential collapse is `O(n)` per qubit, so an unbounded readout is `O(n^2)`
  per shot. This is a cost bound, not a correctness bound.
- `marginal_of=[...]` returns the exact marginal. A stabilizer marginal is
  uniform over an affine subspace, so it is reported by its exact dimension;
  small subspaces are enumerated, large ones are described rather than
  truncated.

## 5. The witness contract

`certificates.issue_witness(program, result)` produces a `RunWitness`.
`verify_witness` is fail-closed and rejects:

- `theorem_proven = True` — this package proves no theorems;
- `consensus_authority = True` — SHA-256d target comparison remains the sole
  accept authority;
- `measured_qpu = True` on a non-hardware backend, or without a provider job id;
- a hardware backend with `measured_qpu = False`;
- an exact backend reporting `truth_class = approximate`, or an approximate
  backend reporting `truth_class = exact`;
- a symbolic backend claiming a materialised state;
- unknown fields.

A caller may attach a witness to a result, diff it against a re-run, or hand it
to a reviewer. A caller may **not** attach hardware evidence to a simulated run;
`issue_witness` refuses that at issue time.

## 6. The hardware boundary

`QPUBackend` is the only hardware backend, and this package ships no provider
adapter.

- `available()` returns `(False, reason)` until a provider is registered *and*
  configured.
- `execute()` raises `QPUUnavailableError`. It never returns a simulated,
  cached, or fabricated result in place of a job.
- `assert_measured_qpu(result, job)` is the **only** sanctioned path to a
  `measured_qpu` claim. It requires a `QPUJob` carrying a provider name, job id,
  completion timestamp, and result digest, and it checks that the record matches
  the result.
- The QPU backend is never selected automatically.

Consequence: an exact classical result cannot reach a hardware claim through
this package.

## 7. The claim boundary

Callers may repeat, without further qualification:

- the register width is a parameter of the algebra, not a hardware ceiling;
- the shipped backends are exact for the state classes they declare;
- wide registers are exact because they use an efficient state class.

Callers must **not** state, and `capabilities.audit_claims()` will flag:

- unqualified universal computation at 10,000 qubits;
- a physical quantum computer or a measured hardware run;
- a hardware speedup;
- cryptanalytic capability;
- theorem proofs or consensus authority.

`capability_report()["claim_boundary_clean"]` is asserted in CI. A wording
regression is a test failure, not a documentation nit.

## 8. Versioning

- The witness schema string is `turing.vqc.run_witness.v1`; the capability
  report schema is `turing.vqc.capability_report.v1`. A schema change is a
  breaking change.
- `Program.digest()` is stable across releases; a witness issued today must
  still match the same program tomorrow.
- Adding a backend is additive. Changing a backend's `execution_class`,
  `max_qubits`, or `truth_class` behaviour is a contract change and must be
  recorded here.
