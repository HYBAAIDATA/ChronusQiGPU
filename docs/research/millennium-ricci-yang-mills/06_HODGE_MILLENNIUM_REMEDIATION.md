# Notion source transfer — HODGE MILLENNIUM REMEDIATION

> **Archive notice:** This is a historical Notion research/source copy, not independent verification, an accepted proof or authority to deploy. Source wording is retained; mathematical/security claims inside are statements made by the historical source, not QC findings. 

- **Original Notion page:** https://app.notion.com/p/febdb8aec0b3400bb9a3040cd85ba81f
- **Notion page ID:** `febdb8ae-c0b3-400b-b9a3-040cd85ba81f`
- **Source capture/edit reference:** `2026-07-31T22:45:19.869Z`
- **Transfer date:** 2026-10-28
- **Content type:** Original Notion content
- **Evidence/claim status:** Later 31 July corrective evidence record; clearly restricts Millennium claims to bounded computational evidence
- **Current repository baseline for reconciliation:** `HYBAAIENTERPRISE/HYBAEnterprise@c4ea01fd1b82d411db3fd394c96fc143579b08b5`
- **Formatting note:** Notion-flavoured Markdown, including certain Notion-specific tags, is retained as source material. Embedded code blocks are proposals, not runnable files created by this transfer.

---

## Preserved source material

<callout icon="⚖️">
<b>Claim boundary.</b> Nothing in this remediation asserts a solution to any Millennium Prize problem. The Hodge component is a <i>status classifier</i> for known varieties plus bounded consistency checks. The Millennium component provides exact algorithms and bounded numerical evidence. Where a problem is open, the code computes checkable instances and returns witnesses a third party can independently verify.
</callout>

## Purpose

Durable laboratory record for the Hodge / Millennium hardening pass. The build sandbox was wiped <b>twice</b> mid-session and all in-progress work was lost both times. This page exists so the work can be reconstructed without re-deriving it.

The sealed artefact is <code>HYBA_hodge_millennium_hardening.tar.gz</code> (421,263 bytes): seven files at their repo paths plus a 15,459-line unified diff against the pristine archive. Andre holds this as the accepted baseline.

## Status

| Component | State | Evidence |
| --- | --- | --- |
| <code>src/euclid/hodge/core/computational_hodge_theory.py</code> | Patched | 0 failures across all reference checks |
| <code>src/euclid/millennium/computations.py</code> | New | All exact-maths checks pass |
| <code>src/euclid/__init__.py</code> | Lazy (PEP 562) | Imports without SciPy; fail-closed preserved |
| <code>src/euclid/millennium/__init__.py</code> | Lazy (PEP 562) | <code>computations</code> reachable as package attribute |
| <code>tests/millennium/test_millennium_capabilities_property_tests.py</code> | Rewritten | <b>32/32 pass</b> |
| <code>.ci/check_test_collection.py</code> | New | Negative control proven |
| <code>.ci/collection-baseline.txt</code> | New | 105 entries, ratcheted |

## The five genuine Hodge defects

On re-reading the pristine file, most of the requested patch set (items 2, 3, 4, 5, 6, the <code>NDArray</code> typing, <code>HODGE_CLASSIFIER_DESCRIPTION</code>, <code>_normalise_entries</code>, K3 <code>picard_rank</code> discipline, correct CY3 <code>(2,2): h11</code>) was <b>already present</b>. The real defects were these:

1. <code>from __future__ import annotations</code> sat <i>above</i> the module docstring, so <code>__doc__</code> was <code>None</code> — the claim-boundary string was not actually reachable at runtime.
2. <code>set_h_pq</code> assigned into a copy of <code>entries</code> without clearing the symmetry orbit <code>{(p,q), (q,p), (n−p,n−q), (n−q,n−p)}</code>. Every overwrite of an existing value raised <code>ValueError: inconsistent Hodge entries</code>.
3. <code>compute_for_grassmannian</code> used <code>max(1, comb(min(n, dimension), min(p, n−k, k)))</code>, which is not a Grassmannian Betti number. Gr(2,4) produced h³³ = 4 against h¹¹ = 1, so <b>Gr(2,4) could not be constructed at all</b>. Replaced with the exact Gaussian binomial <code>[k+m choose k]_q</code>.
4. <code>compute_for_hypersurface</code> <b>ignored its </b><b><code>degree</code></b><b> argument entirely</b>, returning h\^\{p,p\} = 1 for every p. Every degree produced an identical diamond. Replaced with Griffiths' residue calculus via the Jacobian ring Hilbert series.
5. The Grassmannian dispatch passed the caller's <code>dimension</code> instead of dim Gr(k,n) = k(n−k), truncating entries and breaking Serre duality.

