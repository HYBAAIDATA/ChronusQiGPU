# Exact subregister elevation — scoped implementation review

Task: QS-REVIEW-20261013. Repository: PhiEnterprise1/EuclidPhiEnterprise, selected explicitly by the owner. Baseline main: `6688e83c22d36dc16dfd5516e9e7d81959c84438`. Feature branch: `fix/exact-subregister-contracts-20261013`. The final head SHA and draft PR are recorded in the PR handoff rather than embedded circularly in their own commit.

## Outcome and scope

This patch implements canonical exact-mathematics corrections in TURING's `hilbert.py`; it is not a repository-wide completion or release verdict. AGENTS.md, OWNER_DECLARATIONS.md and the entire UNIVERSAL_PRINCIPLE_MAP.md were read before code inspection. Earlier review reports were inspected as historical evidence, not substituted for present execution. Repository read and push permission were observed through GitHub MCP; this task uses only the selected repository's feature branch and draft PR. Broad connector privileges were not exercised.

Actual fixes:

- QFT and reduced density/entropy now reject duplicate, out-of-range, Boolean, fractional and text qubit positions before execution.
- QFT applies the exact Fourier coefficients directly to sparse amplitudes, without storing an M-by-M Fourier matrix. Output support and contraction terms are checked before action. State commits only after every contraction succeeds.
- Fourier-matrix and density-matrix construction have explicit positive-integer entry budgets; dense Born exports respect the register's amplitude budget.
- Fourier dimensions and directions are typed; QSqrt radicands must be positive exact integers. Equality collapses perfect-square radicands to the rational field, respecting hashing.
- Nonbinary Fourier coefficients and wider-QFT outputs use exact complex expansion, not numerical evaluation. No global zero-test simplification was changed.

No floating arithmetic or alternative simulation backend was introduced. SHA256d, protocol hashing, signatures, target comparisons and acceptance authority were not changed. No main push, merge, tag, package publication, deployment, mining, pool connection, invitation or external reviewer assignment occurred.

## Exact counterexamples at the pinned baseline

1. `qft(QuantumRegister(2, basis=1), (0,0))` returned support [0,1] with norm squared **1/2**. Repeating a tensor factor corrupted normalization.
2. With `(2,)` on the same 2-qubit register, QFT returned indices **[1,5]**; index 5 lies outside C^4.
3. A 2-qubit basis register with max_amplitudes=2 admitted a 2-qubit QFT yielding four amplitudes; the old QFT bypassed the support guard.
4. `QSqrt(0,1,2.9)` silently stored root=2. `QSqrt(0,1,4) == QSqrt(2,0,4)` was False although both values equal 2.
5. Empty/nonpositive Fourier dimensions and truthy inverse labels were not consistently refused. Dense Born/density exports had no effective preallocation entry envelope.

## Function contracts

Input states below are well-formed normalized QuantumRegister states; this patch does not make the public amplitudes dictionary immutable or comprehensively validate arbitrary external corruption. Position iterables are finite. TypeError denotes undeclared representations, ValueError invalid values/duplicates, IndexError positions outside the register, and MemoryError an exceeded materialization/work envelope.

