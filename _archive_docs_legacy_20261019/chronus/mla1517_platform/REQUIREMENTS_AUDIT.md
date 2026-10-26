# MLA1517 Session Requirements Audit

This matrix records the requirements expressed throughout the build session.
A requirement is **captured** only when it has a concrete implementation,
contract, test, or documented physical boundary. Unsupported claims are not
silently converted into product behavior.

## Captured requirements

| Requirement family | Concrete capture |
| --- | --- |
| Mathematics-native substrate | Exact Fibonacci, Lucas, Cassini, Zeckendorf, Q-matrix/fast-doubling, Pisot and extended algebra modules |
| MLA1517 identity | 11D state contract, scale 15→17, 32 lanes, 12 execution nodes, 20 Aethel nodes |
| M32 geometry | Fixed topology, nonce partitioning, warp ballot, prefix compaction, D7 routing |
| Z-Core | Fixed-point/LUT ROM generator and synthesizable SystemVerilog Z-Core |
| Progressive sieve | D2/D6 → D5 void/anchor → ballot → compaction → D3/D4 → D10 → D7/D8/D11 |
| Cassini integrity | C++/C11/RTL determinant validation and Aethel write gate |
| Aethel storage | Cache-line-aligned C11 SPSC ring, 20 persistent vertex files, D7 routing, cursors, recovery, query callback |
| Zero-copy boundary | C11 Path A/Path B publication, `/dev/shm`, explicit acquire/release visibility, mmap storage |
| Host bridge | C11 MMIO ABI, ctypes binding, staged CSR writes, commit acknowledgement |
| Pool bridge | Braiins primary, ViaBTC failover, legacy formatter, fail-closed negotiated-adapter boundary |
| Docker deployment | Coordinator, PRIME-DB, telemetry, Salamander services; shared IPC; UIO device; bind-mounted persistence |
| Telemetry | Versioned magic/seqlock snapshot, atomic counters, cursor dashboard feed |
| Salamander | 20 Hz loop, leaky bucket, hysteresis, 24-lane floor, nonce orphan ledger, probation/readmission, ACK-gated control |
| Agentic layer | Deterministic geometry, exact M32 invariants, measured transitions, commissioned SCM, observed counterfactual support |
| Language split | Python orchestration, C11 MMIO/ABI, C++ native throughput, SystemVerilog target RTL; Rust is optional and not the production path |
| Governance | Release gate, requirements audit, explicit unsupported-claim policy, reproducible archive and hashes |

## Explicit boundaries, not missing implementations

- Physical FPGA/ASIC execution requires synthesis, programming, and hardware
  bring-up. The RTL is a target implementation, not a software substitute
  for silicon.
- Docker, Rust, and target HDL toolchains are deployment-stage requirements;
  their absence does not justify inventing results.
- Public Stratum share validity requires the complete negotiated work template
  and independent pool verification. Cassini is an MLA1517 integrity seal,
  not a replacement for a pool's proof-of-work rule.
- Claims such as 10 EH/s, one device equalling 20,000 NVIDIA GPUs, unlimited
  capacity, or universal exponential speed are not mathematical identities.
  They remain prohibited until measured on the real workload and hardware.
- Verification tests are conformance checks. They are not presented as the
  deployed GPU's runtime behavior.

Run the executable audit with:

```sh
python scripts/session_requirements_audit.py
```

## Scope of this artifact

This document is a **requirements traceability audit**. Its presence checks are not a correctness proof and do not replace `scripts/behavioral_gap_audit.py`. The behavioral audit executes native adversarial tests for shared cursors, growth, spill retrieval, query-time Cassini filtering, seqlock snapshots, and per-lane Cassini fault telemetry, plus Python control-plane tests. Docker cross-container execution remains a deployment-host test because Docker is unavailable here.

Honest complexity note preserved from the agentic-workflow review: **If the rig is thermally stationary, well-modeled, and pool behavior is stable, a plain MPC with a hand-tuned thermal model will match this whole stack at 5% of the complexity.** The five-intelligence measured stack is justified only for non-stationary environments and must earn its complexity through measured operational value.