### Reference values now reproduced

| Object | Quantity | Value |
| --- | --- | --- |
| Quartic surface in P³ (K3) | h¹¹, b₂, χ | 20, 22, 24 |
| Cubic surface | h¹¹, χ | 7, 9 |
| Quadric surface | h¹¹, χ | 2, 4 |
| Quintic 3-fold | h³⁰, h²¹, χ | 1, 101, −200 |
| Cubic 3-fold | h²¹, χ | 5, −6 |
| Gr(2,4) | Betti, χ | 1,0,1,0,2,0,1,0,1 · 6 |
| Gr(1,3) / Gr(2,5) / Gr(3,6) | χ = C(n,k) | 3 / 10 / 20 |

Full-square Hodge symmetry and Serre duality verified across all 9 variety types × dimensions 1–4.

### Claim safety is now structural

<code>HodgeStatusResult.__post_init__</code> forces <code>theorem_claim_emitted = False</code> and rewrites <code>classifier_description</code> to the canonical string. Tested adversarially: constructing a result with <code>classifier_description="HYBA proves the Hodge conjecture"</code> is silently overridden. The invariant lives in one place so no caller, subclass, or later edit can emit a proof claim by setting a field.

## Millennium: simulation removed, not repaired

Per instruction — <i>quantum comes from maths, we don't need to simulate</i> — the <code>_simulate_*</code> helpers were <b>deleted</b>, not fixed. They were tautologies: each returned a literal <code>True</code> or a fixed dict, and the tests asserted against helpers defined in the same test file, so they exercised no production code and could not fail.

<code>computations.py</code> contains real mathematics only. Verified against independently known values:

- Zeta zeros: exactly 10 in (10, 50), <b>max deviation from published ordinates 3.268e-13</b>
- <code>zeta(2) = π²/6</code>, <code>zeta(4) = π⁴/90</code>, <code>zeta(−1) = −1/12</code>
- Held-Karp <b>equals brute-force optimum</b> on every instance; greedy heuristic never beats it
- SAT: every UNSAT result confirmed by exhaustive search over 300 random formulas
- <code>π(10⁴) = 1229</code>, <code>π(10⁶) = 78498</code>; <code>600851475143 = 71·839·1471·6857</code>
- Betti numbers of S¹…S⁵ derived from GF(2) boundary-matrix ranks
- <code>y² = x³ + 1</code> over F₅ has 6 points; Hasse bound holds throughout

### Three claims removed rather than implemented

No honest implementation could support these, so they were deleted with the reasoning recorded in the test module docstring:

1. <b>Polynomial-time factorisation, SAT, and TSP</b> — together these assert P = NP. Replaced with <i>completeness and exactness</i> properties instead.
2. <b>"Infinite rank / mathematically impossible to exploit"</b> security and room-temperature coherence — not falsifiable.
3. <b><code>test_global_traffic_prediction</code></b> — computed <code>abs(prediction − traffic_volume)</code> where <code>prediction</code> was a dict (raises <code>TypeError</code>) and divided by a value whose strategy allowed <code>0.0</code>. No production predictor exists behind it.

## Finding: 105 pre-existing collection failures

<callout icon="📍">
<b>Provenance.</b> All 105 are in the repository archive (<code>HYBA_Unified_Backend-main.zip</code>). They are pre-existing and untouched by this pass — exactly one of the 105 was mine to fix. The Yang-Mills / Grover claim issues are separate and come from the four PDFs attached to chat.
</callout>

The original bug was <code>class MillenniumCapabilitiesPropertyTests</code> missing its <code>Test</code> prefix, so pytest silently de-collected all 32 tests. CI stayed green while nothing ran. Building a guard for it revealed the same failure mode is widespread:

- <b>\~102 test files do not parse at all</b> — <code>unexpected indent</code>, unmatched brackets, <code>try</code> without <code>except</code>. pytest can never collect these.
- <b>Further de-collected classes</b>: <code>DeltaCaptureSettlementTests</code> (4 tests), <code>PythagorasVQCContractTests</code> (6), <code>InstitutionalEvidenceBoundaryTests</code> (2), <code>ExecuteJourneyTasksTests</code> (3).

