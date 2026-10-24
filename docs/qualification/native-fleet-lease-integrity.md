# Native fleet lease integrity qualification

## Source and scope

Repository: `HYBAPHI/HYBAEnterprise`. Base main: `5a49a742f5b68d4e96900cd1b2295e812136f04c`.
This increment preserves the six-phase stack, fleet capacity planner and Lucas implementation. Native quantum computation remains mathematical and substrate-agnostic; no physical GPU/iGPU/QPU is required or awaited.

This is a focused source-component qualification. The local runner explicitly bootstraps package namespaces and executes the actual fleet/host/scaling source; it does not exercise eager product initializers, installed wheels, full facade composition, OS process isolation, distributed transport or deployment. Sources retrieved through GitHub MCP were tied to the base commit; no local git checkout/remote change is claimed. Changes are pushed through GitHub MCP to the destination repository.

## Reproduced defects and fixes

1. **Kernel execution preceded lease validation.** Worker execution now binds tenant, worker, work id, fencing token, deadline, partition extent and input length before calling the kernel. A post-execution freshness check refuses an expired result. This does not undo side effects of arbitrary caller kernels or authenticate remote callers; use canonical authority and transaction boundaries for mutations.
2. **Incomplete result binding.** Scheduler registration now requires the currently registered worker object and binds lease id, work id, worker, generation, tenant, partition, backend, output length and recomputed output SHA-256. Mutable payload changes fail verification; a matching digest is not independent semantic proof of the kernel.
3. **Invalid deadlines/budgets and non-monotonic rotation.** Leases reject non-finite deadlines, non-integer partitions and non-positive or non-integer budgets. Expiration includes deadline equality. Generations must increase, rotation cannot reuse the current/revoked token, and failed rotation does not revoke the live worker.
4. **Cross-tenant idempotency collision.** Scheduler history is tenant-scoped. The process-local result ledger refuses a same-work-id/same-digest collision from another tenant instead of accepting it as idempotent. The ledger remains globally work-id keyed and conservatively rejects collisions rather than implementing tenant-keyed durable storage.
5. **Misleading runtime claims.** Worker and custody docstrings now state the actual in-process/in-memory boundary. `FleetCustody` does not currently write to Theseus or survive restart. ONE is a logical device contract; no physical accelerator dependency was added. Generic kernels report zero established SHA-256d evaluations rather than using item count as mining work.
6. **Unsafe legacy fixtures.** Duplicate/tenant fixtures now execute the lease on its actual scheduler-assigned worker. This preserves their original duplicate/tenant assertions while closing acceptance of foreign-worker leases. Invalid leases have separate adversarial regressions.

## Fresh execution

Environment: CPython 3.13.14, pytest 9.1.1, Linux x86-64. No hardware-accelerator prerequisite or dependency.

```sh
python docs/qualification/fleet_local_source_runner.py
python -O docs/qualification/fleet_local_source_runner.py
```

- **52 passed** normal Python.
- **52 passed** optimized Python, with pytest's standard warning that assertions outside rewritten test modules/plugins are disabled. New security/scaling predicates use explicit raising checks; runtime guards do not rely on `assert`.
- Nine changed Python files pass `black --check`.
- Initial adversarial subset against unmodified base: **31 failed, one passed**. This subset predates the additional three security and eleven scaling regressions; it is not the final suite denominator.
- Final suite: six existing fleet-core regressions, 35 adversarial/security regressions, eleven Lucas scaling regressions.

Retained raw logs and source SHA records: `docs/qualification/evidence/native-fleet-lease-integrity/`.

## Lucas scaling evidence and next execution work

`ScaledPlan` is actual executable streaming: `effective_items = min(base_items * L_n, address_limit - start)`, bounded chunks, contiguous coverage and no overlapping address ranges. Every declared rung (10, 12, 15, 18, 20, 31, 50, 76, 110) is checked against an independently iterated Lucas recurrence with bounded address-domain tests. This preserves the value of native Lucas scaling without treating a larger logical address plan as a measured physical-throughput multiplier.

The capacity planner currently reports `effective_scaled_items` but allocates/executes input partitions over `workload.total_items`; its formal clock/CU/lane capacity is declared model capacity, not a host measurement. The fleet runner currently executes workers serially in process, rotates/reconstructs the same logical worker for injected failover and uses an in-memory ledger. A future implementation must explicitly bind streamed scaled work to actual execution, approved resource vectors, durable custody and measured concurrent capacity. Do not silently expand caller input semantics or reinterpret a plan certificate as measured throughput. No Lucas implementation was replaced or reduced to a physical-attachment requirement.

## Owner evidence versus agent reruns

The owner supplied: six-phase stack commit `08e98f57`, fleet commit `5a49a742`, 100 stack/release checks, 30 fleet/stack checks plus 66 subtests and drift-sentry pass. Main at the supplied fleet commit and the relevant modules were independently verified through MCP. The owner's reported suites are preserved as owner evidence; they were not rerun or relabelled as this increment's 52 tests.

## Release decision

**This increment closes the reproduced local lease/result-binding defects. It does not establish whole-system production readiness.** Still unverified by this run: actual installed artifact/dependency closure, full software-stack/release gates, drift sentry, AL HARAS authentication/entitlements and durable pre-mutation audit, Theseus persistence/restart, actual multiprocess/distributed execution, peak resource enforcement, fleet load/fault/soak/SLOs and hosted CI.

Deterministic Merkle/SHA certificates verify embedded plan consistency; they are not an AL HARAS grant, external signature, measured-capacity certificate or durable custody receipt. No merge, deployment, publication, physical accelerator purchase or live mining activation is performed.
