# AGENT D CLOSURE RECORD — TURING / MATHEMATICAL & QUANTUM SOFTWARE SUBSTRATE

```
AGENT: D (TURING / MATHEMATICAL & QUANTUM SOFTWARE SUBSTRATE)
BRANCH: repair/D-turing-math
BASE SHA: 306001b0e75862585a3338e9d549726e52773b52
FINAL SHA: HEAD of repair/D-turing-math (the commit containing this record;
self-referential by construction — verify with `git rev-parse HEAD`)

OWNED FILE COUNT: 428 tracked files
  (turing_universal_quantum_computer/, quantum_compute_substrate/, kellogg/,
   aethel/, lucas/, tensor/, proofs/, cross_verification/, format/, standard/,
   turing_core.py, STRICT_QUANTUM_BOUNDARY.md)
FILES INSPECTED: 428 — every owned file swept for stub/mock/synthetic/claim
  patterns; all boundary-critical modules read in full (kellogg attest/scales/
  quantum_tensor, turing custody/pipeline/backends/SPEC, QCS grover/deployment/
  gpu_advances/implications/scaling_study, format/, cross_verification/,
  standard/check_invariants, STRICT_QUANTUM_BOUNDARY.md)
FILES MODIFIED: 7
  quantum_compute_substrate/scaling_study/beyond_phi37.py   (measurement fix)
  quantum_compute_substrate/gpu_advances_2026.py            (docstring fix)
  quantum_compute_substrate/benchmark.py                    (print label fix)
  quantum_compute_substrate/deployment.py                   (label fix)
  quantum_compute_substrate/implications.py                 (claims rewrite)
  quantum_compute_substrate/README.md                       (5 label fixes)
  turing_universal_quantum_computer/tests/test_lucas_vendor_parity.py (NEW)

DEFECTS FOUND: 7 in-lane + 4 cross-lane
DEFECTS FIXED: 7 in-lane
  1. scaling_study/beyond_phi37.py — diffusion_scaling measured wall-clock
     of a 3-iteration burst (microseconds at dim<=512); timer/scheduling noise
     exceeded signal, making exponent_time a random variable and
     test_diffusion_scaling_produces_positive_exponents flaky (observed
     exponent -0.11, r^2~0.13). Fixed by min-of-7-rounds repeated-application
     timing (>=16 reps, scaled to dim): measured wall-clock, now deterministic.
     Post-fix: exponent +0.073, r^2=0.77, 5/5 repeated runs pass.
  2. quantum_compute_substrate/README.md — Grover "10.7x measured speedup"
     and "99.99% probability" listed under "Measured Performance"/"Real
     Measured Benchmarks"; speedup_ratio = (N/2)/iterations is a computed
     iteration-count ratio, not a measurement. Relabelled (3 spots) plus
     test-count line now distinguishes measured vs computed/theoretical.
  3. gpu_advances_2026.py::FP4Precision.throughput_multiplier — docstring
     claimed "2x vs FP8, 4x vs FP16" while returning 200.0. 200 is the spec
     target ratio 500 EFLOPS(FP4)/2.5 EFLOPS(FP64). Docstring now says so.
  4. deployment.py — validation["Grover_Search"]["measured"] reported the
     computed iteration ratio as measured. Key renamed to
     computed_iteration_ratio. (Honest "TARGETS NOT MET" verdict unchanged.)
  5. benchmark.py — printed "Throughput multiplier: 200x FP64" as a result;
     now "Target throughput ratio (spec)".
  6. implications.py — external-facing manifest (grant apps/investor decks)
     contained unsupported-advantage copy: "Exponential Compression",
     "New Complexity Class", "Quantum Speedup Today", "Quantum advantages
     without $10M+", "Quantum advantages in weeks", "Quantum advantages
     available to all computing workloads", phi-fold "turns quantum's
     exponential memory requirement into a manageable compression problem".
     All rewritten to state mathematical capability, scope to the
     phi-structured state family, and declare no measured quantum speedup.
     Claims-discipline preamble added to module docstring.
  7. No drift guard between vendored
     turing_universal_quantum_computer/lucas/ and canonical lucas/ — a silent
     fork of the exact-algebra substrate would pass every gate. Added
     test_lucas_vendor_parity.py: byte-identity on all 7 shared modules,
     file-manifest lock, cassini.py vs legacy source check, import sweep.

FALSE POSITIVES (audited, correct as-is):
  - fail-closed NotImplementedError in exact_state_vector.py:314,
    hilbert.py:1054 (eigenspectrum not exactly solvable),
    annealing.py (non-Hermitian Hamiltonians), cathedral/bell.py (odd-n
    Mermin), cathedral/pauli.py — deliberate refusal, not stubs.
  - kellogg/exact_tensor.py::NotInF4 — domain exception subclassing
    NotImplementedError by design.
  - aethel isinstance(exc, NotImplementedError) fallback handlers — honest
    degrade on unsupported backend ops.
  - "XXX" matches — literal Pauli X^3 strings in Mermin/Heisenberg code.
  - turing_core/discovery.py + millennium "quantum supremacy domains" —
    names a research mapping domain, not an achieved-supremacy claim.
  - product_registry.py "10 EH/s formal-capacity certificates" — the
    SPEC-sanctioned formal-capacity label (SPEC.md:113), not a throughput
    claim; TURING README correctly attributes the certificate to Mining.
  - kellogg/quantum_tensor.py — already declares finite-precision IEEE-754,
    "must not be described as exact symbolic". Correct.
  - trotter_simulation.py — self-declared textbook approximate method.
    Correct.
  - deployment.py target table — "Architecture targets are projections,
    not achieved performance"; reports TARGETS NOT MET honestly.
  - STRICT_QUANTUM_BOUNDARY.md — boundary doc already enforces
    theory/reference vs measured distinctions; no defect, unchanged.

VALID TEST/RESEARCH SCAFFOLD:
  - turing_universal_quantum_computer/exact-vqc/ — TS snapshot "for review",
    honestly labelled (theorem_proven=False), kept as research artifact.
  - proofs/ — Lean kernels; formal verification is opt-in per SPEC.

EXTERNAL BLOCKERS:
  - exact-vqc TS tests require node>=22.6 (--experimental-strip-types);
    VM has node v20.19.0. Not runnable here. (handoff D-005)
  - proofs/ Lean kernels require a Lean/lake toolchain; absent on VM.
    BLOCKED_EXTERNAL_EVIDENCE. (handoff D-005)
  - kellogg-tensor wheel build blocked by packaging/kellogg-tensor
    pyproject license classifier (setuptools>=77). Worked around locally;
    fix handed to G. (handoff D-004)

STUBS/TODOS CLASSIFIED: 8 in-lane hits — all fail-closed by design (see
  FALSE POSITIVES). 0 unfixed stubs.
MOCKS/FAKES CLASSIFIED: 0 production mocks in lane (mock/fake sweep clean;
  aethel enterprise placeholder-key path is fail-closed, ownership=E).
SYNTHETIC REFERENCES CLASSIFIED: simulation/emulation labels verified honest
  throughout (grover_search docstring "SIMULATE", kellogg "finite-precision",
  QCS README "Classical emulation, not physical quantum hardware").
APPROXIMATIONS CLASSIFIED: matrix_exp_unitary (scaling-and-squaring Taylor,
  labelled finite-precision), phi-fold compression (labelled approximate,
  target-family scope), Trotter (declared approximate). All correctly
  labelled; none presented as exact.

TESTS ADDED: 1 file / 4 tests (test_lucas_vendor_parity.py)
NEGATIVE TESTS ADDED: 1 — vendored-parity guard fails on any byte drift of
  shared exact-algebra modules (mutation-sensitive by construction).
  Existing negative coverage verified working: attestation tamper checks,
  quantum_device_absent fail-closed, backend boundary refusal.
MUTATION TESTS SUPPORTED: byte-parity guard detects any mutation of vendored
  lucas vs canonical lucas; kellogg attestation tamper suite detects envelope
  mutation. Lane participates in repo mutation floors per CI culture.

TEST COMMANDS:
  python -m pytest turing_universal_quantum_computer/tests -q
  python -m pytest quantum_compute_substrate/tests -q
  python -m pytest tests/<aethel,lucas,kellogg,tensor,cross_verification
    related files> -q
  python turing_core.py
  python -m aethel selftest
  python -m standard.check_invariants
  python scripts/verify_pure_quantum_math.py --output
    artifacts/pure-quantum-math/reproduction.json
RESULTS:
  - turing_universal_quantum_computer tests: 258 passed, 0 failed
  - quantum_compute_substrate tests: 1487 passed, 0 failed (post-fix; the
    pre-fix run had 1 flaky failure = defect #1)
  - combined lane suite re-run post-fix: 1750 passed, 0 failed
  - root tests touching lane (aethel/lucas/kellogg/tensor/etc.): 837 passed;
    1 failure = foreign test bug (handoff D-002); 6 failures = euclid
    SyntaxError cascade (handoff D-001); 1 failure = docs claims-gate trip
    (handoff D-003)
  - turing_core self-verification: PASS
  - aethel selftest: PASS (8/8)
  - standard.check_invariants: PASS (56 verdicts)
  - verify_pure_quantum_math.py: PASS — surface code d=31 (n=1861,
    930 stars + 930 plaquettes, k=1), Clifford unitarity exact over
    Q(zeta_8), replay identical digests; evidence at
    artifacts/pure-quantum-math/reproduction.json

CROSS-LANE HANDOFFS: 5 (reports/AGENT_HANDOFFS.json)
  D-001 -> A (blocking): euclid/__init__.py:48 SyntaxError breaks `import
    euclid`; cascades into aethel/enterprise/production_organism and 6+
    tests.
  D-002 -> H: tests/test_kellogg_production_evidence_boundary.py corrupts
    `zeckendorf` (int) via list()+[1] — stale test vs v2 envelope; one-line
    fix supplied.
  D-003 -> H: docs/FAULT_TOLERANT_QUANTUM_ASIC.md literal "10 EH/s" inside a
    disclaimer trips the prohibited-claims gate.
  D-004 -> G (blocking): packaging/kellogg-tensor/pyproject.toml license
    classifier + PEP 639 expression conflict breaks wheel install under
    setuptools>=77.
  D-005 -> H (toolchain): exact-vqc needs node>=22.6; proofs/ needs
    Lean/lake.

UNRESOLVED DEFECTS: none inside lane. Foreign-lane blockers D-001 (euclid
  syntax) and D-004 (kellogg-tensor packaging) gate the integrated voyage
  and fresh-clone install respectively; both have precise fixes recorded.

PRODUCTION-READY: YES — for the lane's own contract surface, with evidence:
  every owned file classified, all in-lane defects fixed, 1750 lane tests
  green, exact-math reproduction artifacts byte-stable, custody/attestation
  fail-closed paths verified, claims relabelled to measured-vs-computed
  discipline. Caveats are external: euclid (A) and kellogg-tensor packaging
  (G) must land before the integrated voyage and clean-clone install pass;
  exact-vqc/Lean evidence awaits toolchain provisioning (H).
```