Repo-wide there are 13,105 collectable tests. The invisible ones are the concern: a test that cannot be collected is indistinguishable from a passing test in a green CI run.

### Why the guard is baselined rather than blocking

Failing on all 105 at once would make the gate red on day one, and a permanently red gate gets ignored — which is precisely how the original bug survived. So findings are split: <b>regressions</b> (not in baseline) fail the build; <b>known debt</b> (in baseline) is reported with a count. The baseline can only shrink; <code>--update</code> refuses to grow it without <code>--allow-baseline-growth</code>.

The guard parses the syntax tree rather than running pytest, so it needs no third-party packages and <b>cannot be de-collected by the bug it detects</b>.

### Negative control (the part that matters)

Reintroducing the exact original bug produced two independent failures:

```javascript
FAIL (floor): tests/millennium/...property_tests.py: collected 0, below the required floor of 32
FAIL (regression): ...::MillenniumCapabilitiesPropertyTests: holds 32 test_* methods but does not
                   start with 'Test', so pytest silently skips all of them
```

Restored → exit 0, 32/32 pass. A guard that has never been shown to fail is not evidence.

## Methodological warning: grep counts are not a defect inventory

Two of my <b>own</b> checks produced false positives this session:

1. A substring check for <code>"NOT a mass gap"</code> failed because the phrase was split across a line wrap in the docstring it was validating.
2. A <code>_simulate_</code> guard matched its own module docstring, which legitimately discusses the deleted helpers in prose.

Both are now AST-based or whitespace-normalised. This directly bears on the stubs hunt: the raw counts — <b>1283</b> bare <code>return True</code>, <b>1428</b> <code>Simplified</code>, <b>460</b> <code>placeholder</code>, <b>193</b> <code>stub</code>, <b>54</b> <code>NotImplementedError</code>, <b>136</b> <code>_simulate_*</code>/<code>simulate_*</code> definitions — are <i>not</i> a defect list. Grep-driven mass edits would damage working code. Triage must be AST-based, and a prioritised inventory must precede any edit.

## Recovery runbook

If the sandbox resets:

```bash
# 1. Re-upload HYBA_Unified_Backend-main.zip, then:
cd /data && mkdir -p repo && cd repo && unzip -oq ../HYBA_Unified_Backend-main.zip

# 2. Re-apply the sealed artefact over the pristine tree:
tar xzf HYBA_hodge_millennium_hardening.tar.gz
cp -r files/. /data/repo/HYBA_Unified_Backend-main/

# 3. Verify (pytest/hypothesis are NOT installable — no network):
cd /data/repo/HYBA_Unified_Backend-main
python3 .ci/check_test_collection.py          # expect exit 0
PYTHONPATH=/data/shim python3 -c "..."        # expect 32/32
```

<b>Environment constraints:</b> Python 3.13.13, numpy 2.5.1. <code>pytest</code>, <code>hypothesis</code>, and <code>scipy</code> are <b>not installed and cannot be installed</b> — no network. Offline shims live at <code>/data/shim/</code> and are harness-only, never repo code.

<b>Tool gotcha:</b> <code>editFile</code> takes <code>file_path</code>; <code>writeFile</code> / <code>readFile</code> / <code>downloadFile</code> take <code>path</code>. Every <code>old_string</code> must be copied from freshly-read content — a fabricated target aborts the whole atomic batch.

## Stub inventory (AST triage, 31 Jul 2026)

Every function in <code>src/</code> was classified by the <b>structure of its body</b>, not by text matching. 3,878 files parsed, <b>40,561 functions analysed</b>, 1,890 flagged.

| Tier | Count | Meaning |
| --- | --- | --- |
| <b>T1</b> | <b>132</b> | Returns a hardcoded literal while ignoring every argument |
| T2 | 270 | Empty body, <code>NotImplementedError</code>, or other input-ignoring literal |
| T3 | 524 | Review individually — real body but unused parameters, or simulation-named |
| T4 | 964 | Legitimate — abstract/Protocol/overload, or parameterless constant accessor |

<b>Actionable: 402.</b> Of those, <b>103 sit on a gate</b> and <b>51 are Tier 1 gates</b>.

### The grep counts were inflated roughly 25×

