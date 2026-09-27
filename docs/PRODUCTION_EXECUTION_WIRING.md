# Production execution wiring

## Canonical path

`mining/production_miner.py` now defaults to:

```text
Stratum TCP/TLS
  -> subscribe
  -> authorize
  -> mining.notify
  -> validated job/target
  -> TOE provenance record
  -> AETHEL folded storage
  -> exact full-rank QuantumTensor coverage plan
  -> Tensor fold and lossless round-trip
  -> Lucas/Pisot Hendrix schedule (L76)
  -> iGPU hash pipeline
  -> independent SHA-256d/target recheck
  -> TOE provenance record
  -> submit only when live gates are explicitly enabled
  -> correlated pool result
```

The default is `PYTHIA_EXECUTION_PATH=aethel_hendrix`. `aethel` remains an
alias for the scaled adapter. `direct` is retained only as a conformance/fault
isolation path and is not the default production route.

## Scale contract

- `PYTHIA_VQC_QUBITS` defaults to `11`, matching the exact 2,048-state virtual
  register.
- `PYTHIA_HILBERT_MEMORY_BYTES` optionally sets the available state/data
  budget. If the full-rank state plus job payload does not fit, execution
  fails closed before hashing.
- `PYTHIA_HENDRIX_SCALE_INDEX` defaults to `76`.
- `PYTHIA_HENDRIX_WORKERS` defaults to `1`; each worker receives a disjoint
  partition of a complete deterministic nonce permutation.

## Pool lifecycle evidence

The following are separate evidence gates:

1. `connected`: TCP/TLS session established.
2. `authorized`: `mining.subscribe` and `mining.authorize` succeeded.
3. `job_received`: a validated `mining.notify` arrived.
4. `candidate_found`: an iGPU/backend candidate passed independent SHA-256d
   and target verification.
5. `submitted`: `mining.submit` was written only after the candidate and TOE
   gates passed.
6. `accepted`: the correlated pool response was `result: true`.

A job receipt is not a share. A submitted share is not an accepted share.
No accepted-share claim is valid without the pool response.

## Live submission safety

Live submission remains fail-closed unless all three controls are present:

```text
HYBA_ENABLE_LIVE_SHARE_SUBMIT=true
HYBA_LIVE_SHARE_APPROVAL_ID=<operator approval>
HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=true
```

Without those controls, the miner may connect, authorize, receive jobs, build
and search work, and report candidates, but it cannot submit to a real pool.

## Production readiness boundary

The implementation and focused tests are committed to PR #16. Hardware
OpenCL execution, Windows Docker deployment, authenticated pool connectivity,
and pool-confirmed acceptance still require execution on the target host. They
cannot be inferred from local source inspection or unit tests.
