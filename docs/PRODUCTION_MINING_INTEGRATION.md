# Chronus #107 production mining integration

## Canonical path

`IntelligentPoolCoordinator.search_current_job` remains the only production entrypoint:

`Stratum job/generation → immutable SearchPlan + nonce lease → dispatch certificate → ExecutionRouter → independent host SHA256d/target recheck → mining.submit → literal pool response`.

#107 does not create a second coordinator, Stratum client, hasher, target validator, evidence ledger, custody store, or Salamander governor.

## Chronus integration points

- **#104:** every plan/evidence record binds immutable corpus digest `0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712`.
- **#105:** route admission distinguishes software verification, device availability and physical execution. Device presence is never execution evidence.
- **#106:** the typed exact `PISOT_SCHEDULE` reference intrinsic proposes bounded conventional and Lucas/Pisot work-group candidates. It is advisory: legality and measured execution retain selection authority.
- **Evidence:** canonical JSON is SHA-256 addressed and appended to the existing causal/evidence surfaces. A plan is not a proof.

## Locked truth boundaries

- Work identity and staleness: existing Stratum adapter.
- Header, SHA256d, share/network target and candidate validity: existing proof adapter plus independent host recheck.
- Pool acceptance/rejection/unknown: literal pool response only.
- Physical route: existing `ExecutionRouter`; CPU/NumPy cannot masquerade as hardware.
- Custody: existing Aethel-derived exact implementations and causal/evidence ledgers.
- Recovery: existing `RecoveryGovernor`, entered at `IntelligentPoolCoordinator.apply_salamander_mode`; #107 only seals its mining-scoped state.

Float64 remains unsupported. An advertised `cl_khr_fp64` extension is not certification. OpenCL `BINET_EXACT` is unsupported. `FOLDED_NATIVE` remains open. Missing physical and live-pool evidence remain `PHYSICAL_EVIDENCE_REQUIRED` / `NOT_RUN`; missing CI remains `NOT_REPORTED`.

## Scope exclusion

This PR does not begin #108 and does not add substrate-wide autonomic control, OVID/THESEUS convergence, governed learning, or Kairos rehearsal. It makes no performance, revenue, profitability, ASIC synthesis, or unsupported physical-execution claim.

## Acceptance

```bash
python scripts/check_chronus107.py
```

The gate runs #106 (therefore #100–#105), validates the locked manifest, runs focused deterministic tests, regenerates the extended corpus, and emits a content-addressed acceptance record. Physical OpenCL and authorized live-pool gates stay explicit when unavailable.