| Function | Domain → codomain; representation/closure | Termination and resource envelope | Rejection/equality semantics |
| --- | --- | --- | --- |
| QSqrt constructor/equality | rational q,s; positive exact integer r → q+s√r in Q(√r) | Integer admission/isqrt and finite rational operations; coefficient-bit growth not separately capped | Floats/Booleans/text/fractional radicands and r≤0 refused. Nonsquare same-root values compare coefficients; square roots compare collapsed rational values. Existing cross-root SymPy exact expressions and hash rules retained. No ordering operator added. |
| _subregister_qubits | register + finite valid distinct positions → sorted tuple | O(k) validation/set + O(k log k) sort | Validate every position, then reject duplicates. Canonical sorted order preserves the prior bit convention; empty tuple is valid. |
| _matrix_budget | positive dimension and exact positive max_entries → None | Finite integer multiplication; no matrix allocated | MemoryError when d²>max_entries; invalid budgets refused. |
| _fourier_scale | prevalidated positive m → exact 1/√m | Finite scalar construction | For 1,2,4,8 use Q(ζ8); otherwise exact SymPy radical. Internal caller supplies the domain. |
| fourier_matrix | positive exact m, Boolean inverse, positive max_entries → exact m×m F or F† | m² coefficients; default max_entries=2^20, checked before allocation | Entries in Q(ζm,√m), with Q(ζ8) fast cases. Exact complex expansion supports exact zero proofs without floating tolerances. No arbitrary-phase closure in a fixed field is claimed. |
| qft | state in C^(2^n), subset, Boolean inverse, exact positive max_terms → same register with F acting on subset | M=2^k, S=input support, E=occupied environment sectors; M*S≤max_terms (default 2^20), M*E≤max_amplitudes. O(M*S) coefficient products, O(S+M*E) amplitude slots, plus symbolic arithmetic costs. Finite loops; one commit after all calculations. | Same valid Fourier action, no dense matrix. Algebraic extensions form the compositum with the input field. Conservative output admission may refuse a transform whose cancellations would shrink support. For M>8, exact SymPy complex expansion/simplification precedes zero pruning; mathematical equivalence is tested, not repr identity. |
| reduced_density_matrix | state + retained subset, positive max_entries → exact SymPy matrix Tr_env(|ψ⟩⟨ψ|) | d=2^k; d²≤max_entries (default 2^20); ≤S² outer-product terms and d² slots | Same subset validation; empty subsystem yields norm squared as a 1×1 matrix. Closure under multiplication/conjugation in the input field. Does not mutate the register. |
| von_neumann_entropy_exact (unchanged body) | validated reduced density matrix → exact symbolic entropy | Inherits the density entry budget; delegates exact eigenspectrum to SymPy; no eigensolver wall-time/degree guarantee | Existing NotImplementedError on incomplete spectrum retained. Log terms are exact symbolic expressions, not algebraic-field members or performance measurements. |
| QuantumRegister.distribution | normalized state + optional dense export → exact Born-weight mapping | Sparse: S entries. Dense: dim entries only if dim≤max_amplitudes | Dense budget refusal before allocation; probabilities remain exact, not deterministic selected Born outcomes. |

Entry/term budgets bound the enumerated work, not scalar bit sizes, total host bytes, symbolic simplifier/eigensolver wall time, or general undecidable symbolic equality. Those wider scalar/degree envelopes are an outstanding engineering gate. No asymptotic quantum speedup or measured performance improvement is inferred from lower matrix storage.

## Requirement/code/test matrix and five review responsibilities

These are review labels, not impersonations, independent agents, or institutional endorsements.

| Requirement / role | Code and actual trace | Executed evidence / gap |
| --- | --- | --- |
| Deutsch — exact operator semantics and composition | quantum_library.qpe → QuantumRegister → qft; same Fourier action and inverse | Independent Fourier definition for every basis at dimensions 2,4,8; dimension-16 exact inverse; noncontiguous environment-bit preservation; new QFT refuses before mutation. |
| Turing — representation, admission, termination | matrix-free qft; dense matrix/export preflight; positive exact budgets | Support/work/entry refusal tests, allocation guards, late contraction failure atomicity, compilation and optimization-safe refusal. Scalar bit/degree/time envelopes remain open. |
| Grover — oracle/amplification integrity | Existing GroverExact and protected oracle code unchanged | Existing exact-operator contracts execute in the focused suite; no new oracle cost model or mining advantage claim. |
| Shor — exact fields and arithmetic | QSqrt admission/equality; rational Fourier phases with declared field extensions | Square-field equality/hash regressions, nonbinary Fourier unitarity, dyadic and nondyadic QPE regressions. Full period-finding pipeline not newly qualified. |
| Schrödinger — unitary evolution and Born/partial trace | exact QFT contraction, density matrix, entropy and Born weights | Exact norms, inverse action, Bell reduced density/entropy and existing QAOA/VQE evaluations. Hardware/QPU execution and installed-artifact integration unavailable. |

Execution below the facade was inspected: QPE invokes the canonical register directly, not a backend-name label. Entropy delegates to the same density implementation. No persistent operator cache was added. The separate VQCPipeline source routes through registry admission and then certificate/witness verification, with optional THESEUS custody/replay and CHRONUS probing. It was inspected but not executed by this suite; this patch does not call that path integrated or certify installed artifacts, cache coherence or custody replay.

## Validation actually executed

