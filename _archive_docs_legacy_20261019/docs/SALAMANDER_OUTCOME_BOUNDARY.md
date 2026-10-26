# SALAMANDER custodied outcome boundary — incomplete increment

## Verdict and scope

**NOT PRODUCTION READY. The requested complete closed-loop production delivery is not complete.**

Baseline: `QuantumPhiRedux/PhiMiner`, `main`, commit
`585d7b11d9cc8e183ff4d5cda44996a9ac30dc4e`.

This increment replaces defective **success-certification** behavior on the existing
`pythia-mine -> MiningAutonomyBridge` telemetry path. It does not pretend to replace
all healing implementations, authorize existing actuators, or execute the required
production voyages. No actuator, optimiser, domain algorithm or capability is retired.
PR #143 is the single canonical convergence lane. The complete 14-file change set
from #134 (`e8da78053c35098884965a7a4c76183042237e4e`) was absorbed on that lane,
with #143's custodied verifier and sink-before-memory ledger ordering preserved.
See `reports/salamander_pr134_absorption.json`. This is file-set consolidation,
not a GitHub merge or a production-readiness claim.

## Executable architecture

Existing owning runtime / RecoveryGovernor / ClosedLoopOptimizer
-> existing MiningAutonomyBridge
-> preserve producer's reported result separately
-> optional CustodiedMiningOutcomeVerifier
-> read independently custodied AL HARAS, CHRONUS, PYTHIA and contract bindings
-> recompute postcondition comparison
-> VERIFIED or UNVERIFIED (retain explicit FAILED)
-> append existing local forensic mirror
-> truthful worker telemetry, with full qualification unavailable.

The verifier uses the **supplied existing shared SystemDataPort** and its fabric.
It does not create private THESEUS, OVID, SQLite or a new domain actuator.
The existing production constructor has no verifier configured: certification is
UNAVAILABLE until the producer integrations below are implemented and deployed.
This is intentional truth, not evidence that healing actuation is fail-closed.

The local JSONL ledger is explicitly labelled `LOCAL_MIRROR_NOT_CANONICAL_THESEUS`.
Its history is preserved, including old success claims. Old claims cannot restore
current certification after restart. Full canonical history replay remains missing.

## Authority map (preserved)

| Authority | Owner |
| --- | --- |
| Healing, bounded optimisation, planning, evaluation | SALAMANDER |
| Security, governance, policy bounds, privileged authorisation | AL HARAS |
| Intelligence orchestration | EUCLID |
| Mining and predictive/causal intelligence | PYTHIA |
| Execution fabric | CHRONUS |
| VQC execution and algorithm identity | TURING |
| Durable custody and restoration | THESEUS |
| Organisation, indexing and query state | OVID |

The new verifier reads authorisation; **it does not obtain authorisation for existing
actuators**. Missing authorization integration is an open material defect, not solved
by an evidence check. Temporal improvement remains distinct from causal attribution.

## Canonical observation contract

`RuntimeObservation` records observation_id, subject, tenant, source_subsystem,
metric, observed_value, expected_range, timestamp_ns, evidence_class, provenance,
source_commit, correlation_id. Evidence classes are OBSERVED, MEASURED, DERIVED,
PREDICTED, SIMULATED and UNAVAILABLE. Missing values are None, not zero. Non-finite
scalar values are refused. Only OBSERVED/MEASURED, pinned, fresh observations can
support this postcondition gate. Freshness is explicit deployment policy, not an
unexplained constant. Range/equality predicates require a separately custodied
PYTHIA contract; a proof producer cannot change the threshold in its observation.

This new structure is used by independent proof validation. Legacy health observations
are **not yet fully migrated** to this contract, so the global observation gate is unavailable.

## Producer schemas and missing integration

A recovery record seeking certification must carry recovery_id, tenant, subject,
action_id, action, resource, correlation_id, state=VERIFIED and proof_binding_id.
The state alone never qualifies.

The proof is `salamander.mining-outcome-proof/v1`, produced under PYTHIA's shared
port. It references three distinct bindings:

- AL HARAS: `salamander.action-authorization/v1` — bound action/resource/recovery,
  actor, tenant, risk, policy_version, decision, timestamp_ns, expires_ns.
