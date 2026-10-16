# PHILOS EQS: measured native execution

Status: implemented and locally tested; draft review, not production/independent certification.
Base: PR75 `81c8c4ef178aae8f349262cbe6c53b1222cb106d`.
Review branch: `feat/philos-measured-eqs-20261014`, stacked on PR75 (not a replacement of Phi-2 history).

## Contracts and execution

Preserve the existing `ReproductionProtocol.steps`, `seed_suite`, manifest/environment hashes,
`required_observables`, candidate snapshots, `qualify(...)`, and native outcome classes.
The submitted action_sequence/compute_id-field/TelemetrySigner constructors do not exist in
this source. No replacement candidate model or alternate learner was introduced.

Supported native step dictionaries:

```python
steps = (
    {'action': 'init_state', 'args': {'accumulator': 1, 'previous': 1}},
    {'action': 'lucas_step'},
    {'action': 'lucas_step'},
    {'action': 'modular_invariant', 'args': {'modulus': 10007}},
    {'action': 'assert_observables',
     'expected': {'accumulator': 3, 'invariant_residue': 110}, 'tolerance': 0},
)
```

The final assertion checks state, never writes expected values into it. Unknown actions,
invalid parameters, missing outputs, any divergent trial or invariant breach fail closed.
`statistical_tolerance` remains a reproduction-rate contract, not an absolute output tolerance;
absolute numerical tolerance belongs to the assertion step. Every observable needs an explicit
numeric/boolean expectation. Empty protocols do not reproduce a claimed label by echoing it.
The two-step example is tested for actual state output; that is not an emergence discovery claim.

`StandardSyncExecutor` / `RealSubstrateExecutor` executes actual state transitions in-process.
`AsyncIsolatedExecutor` creates a fresh `python -I engine.py` process, exchanges JSON only,
checks exit status/timeout, and retains actual worker PIDs. It is synchronous orchestration of
a fresh worker, not asynchronous concurrency, a container, remote hardware or an OS security sandbox.
Both use independent per-trial state. Elapsed and trial latency use perf_counter_ns.
Generic execute_run now requires real decide/act/observe implementations rather than fabricated
observations or fallback decisions. The JSON worker refuses arbitrary Python architecture objects;
a measured serialization/provider adapter for those objects remains missing, not out of scope.

Stability is calculated from numeric output trajectories across N repeated trials *within each
seed*, using the minimum coordinate score, sample sigma and `1 - sigma/(abs(mu)+1e-12)` clipped
at zero. abs(mu) extends the requested nonnegative-mean formula safely to signed coordinates.
Latency is reported separately, never substituted for output stability. Exact integer state is
retained; Decimal statistics avoid implicit Float32/Float64 output downcasts. At least two
repetitions are required. Explicit bounded host execution budgets fail unavailable, not successful.
These are execution budgets, not architectural capability ceilings.

## Host configuration and three gates

No production keys are created implicitly. Configure each executor with its host-owned Ed25519
private key; configure EQS `registered_substrates` with `RegisteredSubstrate` objects binding:
properties-derived substrate ID, distinct public key, actual backend, engine artifact digest,
environment digest, manifest digest and base repetitions. The protocol's manifest/environment
must match registration. Environment digest binds interpreter version, OS, machine and engine
artifact; it is not a complete dependency/container image attestation. Registrations and all
trusted code/private keys remain host authority. Do not accept trust keys from candidate payloads.

1. Gate 1 requires two registered IDs with divergent properties AND divergent measured backends.
   Signed results must match the invoked substrate, fresh challenge, full candidate fingerprint,
   complete protocol, properties, registered artifact/environment and all raw trial evidence.
   EQS rechecks observable results and derived metrics. Worker PID separation is checked. Each
   substrate requires a distinct key; metadata labels or a MEASURED marker alone are insufficient.
2. Gate 2 invokes the actual executor at ceil(N * margin), margin >=1.5, and checks every repetition's
   outputs/invariants and real trial time against the expanded compute budget. Five repetitions
   become eight, not seven. It reports untested noise, latency injection and parameter-bound corners
   explicitly; this is repetition-load/compute-budget stress, not whole-envelope certification.
