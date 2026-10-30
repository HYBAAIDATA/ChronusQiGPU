# EUCLID — Physical Deployment & Recovery Systems Implementation Record

**HYBA | EUCLID**

<aside>

**Status: implemented, verified — 19 July 2026.** The Physical Node Deployment Specification, Probationary Recovery Path, and DAG-Based Chronicle Reconciliation are implemented and validated. All four deployment artifacts are specified. Three invariant verification tests (Probation Graduation, Probation Defalcation, Divergent Fork) all pass.

</aside>

## Part 1: Physical Node Deployment Specification

### 1. Container Specification (`deploy/Dockerfile`)

Multi-stage OCI-compliant build supporting the three-tier execution fallback:

- **Stage 1 (builder):** Compiles C-extensions for NumPy with ATLAS-optimized linear algebra
- **Stage 2 (runtime):** Minimal, hardened runtime with non-privileged `euclid` user, read-only source, environment variable `EUCLID_RUN_ENV=HARDENED_OCI` for dynamic hardware detection
- Exposes ports 8080 (IOP) and 9090 (telemetry bridge)

### 2. Hardened Sandboxing Policy (`deploy/seccomp-profile.json`)

Strict Seccomp filter with `SCMP_ACT_ERRNO` default action — all unlisted syscalls are blocked:

- **Allowed:** read, write, openat, close, fstat, lseek, mmap, mprotect, munmap, brk, rt_sig*, ioctl, pread64, pwrite64, select, poll, socket, connect, accept, sendto, recvfrom, setsockopt, getsockopt, fcntl, flock, nanosleep, getpid, getuid, getgid, geteuid, getegid
- **Blocked (default ERRNO):** execve, fork, sys_ptrace, and all other high-risk syscalls
- Supports x86_64 and AARCH64 architectures

### 3. Multi-Node Deployment (`deploy/docker-compose.yml`)

Two-node overlay network deployment:

- `organism_alpha` at 10.240.0.10, `organism_beta` at 10.240.0.11
- Read-only volume-mounted cryptographic keyrings (`alpha_keys`, `beta_keys`)
- `no-new-privileges:true` and custom seccomp profile per container
- Resource limits: 2 CPUs, 4GB RAM, with 1GB reservation
- Consensus threshold set via `CONSENSUS_THRESHOLD=0.67`

### 4. Host Telemetry Bridge (`euclid/telemetry_bridge.py`)

Maps physical hardware metrics to logical organ degradation:

| Condition | Threshold | New State |
| --- | --- | --- |
| Normal | mem < 90%, temp < 85°C | HEALTHY |
| Memory exhaustion | mem ≥ 90% | DEGRADED |
| Thermal throttle | temp ≥ 85°C | DEGRADED |
| Double fault | Both thresholds exceeded | DEGRADED |

**Epistemic Humility Loopback:** When the bridge reports DEGRADED, the organism drops effective_alpha to 0.236 or 0.146 and renegotiates running IOP contracts to match reduced compute capacity.

## Part 2: Probationary Recovery Path

### `ProbationaryRecoveryManager` (`euclid/reputation_recovery.py`)

Prevents the "congestion death spiral" — degraded nodes recover trust without compromising active consensus:

- **PROBATIONARY state:** Relegated to low-risk test dispatches only — locked out of active consensus
- **Φ₁-attenuated recovery:** Each successful test adds `0.05 × φ⁻¹ ≈ 0.0309` to reputation
- **Doubled penalty:** Any failure triggers immediate suspension with a `−0.40` reputation penalty
- **Graduation:** After `required_tests` successes and reputation ≥ `active_threshold`, node graduates to HEALTHY

### Test 1: Probation Graduation ✅

```
Node C: rep=0.25 (< 0.3) → PROBATIONARY
  Test 1 passed → rep=0.2809
  Test 2 passed → rep=0.3118  
  Test 3 passed → rep=0.3427 ≥ 0.3 → HEALTHY
```

### Test 2: Probation Defalcation ✅

```
Node D: rep=0.20 → PROBATIONARY
  Test 1 FAILED → rep=0.00, SUSPENDED
  Cannot re-enter probation (suspended nodes require operator clearance)
```

## Part 3: DAG-Based Chronicle Reconciliation

### `ReconcilableChronicle` (`euclid/chronicle_reconciliation.py`)

When a network partition heals, two diverging history branches are merged without deleting or mutating historical blocks:

- **Last Common Ancestor (LCA) detection:** Finds the most recent event hash shared by both chains
- **Divergent segment verification:** Cryptographically validates remote chain integrity (predecessor links + event hashes)
- **MergeChronicleEvent:** DAG node referencing both branch tips (local + remote) and the LCA — analogous to a Git merge commit
- **History preservation:** Remote divergent blocks are pulled into local history; no blocks are deleted or overwritten

### Test 3: Divergent Fork ✅

```
Shared history: E1 → E2 → E3 → E4 → E5 (LCA at E5)
Chain A fork: E5 → A6 → A7
Chain B fork: E5 → B6 → B7

Reconciliation:
  LCA detected: E5 ✅
  B6, B7 integrity verified ✅
  Merge event created: links A7 (branch A tip) + B7 (branch B tip) ✅
  Final chain: 10 events (E1-E5, A6-A7, B6-B7, merge) ✅
```

## Canonical Files

| File | Purpose |
| --- | --- |
| `deploy/Dockerfile` | Multi-stage OCI container build with hardened runtime |
| `deploy/seccomp-profile.json` | Syscall-level sandboxing policy |
| `deploy/docker-compose.yml` | Two-node overlay network deployment |
| `euclid/telemetry_bridge.py` | Physical-to-logical degradation mapping |
| `euclid/reputation_recovery.py` | Probationary recovery with φ₁-attenuated steps |
| `euclid/chronicle_reconciliation.py` | DAG-based partition healing with LCA detection |

## Claim Boundaries

- Deployment specifications are production-ready architecture — not deployed on physical infrastructure
- Seccomp profile blocks high-risk syscalls but is not a substitute for full kernel hardening
- Telemetry bridge uses simulated metrics; production requires `psutil` for real hardware sampling
- Reputation recovery uses φ₁-attenuated step sizing; recovery rate is mathematically specified but not independently validated
- Chronicle reconciliation handles single-fork scenarios; multi-fork cascades require recursive reconciliation

</content>