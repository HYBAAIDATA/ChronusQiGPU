# Chronus, OVID and THESEUS: unified execute–transform–custody system

This document records the maintained production composition.

## CHRONUS — execution

CHRONUS owns execution and resource coordination. Maintained execution surfaces include:
- `src/chronus/execution/` for workload execution and backend routing;
- `src/chronus/fleet/` for multi-machine scheduling, leases, verification, recovery and receipts;
- `src/chronus/tensor/` for tensor execution, selective resident-state materialisation and backend routing.

The reference route is always explicit. Physical accelerator routes must identify the actual device and fail closed when a requested device is unavailable.

## OVID — representation transformation and materialisation

`src/chronus/ovid/transform.py` provides a versioned reversible representation contract.

Every OVID representation records:
- transformation contract and version;
- source digest;
- representation digest;
- original length;
- encoded representation bytes.

Materialisation verifies both the representation digest and the final source digest.

The legacy content-addressed helpers under `src/chronus/security/ovid.py` remain compatibility utilities. They are process-local and are not the durable system of record.

## THESEUS — durable custody and continuity

`src/chronus/storage/durable.py` provides the production local custody path.

It uses SQLite WAL with full synchronous commits and supplies:
- content-addressed durable objects;
- tenant-scoped records;
- restart verification;
- digest-checked reconstruction;
- append-only hash-chained journal entries;
- journal continuity validation;
- checkpointing;
- concurrent-writer transactional admission;
- evidence and storage statistics.

`src/chronus/storage/theseus.py::TheseusService` remains the in-process compatibility implementation. Its process-local nature is explicit and must not be confused with `DurableTheseusService`.

## Production triad flow

`src/chronus/triad.py::ProductionTriad` composes the three authorities:

```text
input
  -> CHRONUS workload
  -> OVID versioned representation
  -> THESEUS durable commit + custody journal
  -> restart/replay
  -> OVID verified materialisation
  -> independently digest-checked output
```

The close-out regression proves transform → durable commit → restart → materialise without transferring durable authority to OVID.

## Existing structured storage

Phyllotaxis addressing remains available in `src/chronus/storage/phyllotaxis.py`. Existing authenticated workloads such as `PHYLOTAXIS_STORE`, `THESEUS_RETRIEVE` and `TRINITY_SCALE_FOLD_STORE` remain supported by their current service paths.

Their legacy in-process storage behavior does not substitute for the new durable production composition. Product paths that require durable custody should compose with `DurableTheseusService`.

## Qualification

Focused current tests:

```bash
python -m pytest tests/test_triad_production.py -q
```

Current test execution must be bound to the release SHA. Local durability does not by itself establish multi-region replication, a customer deployment, high availability or a physical-accelerator result; those are separately gated deployment capabilities.