- CHRONUS: `salamander.owned-action-execution/v1` — same identities, executed,
  evidence_class=OBSERVED, actuator_id, started_ns, completed_ns.
- PYTHIA: `salamander.independent-postcondition/v1` — same identities, verifier_id,
  verified result, observations, expected_vs_observed. Verifier and actuator differ.

All documents include tenant and exact source_commit. Each observation's contract_ref
resolves to `salamander.postcondition-contract/v1` under PYTHIA authority, binding
subject, metric and expected_range. All bindings must authenticate in the existing
shared fabric; all observations must follow action completion and be fresh. The
verifier additionally recomputes the predicate, rather than believing `verified=true`.

**The existing governor does not publish this document set. The runtime does not yet
supply the shared port to the bridge. Production certification is therefore unavailable.**
No missing document is manufactured; unit fixtures are expressly synthetic.

## Replacement ledger

| Existing behavior | Intended role | Replacement | Caller / compatibility | Old role / proof |
| --- | --- | --- | --- | --- |
| Reported VERIFIED -> SELF_HEALING | Certify actual recovery | Independent custodied proof and predicate evaluation | Existing MiningAutonomyBridge; optional verifier; producer fields retained | reported_state is OBSERVED; tested with status-only, corrupt, synthetic, stale and denied records |
| Deferred/proposed commands -> action_taken | Report execution | action_taken includes dispatched only; proposal/deferred retained separately | Existing runtime callback unchanged | Original intent retained; deferred-no-execution test |
| ACCEPTED / ROLLED_BACK -> SELF_OPTIMISING | Certify trial and restoration | Preserve reported fields; verification/causality/rollback UNAVAILABLE pending real trial voyage | Existing optimiser untouched | Trial/rollback observation only, not certification |
| Historical success -> current capability on restart | Restore evidence and knowledge | Preserve history; require fresh certification | Constructor/replay still reads old records | History is not current liveness; restart/tamper tests |
| Unknown non-error completion -> HEALTHY | Interpret execution health | No invented device-health contract; UNAVAILABLE unless actual fault | Existing observation path | Source completion retained; direct dimension assertion |
| Failed sink append advances evidence head | Durable evidence ordering | Sink succeeds before local records/head commit; nested payload deep-copy | Existing EvidenceLedger sink protocol | Failed append remains retryable; test checks head/records |

These are partial replacements of evidence behavior, **not proof of equivalent or stronger
end-to-end healing capabilities**. No production path is retired on their strength.

## Inventory status

`reports/salamander_component_inventory.json` records reviewed source findings and
keyword-search candidates with the requested inventory fields. It is explicitly
**INCOMPLETE**, not a complete component or reachability inventory. Static callers do
not prove executed production reachability. Unreviewed paths remain unreviewed, rather
than being labelled safe to obtain a green scanner.

Known open source defects include unmediated generic actions, heuristic applied=true
repair, producer-boolean governor verification, policy-state-only rollback, process-local
recovery/idempotency budgets and the non-canonical healing mirror. Real owning-subsystem
replacement, caller migration and proof must precede any retirement.

## Required delivery closure

Implemented here: observation/proof contracts; read-only custody/domain-bound outcome
verification; existing bridge integration; sink atomicity ordering; forensic restart
claim handling; focused adversarial tests; bounded planted-defect test runner; local
result/digest artifacts; truthful unavailable full qualification.

Not delivered: complete inventory, competing diagnosis/hypothesis selection, bounded
risk-ranked plans, authorisation at **all** actuators, owner-wide action registry
migration, independently verified rollback, controlled multi-objective optimisation,
durable budgets/circuits and escalation across restart, explicit full lifecycle,
canonical THESEUS/OVID healing history, context-aware learned recovery selection and
negative transfer, all API/service migrations, ten required critical-boundary mutants,
real mining/CHRONUS/TURING/custody voyages and full production-composition restart.

The five required end-to-end voyages (success, rejection/rollback, AL HARAS rejection,
budget exhaustion and optimisation regression) are **NOT EXECUTED**. A contract test
fixture is not a real fault, real mining execution, pool acknowledgement, or Bitcoin
consensus proof. Difficulty and acceptance logic are untouched.

