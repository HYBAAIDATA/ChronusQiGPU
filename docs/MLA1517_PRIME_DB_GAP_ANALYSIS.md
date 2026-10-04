# MLA1517 + PRIME-DB gap analysis

## Decision

The transfer notes are a mixed historical/specification record, not a single shipped-product manifest. This repository is the PYTHIA mining proof ground. It may carry Chronus/MLA1517 execution code and legacy PRIME-DB reference or local-persistence surfaces, but enterprise durable authority remains OVID and rebuildable query/index projection remains THESEUS.

## Closed in this change

| Gap | Closure | Evidence |
|---|---|---|
| Conflicting durable authority | Replaced PRIME-DB-as-authority wording with OVID authority and THESEUS/PRIME-DB projection semantics. | `CONTRACTS.md`, `al_haras/delivery_plan.py` |
| Shipped vs planned ambiguity | Classified enterprise product-platform sections as enterprise-only planned work, not mining-repository capabilities. | `manifests/mla1517_prime_db_gap_analysis.json` |
| Narrative-only review | Added a machine-readable ledger and regression test for ownership, refuted claims, and open physical gates. | `tests/test_mla1517_prime_db_gap_analysis.py` |
| Chronos v3.3 distribution gap | Already closed by merged PR #31: packaged facade/data and executable capability audit. | PR #31 |

## Verified software surfaces already present

- Exact integer rings, a no-float exact-core gate, exact Lucas/Pisot ladder logic, and an exact `Q(sqrt(2))` quantum path.
- M32 contracts for 32 logical lanes, 12 execution nodes, 20 memory nodes, and the 11D state model.
- Native PRIME-DB local persistence with bounded growth, cursor recovery, Cassini revalidation, overflow/backpressure handling, and telemetry ABI checks.
- `FoldContract` and `OperatorContract` surfaces, strict hardware fail-closed behavior, and live-submit approval gates.
- Transfer-note hypotheses are explicitly tested and not promoted when refuted: generic Zeckendorf bit reduction, Float64 Binet-only lossless storage, Lucas/Pisot phase speedup, and observable global phase effects.

## Open evidence gates — not code-closed

These remain open until evidence is produced on qualified targets:

1. Real OpenCL device execution and signed device identity.
2. HDL simulation, synthesis, timing closure, and FPGA/silicon execution.
3. Rust, CUDA/HIP, and Docker builds in the required toolchains.
4. Explicitly authorized live-pool acceptance at the announced target.
5. Reproducible hashrate, latency, power, thermal, and error measurements.

A missing device or toolchain is not converted into a pass. CPU/reference execution remains separately labelled and cannot stand in for device evidence.

## Scope exclusions

The transfer notes' enterprise platform roadmap—versioned datasets, multimodel query, cost/proof planning, uncertainty, privacy, QRAM/QDC, and the HYBA Flow/Ontology/Agent/Quality/Model/Document/Evidence/Share/Federate/Studio/Insight/Edge/Vault/Deploy/Guard services—is not promoted into this mining-only repository by this audit. Those services require the enterprise repository, separate authority review, and their own evidence gates.

## Non-negotiable boundaries

- OVID data survives; THESEUS is rebuildable from OVID.
- PRIME-DB names local/reference MLA1517 storage semantics here; it is not the enterprise system of record.
- The 11D substrate boundary is Float64 or exact integer unless a narrower device path is explicitly certified; no silent downcast is permitted.
- SHA-256d and target comparison remain the mining accept authority; pool acknowledgement remains required for a share.
- Refuted hypotheses and unmeasured physical/performance claims remain prohibited.