Isolated environment: Python 3.13, SymPy 1.14.0, pytest 9.1.1, Black 26.10.1. Retrieved unmodified canonical hilbert, quantum_library, quantum_walk and stabilizer modules were placed in an isolated namespace package. No alternate operator implementation was used. The actual package __init__, full checkout, root/TUQC conftest, backend registry, installed wheel and certificate/custody integration were not loaded. Refusal tests use guarded allocation/failure injection; mathematical evolution tests use real operators.

- Final 60 new regression cases on pinned baseline: **35 failed, 25 passed**, exit 1.
- Final combined patched suite: **122 passed, 3 deselected**, exit 0 (60 new cases + 62 existing cases).
- Deselected (unavailable, NOT passes): test_lanes_report_live_backends, test_execute_ops_selects_exact_lane_for_clifford, test_execute_ops_refuses_unknown_gate.
- Nondyadic QPE was additionally run with a 30-second external bound on baseline and patch: **1 passed on each**, exits 0.
- Compileall, Black check of the new test file, changed-operator AST float-literal check and explicit python -O rejection checks: exits 0.

Exact commands, cwd, tool versions, source SHA256s and result summaries are retained in `docs/exact_subregister_local_validation.json`. A slower experimental global zero-normalization variant was discarded; its interrupted run is not acceptance evidence. The final implementation retains the existing global zero-test semantics and passes nondyadic QPE.

Repository-wide Python/TUQC/frontend suites, Flake8, whole-file/repository Black, import/deploy/drift gates, security review, CI, wheel/sdist installation, protocol compatibility, device benchmarking, provenance qualification and rollback remain **unexecuted/unavailable**, not passed. No service smoke test with a pool endpoint was run.

## Remaining exact counterexamples and prioritized backlog

These were reproduced against the retrieved actual facade, not inferred from a prior report:

| Priority | Gap / counterexample | Proposed blocker owner and next action |
| --- | --- | --- |
| P0 | vqe_evaluate(1, [], [(1, ((0,'x'),(0,'y')))]) returns energy **I**. Repeated-qubit XY is not a Hermitian observable; the Hamiltonian contract must reject or canonically reduce it with its phase. | Quantum-library maintainer, assignment pending with devops: implement typed Hermitian Pauli admission and exact real-energy checks before computation. |
| P1 | qaoa_maxcut([(0.9,1)], [(0,0)]) reports edges [(0,1)]. int coercion silently changes the supplied graph. | Quantum-library maintainer, assignment pending: exact endpoint domains, duplicate/oriented-edge policy and scan count/resource admission. |
| P1 | Stabilizer/walk inputs retain public int coercions; exactness audit accepts opaque leaves and only detects bare decimal text. Presence of a symbolic expression alone is not a completed exact execution contract. | Substrate/representation maintainer, assignment pending: targeted admission and serialization audit with executable regression cases. |
| P1 | Scalar bit size, cyclotomic degree, symbolic simplifier/entropy time and conservative Hadamard support admission need declared resource envelopes. | Exact-runtime maintainer, assignment pending: bound representations/work without numerical substitutes. |
| P1 | Full package initialization, backend/certificate/custody replay, installed artifact and whole-system evidence unavailable. | Owner-designated engineering/security reviewer (not yet assigned): execute retained gates at a fixed head/artifact. |
| P2 | H4, Wythoff, general algebraic-root operations and foundation PR status in the selected repository were not audited in this slice. | devops assigns the next bounded workstream; inspect current implementation, do not transfer old repository verdicts blindly. |

Human engineering/security review and release approval remain mandatory under PYTHIA delivery authority. Proposed blocker ownership is not evidence that an external researcher or reviewer has accepted an assignment. Next step: independent review of this draft patch, then implement the reproduced facade admission defects and execute the installed-backend qualification gates. This work self-issues neither independent review nor a production-ready verdict.

## Connector write limitation

The attempted five-file batch was rejected before execution because MCP request confirmation exceeds 65,536 bytes. The canonical map is 126,446 characters and cannot be replaced through this surface within that limit. Its proposed targeted append was NOT persisted. Code/tests and retained evidence are committed in bounded batches instead. Follow-up owner: repository maintainer — apply the source-bound canonical-map append through an approved patch-capable executor after reviewing this PR. No canonical-map update is claimed.
