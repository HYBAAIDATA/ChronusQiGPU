# Euclid / Salamander agent capability integration — 2026-10-23

## Outcome

**Bounded in-process integration and scoped qualification PASS. Full legacy-role
implementation remains PARTIAL. Production promotion remains HOLD.**

Branch: `feat/euclid-salamander-agent-capabilities-20261023`.
Draft review: https://github.com/PhiEnterprise1/EuclidPhiEnterprise/pull/145.
Initial integration commit: `0c47fd32020b94366b4eca20be73dd4b56c85010`.
The companion manifest identifies the exact follow-up source candidate by hash.

This follow-up replaces extracted-method runtime fixtures with actual constructor
and composition tests, fixes a package startup dependency bug, hardens concurrent
shared evidence writers and input bounds, and adds a clean-installed feature gate.
It does not silently redefine these bounded diagnostics as full self-healing.
Deprecated role documents remain unchanged and are not executed as authority.

## Integration and functional fixes

1. `AgentCapabilitySuite.inspect` runs ten explicit diagnostic/draft roles. It
   binds tenant, target, source/input/report digests and statuses to a receipt.
2. `MultiAgentEntangledOrchestrator.run_multi_agent_cycle` invokes the suite for
   each source target. Old call signatures remain supported; enterprise callers
   must supply the tenant explicitly. A review never sets self-healing ready.
3. `EuclidRuntime.review_repository_capabilities` uses the composed Salamander
   ledger and its existing Euclid evidence sink. An uncomposed, closed or wrongly
   tenant-bound runtime refuses the request. No second actuator is created.
4. Normal `import salamander` no longer eagerly imports the optional mining
   integration (which requires CHRONUS, absent from the standalone distribution).
   Existing named mining exports remain lazy; requesting one still requires its
   actual owner dependencies. `AgentCapabilitySuite` is a public lazy export.
   Wildcard imports can request mining names: use explicit control-plane imports
   in standalone consumers. No optional subsystem is fabricated or vendored.
5. `EvidenceLedger` now serializes append/read/verify/checkpoint operations on a
   shared instance. This covers multiple suites and owner observations, not only
   one suite's own writes. Its durable JSONL subclass serializes writes too.
   Sink failure does not commit in-memory state; recursive sink append is denied.
   The lock is process-local, NOT cross-process coordination or THESEUS custody.
   A sink which performs an external side effect then raises requires operator
   reconciliation; no distributed exactly-once guarantee is claimed.
6. Evidence preflight rejects custom objects/callbacks, cycles, depth >24,
   >10,000 structural visits, non-string keys, non-finite numbers and >4096-bit
   integers before serialization. The serialized 128 KiB cap still applies.
   Tenant/target/source must be plain strings. Source AST and arithmetic budgets
   remain explicit; supplied source and emitted drafts are never executed by
   `inspect`, applied, merged or deployed.

This is an **in-process API**, not a newly authenticated HTTP service. Caller
identity/authorization must remain with the service and AL HARAS owner boundary.
A tenant string is not authentication. Diagnostic PASS cannot authorize action.

## Capability contract and unfulfilled legacy scope

| Role | Executable supported contract | Still not established |
|---|---|---|
| auditor | Supplied claim/source SHA-256 binding and mismatch rejection | Semantic evidence tracing across the repository |
| remediator | Caller-supplied draft bundle validation; four-file / 128 KiB limits and safe paths | Autonomous repair discovery, complexity/fanout or correctness qualification |
| test_engineer | Safe exact-rational known-answer unittest draft generation | General property-test generation and automatic production test execution |
| governance | FAIL/NOT_PROVABLE aggregate over truth diagnostics | Approval, merge, release or AL HARAS authority |
| provenance | Tenant/source/input/report digest receipt, existing evidence sink and tested local checkpoint integrity | Canonical THESEUS custody and full seed/version replay |
| math_verifier | Bounded exact rational arithmetic identities and counterexamples | Symbolic theorem proving, quantified ranges or arbitrary expressions |
| security_verifier | AST dangerous calls, trivial constant-true verifier and swallowed-exception findings | Comprehensive crypto, key lifecycle or whole-program security proof |
| quantum_checker | Exact real-rational square-unitary and Kraus completeness checks | Complex/symbolic gates, full measurement formalism or general channel certification |
| precision_sentinel | Float/complex literals and constructors on explicitly exact surfaces | Runtime conditioning, cancellation, full dataflow or numerical oracle qualification |
| pin_verifier | Explicit caller-selected boolean literal assignments | Whole-program invariance or documentary theorem-claim analysis |

Missing/unsupported/malformed scientific inputs stay `NOT_PROVABLE`, not PASS.
Security/precision scans without findings likewise are not comprehensive passes.
No deprecated blanket `theorem_proven=False` rule is silently revived. Known-answer
falsification tests really run and fail as expected inside a passing negative test.

## Qualification actually performed

Local environment: Linux, CPython 3.13. The workspace contains an MCP-retrieved,
pinned dependency closure, **not a full Git checkout**. Package initializers were
not bypassed in the current default qualification. Optional specialist owners
which are absent remain recorded unavailable; a composed base runtime is not the
same as a fully deployed `EuclidRuntime.production()` organism.