| Marker | Text-scan count | Structural reality |
| --- | --- | --- |
| bare <code>return True</code> | 1283 | <b>51</b> functions actually return literal <code>True</code> ignoring all inputs |
| <code>simplified</code> | 1428 | 1403 in prose/comments, 26 in code |
| <code>placeholder</code> | 460 | 446 in prose/comments, 16 in code |
| <code>in production</code> | 750 | 746 in prose/comments, 4 in code |
| <code>simulate</code> | 1614 | 1166 in prose/comments, 448 in code |

The remaining <code>return True</code> occurrences are ordinary predicates that return <code>True</code> <b>after doing real work</b>. A grep-driven mass edit would have destroyed working code. This vindicates the decision to triage before editing.

### Highest severity: gates that cannot fail

These decide whether something is valid, compliant, approved, or safe, and they return a hardcoded affirmative regardless of input. <b>A gate that always returns </b><b><code>True</code></b><b> is worse than an absent gate, because it manufactures evidence of compliance.</b>

- <code>backend/systems/intelligence/safety/constitutional_oversight.py:10</code> — <code>ConstitutionalOversight.check</code> → <code>{'safe': True}</code>
- <code>backend/systems/intelligence/oversight/constitutional_council.py:10</code> — <code>ConstitutionalCouncil.review</code> → <code>{'approved': True}</code>
- <code>backend/standards/quantum_standards_compliance.py</code> — <b>five</b> IEEE 2830 / NIST / OpenQASM validators → <code>True</code> (duplicated verbatim in <code>security/post_quantum/</code>, so <b>ten</b> total)
- <code>backend/validation/formal_verification.py</code> — <b>seven</b> property verifiers (<code>QuantumEntanglement</code>, <code>QuantumInterference</code>, <code>QuantumCoherence</code>, <code>Homotopy</code>, <code>Incompleteness</code>, <code>LobTheorem</code>, <code>MinkowskiMetric</code>) → <code>True</code>
- <code>security/self_healing/self_healing_engine.py:339-369</code> — <b>all seven</b> <code>_verify_*</code> methods → <code>True</code>. The self-healing engine confirms every remediation succeeded without checking anything.
- <code>euclid/al_haras_integration.py:167</code> — <code>AlHarasQuantumSecurity.verify_integrity</code> → <code>True</code>
- <code>euclid/api/services.py:77</code> — <code>AuthenticationService.authenticate</code> → <code>{'authenticated': True, 'account_id': 'system', …}</code>
- <code>security/penetration_testing_framework.py:676</code> — <code>_check_audit_logging</code> → <code>True</code>
- <code>hyba_kernel/agi_interface.py:343</code> — <code>_verify_privacy_invariants</code> → <code>True</code>
- <code>yang_mills/core/continuum_extrapolation.py:560,586</code> — <code>WightmanAxiomVerifier._verify_poincare_covariance</code> / <code>_verify_locality</code> → <code>True</code>
- <code>yang_mills/advanced/yang_mills_open.py:161</code> + <code>euclid/humanity/yang_mills_open.py:161</code> — <code>verify_gauge_invariance</code> → <code>True</code>
- <code>backend/api/v1/prisma.py:313</code> — <code>validate_ledger</code> → <code>{'valid': True, 'total_entries': 240, 'validation_rate': 1.0, …}</code>

<callout icon="🚨">
<b>The Wightman axiom verifiers matter for the mass-gap claim.</b> <code>_verify_poincare_covariance</code> and <code>_verify_locality</code> return <code>True</code> unconditionally. Any Yang-Mills output that cites Wightman axiom verification as support is citing nothing. This compounds the Appendix E finding: both the analytic scaffold and the runtime verifier compute nothing.
</callout>

### Fabricated payloads (81 findings)

Literal metrics, forecasts, and analytics returned as constants — including <code>get_quantum_security_metrics</code>, <code>get_containment_status</code>, <code>get_resonance_analytics</code>, <code>get_pool_analytics</code>, McKinsey-branded <code>_assess_enterprise_risks</code> and <code>_build_ansoff_matrix</code>, and <code>TopologicalIntelligence.compute_betti_numbers</code> → <code>{'β0': 1, 'β1': 0, 'β2': 0}</code>. Any dashboard reading these displays invented numbers.

### 14 files in src/ do not parse

They cannot be imported, so nothing in them runs today: <code>analysis/blockchain_phi_resonance.py</code>, <code>backend/systems/intelligence/domain_adapters/gnn_knowledge_graph.py</code>, <code>cogito/cogito/core/cbf/control_barrier_runtime.py</code>, <code>cogito/cogito/integration/__init__.py</code>, <code>euclid/physics/universality_classes.py</code>, <code>euclid/pythagoras/integration/__init__.py</code>, <code>euclid/sovereign_liquidity_bridge/{api,ifsb15_capital}.py</code>, <code>euclid/voice/quantum_development_agent.py</code>, plus 5 test files misplaced under <code>src/</code>.

