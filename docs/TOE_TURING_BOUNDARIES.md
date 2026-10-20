# TOE / TURING boundaries and admission language

This note records the reviewed ownership and evidence boundaries as they should be described in code, tests, and user-facing reports. It is not a claim that the repository proves a physical Theory of Everything.

## TOE's HR-shaped schema is a fixture, not its domain

`toe/bridge.py` contains an HR-shaped legacy demonstration schema. Its vocabulary is a compatibility fixture for the quantum-state and causal examples, not the canonical TOE input model. New application areas should use explicit sector adapters that translate their source data into the domain-neutral `toe.problem.Problem` contract.

`Problem.domain` records provenance and scopes learning namespaces; the reasoning path must not branch on it. Adapters map data and declared structure into the contract. The adapter boundary does **not** grant TOE operational authority: mining validity remains with PYTHIA's SHA-256d/target predicate, and any adapter for that context must not carry credentials or manufacture share-acceptance decisions.

## Evidence and admission vocabulary

Use one compact report vocabulary across TOE and TURING, while preserving each component's authority:

| Question | TOE evidence | TURING-facing language |
| --- | --- | --- |
| What structure is present? | `structural_signature` records measured fields and supplied structure. | State the representation and execution class the backend admits. |
| Which analyses may run? | `select_views` returns selected and rejected lenses with reasons. | Say **admitted**, **refused**, or **unsupported**, with the reason, before execution. |
| Is a causal effect available? | Run identifiability before estimation; `NOT_IDENTIFIED` returns without an estimate. | Preserve the refusal; do not convert missing identification into a score. |
| What uncertainty remains? | Keep aleatoric, model, structural, identifiability, and missing-evidence axes distinct. | Do not collapse those axes into one confidence value. |
| What supports the claim? | Name evidence class and assumptions; distinguish measured, propagated, and assumption-bound results. | Name the exact representation, resource limits, and certificate/evidence class. |

`select_views` currently makes structural admissibility decisions and explains rejections; it does not expose a numeric execution-cost model. Do not describe its result as cost-optimal or as a runtime budget guarantee.

## Exact quantum and finite-spectrum claims

- `toe/strict_quantum.py` emits exact Q(i) work-window certificates. A certificate is not a substitute for SHA-256d and has no consensus authority.
- `toe/solovay_kitaev.py` reports a bounded single-qubit Clifford+T synthesis frontier. Its report is feasibility evidence, not a general U(32) synthesis claim or a production decision input.
- `toe/poincare_yangmills.py` labels the computed binary-icosahedral result `finite_volume_spectrum`; `proof_claim` and `continuum_claim` remain false. The finite value is not the continuum Yang–Mills mass gap.
- The shared foundation sources, `toe/foundation.py` and `turing_universal_quantum_computer/turing_universal_quantum_computer/unified_theory.py`, are byte-identical at the reviewed base revision. The quantum-math workflow now checks this invariant so governance wording cannot drift silently.

## Ownership and remaining migration

TOE selects views, reasons over declared problem structure, plans advisory actions, and records evidence. TURING owns the quantum execution/admission boundary and exact certificates. Kellogg owns the shared exact tensor/field substrate. The relevant domain predicate remains the only validity authority. The foundation contract may be shared; orchestration modules should not be moved into TURING.

One repository-level ownership item remains a separate migration: root `turing_core.py` still loads `pythia_turing_math.py` from `chronus/mla1517_platform/python`. Reversing that dependency safely requires preserving the legacy import surface and testing clean installs of both the monorepo and TURING distribution. This patch does not silently change that public loader; track the canonical-source move separately from these evidence-gate/documentation changes.