## Local evidence and CI

Commands (repository root):

```bash
python -m unittest discover -s tests -p test_salamander_outcome_evidence.py -v
python -m pytest -q tests/test_salamander_autonomic.py tests/test_salamander_outcome_evidence.py
python scripts/salamander_evidence_mutation.py
```

The mutation runner uses isolated temporary copies and bounded subprocess timeouts,
never live production state. Initial run: 6 killed, 1 survived. The survivor showed
that aggregate UNAVAILABLE hid an invented healthy execution dimension. The test was
strengthened to check the dimension itself; final run: all 7 killed. Both artifacts
are retained. This is a test-system repair, not completion of the ten mandated mutants.

Local source/result digests are in `reports/salamander_increment_evidence.json`.
These are **LOCAL_CONTRACT_TEST** evidence. Only the focused source subset was fetched;
the full repository/build/platform/frontend/security gauntlet was not executed.

GitHub check-run retrieval for PR #134 returned 403 (`Resource not accessible by
personal access token`). Combined statuses were pending with zero reported statuses.
This does **not** establish that runner jobs executed zero steps. CI execution evidence
is UNAVAILABLE, not PASS and not an implementation failure. The included focused CI
workflow has not been independently qualified.

## External blockers versus unfinished implementation

External: the connection lacks check-run visibility; no isolated deployed production
mining/policy/custody environment was supplied or qualified for fault injection.
These do not excuse unfinished implementation listed above. Missing governance must
make actuation unavailable in the final replacement; no keys/tokens are in evidence.

## Machine-readable verdict

`reports/salamander_closure.json` contains all sixteen requested counters. Global
counts remain null/UNKNOWN rather than invented zeros. It includes known material
source findings and twelve unavailable qualification gates. The conjunction of
verified qualification gates computes false. Capabilities removed in **this diff**: 0.
That scoped fact is not asserted as a repository-wide historical count.

## Consolidation safety work (not production closure)

The existing AL HARAS adapter now re-reads the genuine guardian audit chain and
binds an action receipt to tenant, actor, resource, operation, exact payload,
policy version and signed entitlement expiry. Each receipt can dispatch once.
The registry requires a bound canonical authorizer; arbitrary ALLOW dictionaries
and `require_authorization=False` cannot authorise actuation. Outstanding grants
have an explicitly configurable finite admission budget.

The existing control plane serializes execute/recover operations, scopes
idempotency to tenant/actor/key and circuits to tenant/target/handler, rejects
changed requests using the same idempotency key, and conservatively rejects
re-dispatch when an earlier proposed action has no committed result. Recovery
budget reservations and circuit state are recorded before/after the relevant
work and reconstructed from a supplied, verified EvidenceLedger. Exhaustion
records escalation. Deadlines are checked between plan steps.

**Ledger reconstruction is not proof of canonical durable custody.** The normal
factory still defaults to process-local evidence. THESEUS/OVID integration, real
shutdown/fresh-process replay and storage-failure voyages remain unresolved.

Unit tests use genuine repository AL HARAS signing/admission/audit but unit
actuators and probes. Neither those fixtures nor the synthetic custodied-fabric
contract fixtures qualify a production voyage. Mutant runners test the unit
boundaries; they do not qualify owner-composition, hardware, mining or custody.

### Material repository work still open

- Normal EUCLID/mining/ProductionOrganism factory migration and verifier injection.
- Owning subsystem publication of all independent proof schemas.
- Full first-class diagnosis/planning/control state machine and complete inventory.
- Pre-actuation required-rollback validation and all affected-owner restoration.
- Canonical durable reservations, history/query, idempotency/circuit replay and
  learned context-dependent decisions through THESEUS/OVID.
- Real-component mining, CHRONUS, TURING, custody, rejection/rollback, denial,
  budget-exhaustion and optimisation-regression voyages.
- Production-composition planted defects and machine-computed final readiness.

These are not external dependencies. Neither completion condition A nor B has
been achieved. Historical reports are not evidence for a later source head.
Current-head local evidence is published separately after the source commit to
avoid self-referential source-head claims.