### Remediation order

1. <b>T1 gates</b> — implement the check, or make it <b>fail closed</b> by raising <code>NotImplementedError</code>. Never leave an affirmative default.
2. <b>T1 payloads</b> — remove, or explicitly mark the surface as sample data.
3. <b>T2</b> — convert silent no-ops into explicit failures.
4. <b>The 14 unparseable files</b> — fix or delete.
5. <b>T3</b> — individual review, no bulk edits.

## Millennium maths remediation (31 Jul 2026, second pass)

Artefact: <code>HYBA_millennium_maths_remediation.zip</code> (1,787,140 bytes) — 312 changed files, an 8,966-line diff against the pristine archive, plus both scripts. Verification: <b><code>MILLENNIUM MATHS CHECK FAILURES: 0</code></b> across 45 checks.

### Five mathematics files rewritten

| File | Was | Now |
| --- | --- | --- |
| <code>euclid/seven_intelligences.py</code> | <code>{beta_0: 1, beta_1: 12, beta_2: 3}</code> for every input | Real simplicial homology over GF(2) |
| <code>athena/core/learning_substrate.py</code> | Two fallbacks fabricating Betti numbers and a fixed 0.1 lift | Both raise <code>RuntimeError</code> |
| <code>euclid/humanity/yang_mills_open.py</code> | <code>return True  # Simplified check</code> | Mean-plaquette observable + Haar gauge rotation |
| <code>yang_mills/advanced/yang_mills_open.py</code> | Byte-identical duplicate of the above | Same implementation |
| <code>yang_mills/core/continuum_extrapolation.py</code> | W0/W1/W2/W4/W5 all bare <code>True</code> | Honest values with provenance strings |

<b>Homology.</b> Face closure, sparse boundary matrices, Gaussian elimination, βₖ = dim ker(∂ₖ) − dim im(∂ₖ₊₁). Verified against S¹, the disc, S² as the tetrahedron boundary, the solid tetrahedron, disjoint discs, the figure eight, S²∨S¹, three disjoint circles, and the <b>7-vertex minimal torus</b> (V=7, E=21, F=14, χ=0 → β = 1,2,1). Raises on input from which no complex can be read. GF(2) coefficients do not distinguish torsion, and the docstring says so.

<callout icon="⚖️">
<b>Claim boundary on gauge invariance.</b> Plaquette invariance is a <b>theorem</b>, not an open question: for any g(x) ∈ U(N), U\_μ(x) → g(x) U\_μ(x) g(x+μ)† leaves Tr U\_\{μν\}(x) unchanged. The new check is therefore a <b>regression test on the implementation</b> — the neighbour shifts, the adjoints, the index conventions. It is not a property of the configuration and it is <b>not evidence for a mass gap</b>. The docstring states this plainly so no downstream reader can mistake it.
</callout>

<b>Wightman axioms.</b> W0, W1 and W5 were returning <code>True</code> while their own comments admitted they were <i>assumed</i>. An assumption reported as a verification is manufactured evidence, so they now return <code>False</code> with provenance <code>assumed_by_construction</code>. W2 probes the only subgroup single-argument Wightman functions can express — the time reflection W(−t) = conj(W(t)) — and reports <code>reflection_subgroup_only</code>. W4 fails closed with <code>not_testable_from_supplied_data</code>, because spacelike separation cannot be expressed by this data shape at all. <b>A verifier that cannot test must report unverified.</b> W3 was already genuinely computed and is untouched.

Negative controls were run for each: transposing a single gauge link moves the plaquette; a reflection-violating function is rejected; empty and non-finite inputs fail closed.

### Finding: repo-wide annotation corruption (310 files, 857 sites)

Found by accident while verifying the above — an <code>AttributeError: module 'logging' has no attribute 'Optional'</code>. A past codemod had moved the module prefix onto the typing constructor:

```py
Optional[np.ndarray]      ->  np.Optional[ndarray]
Optional[logging.Logger]  ->  logging.Optional[Logger]
Union[np.ndarray, dict]   ->  np.Union[ndarray, dict]
```

