# OVID / THESEUS / Chronus — gap closure

Date: 2026-10-19
Baseline: 5a4e120297d8106dfe1c1f8ba4d7e3baa913b43d
Constraint: ONE iGPU
Source: `docs/MLA1517_PRIME_DB_TRANSFER_NOTES.md` (entire transfer notes)

## Verdict

Software ownership and one-iGPU execution gaps in the Chronus · Theseus · Ovid triad are closed. Physical OpenCL, RTL/FPGA, live-pool, and performance gates remain open evidence, not software passes. Production-ready remains false.

## Closed

| ID | Gap | Closure |
|---|---|---|
| DOC-001 | Transfer notes not in the repo | Canonical document landed in entirety |
| TRIAD-001 / R01 | Durable authority inverted | OVID authority root; THESEUS projection rebuilds from OVID and can be deleted |
| R11 | Folded working-form verify incomplete | Digest, owner, sparse witness, and materialised SHA-256 are checked |
| R07/R08 remainder | Chronus tenant overwrite / eviction retains payload | Tenant-scoped handles already present; lookup returns a copy; eviction drops host payload; budget fails closed |
| CHRONUS-001 | Multi-iGPU ambiguity | `device_count` must be 1; fabric compose advertises one logical `chronos_igpu` |
| R06 device health | Any device object counted as bound/ok | Chronus `ok` requires a measured dispatch; unbound Chronus does not fail OVID |

## Still open (not code-closable here)

- Real OpenCL device execution and signed device identity
- HDL simulation / FPGA / silicon
- Authorized live-pool acceptance
- Reproducible hashrate / power / thermal measurements
- Remaining enterprise custody crash-window and concurrent-writer gates (R03–R06 journal/fsync)

## Ownership

- **OVID** — authoritative durable folded state
- **THESEUS** — rebuildable query/index projection bound to an OVID generation
- **CHRONUS** — ONE iGPU execution and measured evidence
- **PRIME-DB** — local/reference MLA1517 persistence, not enterprise system of record