| Command / gate | Observed result |
|---|---|
| `python scripts/qualify_agent_capabilities.py` | **80 tests PASS**, zero failures/errors/skips |
| `python -m pytest -q tests/test_salamander_autonomic.py tests/test_salamander_authority_replay.py tests/test_salamander_outcome_evidence.py` | **67 tests + 26 subtests PASS** |
| `python scripts/qualify_agent_capability_package.py --output-dir <fresh external directory>` | **PASS**, sdist → wheel → clean venv → installed diagnostic smoke |
| Changed Python compilation / Python 3.11 grammar inspection | PASS |
| New workflow YAML parse | PASS; hosted matrix result NOT VERIFIED |

The 80 focused tests comprise 56 existing capability/orchestrator tests and 24 new
actual-runtime, persistence, concurrency and input-boundary tests. The previous
four AST-extracted runtime fixture tests have been removed, not counted as real
startup evidence. The 67 regression tests use their existing explicitly labelled
unit actuators/probes; those results are not production voyages. Local regression
execution used the retrieved modules rather than the full repo pytest bootstrap.

Specific observed coverage:
- Actual `EuclidRuntime` constructor and `compose_organism`, canonical receipt
  sink, tenant rejection, re-composition binding, closed/uncomposed refusal.
- No supplied source execution; no authorization bypass after diagnostics.
- Concurrent runtime reviews mixed with real control-plane observations.
- Multiple suites and direct owner writers sharing one ledger: 160 appends.
- Durable ledger concurrent writes: 80 appends, fresh-process replay, then
  deliberate record corruption rejected on restart.
- Actual runtime checkpoint evidence saved and verified in a fresh process;
  tampered evidence rejected. This is **not** full production runtime restore,
  specialist recovery, remote custody or deployed tenant reattachment evidence.
- Source/draft bodies are excluded from ledger receipts; returned drafts may
  still contain caller-sensitive material and must not be broadly exposed.
- Clean-installed feature smoke confirms installed module origins, normal public
  import without CHRONUS, all ten role outputs, positive and negative exact
  checks, evidence reconstruction and fail-closed registry dispatch.

The package smoke stages the retrieved product sources and existing package
configuration, builds an sdist, builds its wheel, verifies source-byte equivalence
and installs into a fresh venv. Its input manifest identifies this **source
candidate**, not an invented clean-Git release commit. It does not run the
canonical full-product release verifier, import every optional module or certify
all Euclid enterprise dependencies. Do not publish these locally built artefacts.

The optional historical `--source-snapshot` runner still runs only the module
suite; it is not the default and cannot qualify constructor/package startup.

## Reproducible hosted qualification

`.github/workflows/agent-capability-qualification.yml` adds Linux/Windows,
Python 3.12/3.13 jobs for the actual runtime tests, existing authorization/replay
regressions and installed diagnostic feature check, retaining package evidence.
It has read-only repository permissions and no deploy/publish step.

The draft PR also falls under the existing enterprise clean-install and
Salamander package workflows. **Their outcomes have not been verified here.**
The GitHub check-runs endpoint returned HTTP 403 (token cannot read checks).
The separate commit-status endpoint returned pending with zero legacy statuses
for `0c47fd3`; that is not proof that Actions passed or even ran. After the new
commit, an authorized reviewer must inspect the checks on the exact PR head.

## Explicit production blockers / acceptance gates

| Gate | State / required action |
|---|---|
| Full intended role mandates | PARTIAL — scope gaps above require implementation/owner acceptance, not relabelling |
| Hosted full-checkout matrix and existing product CI | UNVERIFIED — authorized CI review required |
| Full enterprise wheel + complete production startup | UNVERIFIED — canonical clean-install pipeline must pass |
| Licensing consistency | BLOCKED for publication: root LICENSE says BSD-3-Clause; Salamander package configuration/README say MIT. Owner must reconcile licensing; this change does not relicense the product |
| Actual specialist owners, credentials and authenticated tenant binding | UNVERIFIED in deployment; owner-provided integration required |
| Canonical THESEUS custody, full runtime restart, recovery/rollback and independent postconditions | UNVERIFIED; local evidence replay is not a substitute |
| Independent security review and owner production acceptance | PENDING |

**Release decision: HOLD.** Do not equate a green focused feature check with
complete legacy-role implementation or production self-healing qualification.
No merge, registry publication, release, deployment or live recovery was executed.

## Supported invocation

```python
review = runtime.review_repository_capabilities(
    tenant_id="the-runtime-bound-tenant",
    target="src/example.py",
    source="invariant = False\nx = 1",
    evidence={
        "pins": {"invariant": False},
        "identities": [{"left": "1/3 + 2/3", "right": "1"}],
        "quantum": {"kind": "unitary", "matrices": [[[0, 1], [1, 0]]]},
    },
)
```

Use an already composed, open canonical runtime and plain JSON evidence. Inspect
per-role status and scope; never infer permission or recovery from a review.