<callout icon="🚨">
These <b>parse cleanly</b>, so linters, <code>py_compile</code> and pytest collection miss them entirely — but the expression raises <code>AttributeError</code> the moment the annotation is evaluated. Files carrying <code>from __future__ import annotations</code> kept them dormant; <b>48 files without it could not be imported at all.</b> This is the same failure class as the de-collected test bug: invisible to every green check in the pipeline.
</callout>

Repaired 473 <code>Optional</code> sites, 160 <code>Union</code> sites, and 136 destroyed <code>Union</code> members. Where the codemod had reduced a member to a bare module name the original type was <b>destroyed</b>; those became <code>Any</code> rather than a plausible-looking guess. The fixer uses an explicit allow-list of module prefixes so genuine APIs (<code>ctypes.Union</code>, <code>ast.List</code>, <code>types.Type</code>) are untouched, and it skips any file whose repaired text would not parse.

Three sites remain, all inside <code>backend/systems/intelligence/domain_adapters/gnn_knowledge_graph.py</code>, which has a pre-existing syntax error at line 312 — one of the 14 unparseable files already listed above.

## Outstanding

- [x] Millennium maths: Betti numbers, gauge invariance (both copies), Wightman axioms, fail-closed Athena fallbacks — 45/45 checks pass
- [x] Repair the 857 mangled type annotations across 310 files
- [ ] Remaining maths findings: <code>pvsnp_generalization.py</code> (four hardcoded substrate-independence scores feeding <code>overall_score > 0.7</code>), <code>riemannian.py:632</code> → <code>1.0</code>, <code>geodesics.py:237</code> → <code>0.0</code>, <code>quantum_gauge_core.py:103</code> → <code>0.999999999</code>, <code>euclid_redux_enterprise/…/yang_mills_open.py:60,70</code> (self-declared AUTO-GENERATED STUB)
- [ ] Add a CI guard for the mangled-annotation pattern so it cannot reappear
- [x] Stubs hunt — AST triage complete; 402 actionable findings inventoried above
- [ ] Fail-close the 51 Tier 1 gates, starting with constitutional oversight, self-healing verifiers, and standards compliance
- [ ] De-duplicate <code>quantum_standards_compliance.py</code> (verbatim copy in <code>backend/standards/</code> and <code>security/post_quantum/</code>)
- [ ] Add a CI guard that fails on any new T1 finding, baselined like the collection guard
- [ ] Audit downstream consumers for proof-implying language: <code>api/hodge_evidence_api.py</code>, <code>hodge/agents/hodge_evidence_agent.py</code>, <code>docs/mathematical_foundations/HODGE_AND_CLAIM_SAFETY.md</code>, <code>formal/hodge_cycle_statement.lean</code>
- [ ] Commit a repo-resident offline harness so acceptance criteria are demonstrable without pytest
- [ ] Wire the collection guard into <code>capability-property-tests.yml</code> / <code>nightly-property-tests.yml</code> / <code>2-build-and-test.yml</code>
- [ ] Drive the 105-entry collection baseline down (\~102 unparseable files first)
- [ ] Consider the other 19 test files containing <code>_simulate_</code> now the pattern is proven

### PDF claim-safety items (from chat attachments, not the repo)

- [ ] Grover 630× factor is <b>calibration, not derivation</b> — the product of <code>phi_resonance_factor</code> 6.854, <code>zeta_optimization</code> 2.1, <code>gamma_tuning</code> 1.8, <code>consciousness_coupling</code> 2.5, <code>gpu_acceleration</code> 8.2 ≈ 532, then "calibrated to empirical 630×". <code>consciousness_coupling = 2.5</code> has no derivation.
- [ ] <b><code>79,600x</code></b><b> exceeds the O(√N) ≈ 65,536× ceiling</b> for a 32-bit space. Physically impossible as stated; flagged in workflow.pdf task 5.01.
- [ ] Yang-Mills mass-gap monograph rests on proof <i>sketches</i>; Appendix E is an admitted scaffold — <code>return np.eye(2)</code>, <code>T = np.zeros((4,4,4,4))</code>, <code>num = 0.0</code> never accumulated. <b>The "numerical validation" computes nothing.</b> Must not be cited as validation.

<callout icon="🎯">
<b>Publish bar.</b> Extraordinary claims require extraordinary proof. Under the code↔documentation elevation rule, code is elevated to meet documentation and never the reverse. Any claim not yet met by verified code stays <b>INTERNAL</b> until it is.
</callout>
