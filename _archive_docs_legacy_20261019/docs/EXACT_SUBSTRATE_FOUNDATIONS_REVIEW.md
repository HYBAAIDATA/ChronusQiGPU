# Exact substrate foundations — scoped implementation review

Baseline: `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.
This additive draft implements four foundation modules from the supplied nine-module
specification. It does not replace the existing backend or certify production readiness.
No simulators, quantum frameworks, approximate arithmetic, mocks, mining connections,
protocol hash changes, throughput claims or institutional endorsements were added.

## Implemented contracts and acceptance evidence

| Module | Exact contract | Independent check | Outstanding scope |
| --- | --- | --- | --- |
| `chronus/pisano.py` | F(n) mod m for n>=0, m>=1; positive period verification; minimal period from factored verified bounds | direct recurrence periods for m=1..500 and Fibonacci recurrence residues | trial division cost and million-entry table throughput not benchmarked |
| `chronus/metallic.py` | a+b*mu_n, n>=1, integer coefficients; mu_n^2=n*mu_n+1; nonnegative powers; conjugate and norm | coefficient recurrence, power composition, conjugate involution and norms | generalized legal digit language; negative powers and rational coefficients |
| `chronus/tribonacci.py` | order>=2, index>=0; initial zeros then one; iterative and binary companion paths | independent full-list recurrence for orders 2..8, indices 0..99 | exact root descriptor has no general scalar arithmetic interface |
| `chronus/calkin_wilf.py` | one-based root; positive reduced rationals; exact inverse and ordered Stern–Brocot mediant parents | 10,000 index roundtrips, coprime fraction grid, determinant and mediant identities | installed-package integration and externally enforced request envelopes |

Each module rejects booleans, floating inputs and invalid domains explicitly. The metallic
API keeps its parameter in every value and rejects mixing different fields. Its identity
is `(a,b)=(1,0)` and generator `(0,1)`. All integer/rational arithmetic is exact; none of
these arithmetic routines is labeled a quantum algorithm.

Pisano correctness: for primes p!=2,5, the quadratic-residue formulas bound a period.
Prime-power periods divide pi(p)*p^(e-1); candidate verification and factor stripping
recover the minimal return time. The composite period is the LCM of prime-power periods.
Verification of a return time alone is not verification of minimality. pi(29)=14 rather
than the candidate 28 is a regression test.

For n-step sequences, the state at k=n-1 is `(1,0,...,0)`. Therefore the returned
coordinate is `(M^(k-n+1))[0][0]`, not `(M^k)[n-1][n-1]`.
The positive root descriptor denotes the unique root of x^n-x^(n-1)-...-1 in (1,2):
Descartes' sign rule gives one positive root, P(1)=1-n<0 and P(2)=1>0. It is not a
rounded bisection result, and it does not pretend to implement all algebraic-real arithmetic.

Calkin–Wilf inversion uses Euclidean run lengths rather than one subtraction per edge.
Its output index can itself require Theta(a+b) bits; batching Euclidean operations does
not erase that materialization cost. Stern–Brocot endpoints may be 0/1 and 1/0.

The canonical map's two `kellogg/exact_field.py` descriptions are corrected to match
its real implementation: representable real square roots in Q(zeta_8), not sqrt(5).
The real subfield is Q(sqrt(2)); a separate golden-field representation is needed for
sqrt(5). No behavior of that helper was changed.

## Exact-only blockers in the remaining specification

1. **Wythoff bijection**: the supplied formula gives W(0,1)=W(1,0)=1. Specify the
   intended standard array, row seeds and indexing before implementing the inverse.
   Beatty floors must use exact integer/algebraic comparisons, not PHI_INV decimals.
2. **Metallic decomposition**: binary non-adjacent digits are insufficient for n>1.
   For n=3, recurrence weights 1,3,10,... cannot represent 2 with binary digits.
   Approve an Ostrowski/generalized digit language and prove uniqueness first.
3. **H4 composition**: missing z_to_qsqrt5 and qsqrt5_to_vec4 contracts; DphiT is
   defined but not actually called by h4_hash_complete. Z[phi] is dense in its
   single real embedding, so nearest_zphi needs a discrete embedding or restricted
   admissible coefficient set. Supply termination, tie rules, zero handling and
   a rigorously derived covering radius. Sampling cannot prove universal coverage.
   Computing and then discarding F(h) still costs Theta(h) output bits for UInt64 h.
   Cassini verification must compute the identity, not merely return its expected sign.
   The extra Zeckendorf index decrement can skip valid terms; existing canonical
   implementations should be reused once integration is designed.
4. **Quantum arsenal**: 32 real amplitudes cannot represent 120 indexed vertices
   or general complex states. A 120-dimensional logical space or an explicit
   128-dimensional qubit embedding is required, with all operator behavior defined.
   Continuous exp(-iHt) at generic algebraic times has transcendental entries;
   the proposed algebraic field is not closed under it. Use a certified symbolic
   functional calculus or an approved exact discrete gate/phase domain, not floats.
   Mean mixing, gradient descent and golden-section search are classical/nonunitary;
   no quantum relabeling is acceptable. VQE and QAOA also require an explicit
   optimization contract; exact circuit arithmetic does not remove variational search.
5. **TOE bridge**: return a typed state, measurement distribution/outcome, or metric,
   not an untyped State after every primitive. Born sampling is stochastic. Separate
   deterministic exact distributions from outcome generation and randomness provenance.
   Zero-state initialization must mean a normalized basis state, not the zero vector.
   No evidence proves all possible frontend grammars are universally computable.
6. **Consortium ledger**: a digest authenticates serialized data, not its truth.
   Institution strings do not establish independent reviewers. Counter increments
   do not measure hardware throughput. Require replayable computational evidence,
   authenticated producer/verifier identities, stale-value/replay handling and explicit
   separation of formulation, computational verification and device measurement.
7. **No-simulator semantics**: the attachment and repository include software
   amplitude/tableau execution examples while the mandate bans simulators. Clarify
   the admissible exact execution representation rather than renaming a simulation.
   Exact quantum algebra on a classical host does not by itself prove physical-QPU
   execution or asymptotic quantum advantage.

## Test evidence and release limitations

Executed in an isolated local directory using the actual baseline `chronus/__init__.py`:

```
python -m unittest discover -s tests -p 'test_chronus_*.py' -v
```

Exit 0; **25 test methods passed**. Four new module ASTs were also checked for float/
complex literals and non-stdlib imports: exit 0. Machine-readable evidence is in
`docs/exact_substrate_foundations_local_validation.json`. Finite tests corroborate
these contracts; they do not prove universal H4 coverage or quantum advantage.

This environment does not have pytest, Black or Flake8 installed. Repository-wide
checks, conftest integration, installed wheels/sdists, dependency ownership, CI,
benchmarks, security qualification, SBOM/provenance, staging and rollback are **not run**.
The copied baseline __init__ is test scaffolding for isolated import resolution; it is
not modified or included as a changed file in this patch. Production admission must
also enforce explicit bit-length, order, index and table-size limits at the caller
boundary; mathematical totality does not imply bounded service latency.

## Review and authority

Deutsch, Turing, Grover, Shor and Schrödinger are review-role labels, not participating
scientists. Clay, MIT, Caltech, Oxford, Cambridge, Princeton, ETH and any Moscow
institution are not engaged supervisors. ETCH and Moscow identities require clarification.
An AI review is not an independent human production sign-off. Nominate engineering/
security reviewer and release approver before leaving draft status. No merge, publication,
deployment, mining activation or main-branch change is authorized by this patch.
