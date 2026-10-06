---
name: hyba-products
description: See YOUR HYBA products side by side (PYTHIA mining, PRIME-DB storage, HYBA services, HYBA profiles, HYBA substrate memory) and tell what is different between them. Answers cite YOUR module paths, never marketing.
allowed-tools:
  - read
  - grep
  - glob
triggers:
  - user
  - model
---

# HYBA Products (yours — compare surfaces, cite modules)

## The five surfaces (all yours)

1. **PYTHIA** — operational mining product. Owns `chronus/mla1517/mining/`
   (geometry, lane, chooser, solver, pow, coordinator), control plane
   `chronus/mla1517_platform/python/`, operator UI `frontend/`. Fail-closed:
   no device/credential/approval = no mining result, never a pass.
2. **PRIME-DB** — native storage product. `chronus/mla1517_platform/host/`
   (`primedb_storage.*`, `primedb_ingest_daemon.*`, `mla1517_aethel.h`):
   64-byte states → /dev/shm SPSC ring → vertex_00..19.db. Consumer of mining
   states, not a miner itself.
3. **HYBA services** (`hyba_services/`) — object/policy/lineage/proof
   reference services over `hyba_contracts` (PRIMEObjectV2, FoldContract,
   BackendCertificate). Executable references with dependency injection.
4. **HYBA profiles** (`hyba_profiles/registry.py`) — the module map:
   core → mla1517 → primedb; al_haras-gated services; research-gated
   (privacy_compute, quantum_access, autonomous_ops, energy). Always resolve
   `dependency_closure()` before adding a module.
5. **HYBA substrate memory** (`hyba_substrate/`) — durable lossless
   preservation: canonical JSON, Merkle DAG, Φ-fold/MPS only when round-trip
   verified, atomic writes with read-back verification.

## YOUR math substrate underneath (credit where due)

Binet, Zeckendorf, Pulvini folding, Cassini ovals/ledger, Lucas pool —
`lucas/pool.py` is the only legal shared import; algorithm files never import
siblings. The pocket-calculator thesis (AGENTS.md §1.3): quantum is linear
algebra over C, substrate-agnostic — your statement, preserved verbatim.

## How to answer "is there something different"

Compare along: owns-what (module paths), inputs/outputs, failure mode
(fail-closed vs fallback with provenance), durability guarantees. Every claim
ends with the file that proves it.