3. Gate 3 reconstructs complete telemetry windows from the verified current runs, verifies their
   exact signed payloads, measures normalized Shannon entropy over executed action traces and
   suspends above the host threshold (maximum .85). Existing invariant/action-distribution monitor
   checks also run against the declared protocol action profile, not an invented success scalar.
   This is action-mix entropy, not thermodynamic/neural entropy or proof of emergent intelligence.
   It is an execution-window check, not evidence of future/production behavioral stability.

Omitting a legacy pre-recorded window requests these current authenticated windows; an explicitly
supplied empty/foreign/incomplete window refuses. `QualificationCase` remains frozen and retains
real executors; PR75's adapter now maps its default absent window to this measured-run path.
The adapter keeps native QUALIFIED/REJECTED/SUSPENDED outcomes and independently_qualified=false.
Actual canonical dispatch still requires PR74. No entitlement, AL HARAS grant, learner or deployment
is created by this change. The canonical PR74/PR75 joint-runtime suite was not rerun here.

## Result receipts and admission

PR75's external, single-use invocation GovernanceToken and public-only QualificationAuthorization
remain unchanged. Their authorization precedes execution, retains persistent SQLite replay custody,
and invalid/replayed authorization still raises InvalidGovernanceTokenError.

Configure a separate explicit `QualificationReceiptIssuer` on EQS with host signing key, issuer,
audience and bounded TTL. No default authority or silent ephemeral signer. Result receipts sign
schema/operation, candidate ID/full fingerprint, gate-artifact digest, audience, nonce and integer
time window. `QualifiedEmergent.certification_token` remains a string, now containing the signed
JSON receipt. `qualification_receipt`, `gates_digest`, `gate_3_monitoring` are additive fields.
`governance_signature` now contains the *result receipt* signature, not a copied invocation signature.
Old hash-only certificates are not accepted as receipts. Receipt issuance conveys no rights itself.

A downstream host must call `QualificationReceiptAdmission.consume(...)` before an admission effect:

```python
admission = QualificationReceiptAdmission(
    trusted_issuers={'eqs-results': receipt_public_key},
    audience='admission', replay_path=protected_replay_path,
    is_active=eqs.is_receipt_active,
)
admission.consume(outcome.qualification_receipt, candidate=candidate,
                  gates_digest=outcome.gates_digest)
```

This public-key verifier checks scope/signature, host-active receipt status, expiry, rollback,
and durable SQLite BEGIN IMMEDIATE replay consumption. Concurrent/restarted verifiers admit once;
no refund for a subsequent failed admission effect. Suspension/requalification makes older receipts
inactive. Missing in-memory qualification status after service restart refuses: authoritative
qualification-state restore/custody integration remains missing, not silently reconstructed.
PR75's constituent dispatch adapter serializes the receipt; it does NOT auto-admit/promote it.
Wire the consumer explicitly where production promotion is authorized; this patch grants no rights.

## Evidence and remaining work

`python scripts/verify_philos_measured.py` and `python -O scripts/verify_philos_measured.py`:
85 tests passed in each mode; zero failures/errors/skips. 43 new measured tests + 19 existing
external authorization tests + 23 custody tests (13 snapshot and 10 migrated service cases).
Success paths execute real native actions, subprocesses, Ed25519 and SQLite. Negative attack
cases use deliberate tampering/patching, never success-path qualification doubles.

The scoped runner supplies namespace package paths to bypass unrelated package initializers; all
subject modules are actual MCP-retrieved/patched source. This is not full package startup, installed
artifact, canonical runtime dispatch, Windows, device assurance or independent review. Full pytest
command failed with `No module named pytest`; legacy pytest migrations were compiled, not executed.
Compilation/tabnanny passed. Exact logs/source hashes are retained in sibling validation files.
The original test caller for a decision-only mock architecture now expects honest observation-provider
refusal; real JSON-isolated architecture serialization remains missing.

No full dependency/image provenance, authenticated initial discovery, malicious-host resistance,
physical substrate attestation, distributed replay consensus, backup-rollback resistance,
continuous production-window verification, OVID custody convergence or mandatory CI/security
sign-off is claimed. Signing in the parent process authenticates trusted-host custody of measured
worker output; it is NOT independent worker attestation. No production keys, deployment, live
network/mining/submission, merge, scope reduction or protected mathematical/consensus changes.
