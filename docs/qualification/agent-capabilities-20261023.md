# Euclid / Salamander agent capability integration — 2026-10-23

## Outcome

**PARTIAL implementation; focused tests PASS; production qualification HOLD.**

Source base: `c760cdfc6b5a7c8c9c97dec2493a9a75a1997dbc`.
Branch: `feat/euclid-salamander-agent-capabilities-20261023`.

All ten legacy roles now have executable bounded diagnostic/draft paths. This
is not a claim that every original mandate has been fulfilled. The legacy
`.github/agents/DEPRECATED.md` and role documents remain deprecated and unchanged.
No agent prompt is loaded or executed as authority. No source patch, merge,
deployment, arbitrary candidate code execution, reward or live recovery occurs.

## Wiring

1. `salamander.agent_capabilities.AgentCapabilitySuite.inspect` supplies the
   executable role surface, mandatory tenant/target binding, explicit limits,
   honest unknown states and hash-chained diagnostic receipts.
2. The existing `MultiAgentEntangledOrchestrator.run_multi_agent_cycle` invokes
   the suite for each supplied source target. Old call signatures still work;
   enterprise callers must explicitly supply the tenant. Its former unconditional
   `self_healing_ready=True` has been removed. A review is not a recovery proof.
3. The supported `EuclidRuntime.review_repository_capabilities` requires an open,
   composed runtime and the runtime-bound tenant (creator for standalone mode).
   It shares `self.autonomic.ledger` and its existing evidence sink. No second
   actuator is created and AL HARAS authorization paths are unchanged.
4. This is an in-process API, not an authenticated HTTP endpoint. Existing
   service-layer caller authentication remains required. The tenant field alone
   is not proof of identity. No new production route or startup policy is enabled.

## Role scope / remaining gaps

| Role | Executable scope | Not established |
|---|---|---|
| auditor | Source SHA-256 claim binding and mismatch rejection | Semantic evidence tracing across the repository |
| remediator | Candidate draft bundle validation; four-file / 128 KiB limits; unsafe-path rejection | Autonomous repair discovery, complexity/fanout qualification or correctness |
| test_engineer | Exact-rational known-answer unittest draft generation | General property/falsification generation or automated production test execution |
| governance | FAIL/NOT_PROVABLE aggregation over truth results | Approval, merge, release or AL HARAS authority |
| provenance | Tenant, source/input/report digest receipt in existing evidence ledger | Canonical THESEUS custody, automatic file writes or full seed/version replay |
| math_verifier | Bounded exact rational arithmetic identities and counterexamples | Symbolic theorem proving, quantified ranges or arbitrary expressions |
| security_verifier | Static dangerous-call, trivial constant-true-verifier and swallowed-exception findings | Comprehensive fail-closed/crypto/key-lifecycle verification |
| quantum_checker | Exact real-rational square-unitary and Kraus completeness checks | Complex/symbolic gates, measurement formalism or complete channel certification |
| precision_sentinel | Float/complex literals and constructors on explicitly exact surfaces | Runtime nondeterminism, conditioning, cancellation, full dataflow or oracle checks |
| pin_verifier | Explicit caller-selected boolean literal assignment invariants | Whole-program invariance or documentary theorem-claim analysis |

The deprecated blanket `theorem_proven=False` rule is not silently revived.
Pins must be explicitly selected. Unsupported/missing/malformed mathematical or
scientific evidence yields `NOT_PROVABLE`, not a fabricated pass. Security and
precision scans without findings likewise do not yield comprehensive PASS.
Governance FAIL means a diagnostic gate failed, not a final adjudication of an
entire system's security or mathematical validity.

## Qualification performed

Command:

```sh
python scripts/qualify_agent_capabilities.py --source-snapshot
```

**60 tests passed, zero test-suite failures/errors/skips.**
- 54 capability/negative/bounds/evidence/concurrency tests.
- 2 real module integration tests execute the modified orchestrator and actual
  retrieved Phi, intelligence, manifold, quantum tensor and Poincare modules.
  Those implementations are not mocked.
- 4 canonical runtime binding contract tests execute the actual new method AST
  with an explicitly documented composition fixture and the real EvidenceLedger.
  These are NOT full EuclidRuntime startup or production integration tests.
- Generated correct known-answer tests are executed successfully. A deliberately
  false generated identity is also executed and is required to fail; that
  expected failure is contained in a passing falsification test.
- Concurrent use of a single suite preserves its evidence chain across 40 reviews.
- Existing ActionRegistry still rejects unauthorised direct dispatch.
- Source and candidate draft contents are not copied to the shared ledger;
  hashes and status summaries are recorded instead. Returned drafts must still
  be treated as sensitive by callers.
- Compilation of modified/new Python files passed.

The isolated source-snapshot runner bypasses package `__init__` startup files
using namespace packages; it does not replace implementation modules. Git clone
was attempted but the private repo required credentials unavailable to the local
Git process. GitHub MCP reads provided the pinned source files. HTTP 429s during
reads were resolved with cooldown and smaller batches.

## Production gates still open

- Full package imports, supported runtime constructor/startup and production CI.
- Authenticated service exposure and deployed tenant/identity binding.
- Production persistence, restart, canonical custody and recovery qualification.
- Broader regression suites, independent security review and owner acceptance.
- Remaining per-role mandates listed above.
- Shared-ledger concurrent writers outside a single suite must remain serialized
  by the owner control plane; the suite's lock covers its own appends only.

No full-suite, packaged-install, production-ready or completed-self-healing claim
is made. No PR, merge, release or deployment was performed by this change.

## Invocation

With an already composed canonical runtime:

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

Requests do not execute the supplied source. Attach relevant evidence explicitly;
a role definition or metric cannot manufacture missing evidence.
