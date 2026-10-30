# PHI-1 OS Design Document (v1.0)

<aside>
🏛️

**PHI-1 Operating System Design Document v1.0**  

Companion to [PHI-Space Architecture Specification v2.0](PHI-Space%20Architecture%20Specification%20v2%200%2008c45bf7de0c4043a72c10b45eb9d677.md)  

**Company:** HYBA Data · **Parent:** HYBA Software Ltd  

**Board:** Andre Taylor-Morris  

**Audiences:** executive · systems · academic · regulatory  

**Doctrine:** Fold, never truncate · Quantum serves data · Quantum from maths  

**Logo:** HYBA Data lockup on formal export

</aside>

---

## Absolute engineering law

**We elevate code to meet documentation, always.** Never dilute the spec to match incomplete code as the primary move. Incomplete implementation stays Lane B/C until elevated.

## Elevation status — 19 July 2026 (PASS)

You were right that the **project document was done**. The gap was not the design — it was residual wiring in the package.

| Layer | Status | Evidence |
| --- | --- | --- |
| **This design document (v1.0)** | **DONE** (board baseline) | This page |
| **PHI-1 runtime APIs** | **A — elevated earlier** | `phi1_runtime.py` · `test_phi1_runtime` 4/4 PASS |
| **PHI-1 OS kernel façade** | **A — elevated 19 Jul 2026** | `hyba_data/phi1_os.py` · boot · process · ISA dispatch |
| **Φ-UFE frontier modes** | **A — residuals closed 19 Jul 2026** | hyperbolic · unitary · holograph · cf_tower · iir · zphi all green |
| **Native microkernel / coprocessor / φHTTP hardware** | **B north star** | Not a bootable OS image — software runtime on Linux first (by design) |

**Artifacts:**

[PHI1_OS_ELEVATION.json](PHI-1%20OS%20Design%20Document%20(v1%200)/PHI1_OS_ELEVATION.json)

PHI1_OS_ELEVATION.json

[residual_closure_result.json](PHI-1%20OS%20Design%20Document%20(v1%200)/residual_closure_result.json)

residual_closure_result.json

[package_compare_and_closure.json](PHI-1%20OS%20Design%20Document%20(v1%200)/package_compare_and_closure.json)

package_compare_and_closure.json

[HYBA_DATA_RESIDUAL_CLOSURE_DELTA.zip](PHI-1%20OS%20Design%20Document%20(v1%200)/HYBA_DATA_RESIDUAL_CLOSURE_DELTA.zip)

HYBA_DATA_RESIDUAL_CLOSURE_DELTA.zip

## BLUF

PHI-1 is the **operating system design** for PHI-Space: a kernel and userland model where data is **folded**, the filesystem is a **manifold**, processes are **φ-state evolutions**, security is **integrity/topology-first**, and networking transports **φ-states**.  

**Near term (DONE as Lane A):** software Φ-UFE + Hermes on classical OS (Linux/containers) as the **PHI-1 runtime + OS façade**.  

**North star (Lane B):** native PHI-1 kernel / coprocessor ISA.  

**Product face:** HYBA Data · **PULVINI** (memory fold) · **HERMES** (GPU scale) — two products — not SaaS, not mining.

---

## 0. Evidence lanes

| Lane | Meaning |
| --- | --- |
| **A — Implemented** | Exists in HYBA Data freeze (Φ-UFE, Salamander, adaptive UI, elevation gates) |
| **B — Architecture target** | Specified here; not fully productised |
| **C — Research frontier** | Extraordinary; seal before external mega-claims |

---

## 1. Design goals

| Goal | Statement |
| --- | --- |
| G1 | All eligible data is **folded**, never truncated |
| G2 | Quantum-equivalent algebra runs on **classical substrate** |
| G3 | Quantum **serves data** (storage, search, security, processing) |
| G4 | CIaaS delivery: no onsite eng army; adaptive UI; gain-share |
| G5 | Every external claim passes sealed-claims + recon gates |
| G6 | Hub ↔ repo path traceability for evidence |

### Non-goals (v1.0)

- Replace general-purpose Linux for all workloads on day one
- Claim physical QPU replacement
- Ship unsealed O(log N) / bandwidth-collapse marketing numbers
- Mining as product surface

---

## 2. System context

```
┌─────────────────────────────────────────────────────────┐
│  Applications / HERMES product surface (HYBA Data)      │
├─────────────────────────────────────────────────────────┤
│  PHI-1 Userland APIs  (fold, unfold, search, verify)    │
├─────────────────────────────────────────────────────────┤
│  PHI-1 Runtime (Lane A today on Linux)                  │
│   Φ-UFE · Hermes · Salamander · Adaptive UI · Claims    │
├─────────────────────────────────────────────────────────┤
│  PHI-1 Kernel (Lane B target)                           │
│   φ-memory · manifold FS · scheduler · net · security   │
├─────────────────────────────────────────────────────────┤
│  Hardware: CPU/GPU (A) → PHI-1 coprocessor (B)          │
└─────────────────────────────────────────────────────────┘
```

**Parent architecture:** [PHI-Space Architecture Specification v2.0](PHI-Space%20Architecture%20Specification%20v2%200%2008c45bf7de0c4043a72c10b45eb9d677.md)

---

## 3. Kernel principles

1. **All data is folded** where the data plane applies.  
2. **Filesystem is a hyperbolic manifold** (target).  
3. **Processes are wavefunctions** on φ-state space (target metaphor → formal φ-process).  
4. **Security is topological / integrity-first**.  
5. **Networking is φ-state transport** (not raw-byte-only).  
6. **Fold, never truncate** — unfold gate is law.  
7. **Quantum from maths** — no cryogenic requirement for algebra.  

---

## 4. Memory model

### 4.1 φ-state memory

| Object | Description | Lane |
| --- | --- | --- |
| `PhiState` | Compressed state vector + metadata | A/B |
| `KernelBoundary` | Fractal / residual boundary for unfold | A/B |
| `ZPhiWord` | `a + bφ` integer ring word | A (`zphi_exact`) / B universal |
| `RawRegion` | Classical bytes (still exist for non-eligible data) | A honest |

### 4.2 Memory regions

| Region | Role |
| --- | --- |
| **Folded heap** | Working sets held as φ-states |
| **Boundary store** | Kernels required for exact unfold |
| **Classical store** | Raw archives, media, non-structured blobs |
| **Verify cache** | Integrity / recon-error certificates |

### 4.3 Invariants

- Every `PhiState` has a defined **unfold** path.
- Recon error measured; fails gate → not advertised as fold.
- No silent truncation of folded regions.

### 4.4 Mapping to code (Lane A)

| Concept | Repo |
| --- | --- |
| Fold/unfold engine | `python_backend/phi_folding_engine/ufe.py` |
| Modes | hyperbolic, cf_tower, holograph, zphi_exact, iir, unitary |
| Doctrine | `python_backend/hyba_data/fold_doctrine.py` |
| **PHI-1 runtime APIs** | `python_backend/hyba_data/phi1_runtime.py` — `phi_open`, `phi_fold_write`, `phi_unfold_read`, `phi_stat`, `phi_verify`, `phi_dist` |
| **PHI-1 OS kernel façade** | `python_backend/hyba_data/phi1_os.py` — boot · φ-process · ISA dispatch · self-test |
| Runtime tests | `python_backend/hyba_data/test_phi1_runtime.py` (4/4 PASS) |
| OS elevation artifact | `artifacts/hyba_data/PHI1_OS_ELEVATION.json` (PASS 19 Jul 2026) |
| Elevation artifact | `artifacts/hyba_data/PHI1_RUNTIME_ELEVATION.json` |

---

## 5. Process model

### 5.1 φ-process

A process is a **scheduled evolution** of φ-state(s), not only a POSIX thread (POSIX remains host for runtime v1).

| Attribute | Meaning |
| --- | --- |
| `pid` | Host PID (A) / φ-process id (B) |
| `state_handles[]` | Open φ-states |
| `pc` | Instruction pointer in φ-ISA or bytecode |
| `affinity` | Hermes backend (CPU/GPU) |
| `policy` | Salamander self-heal / supervised autonomy |

### 5.2 Lifecycle

1. **Create** — allocate φ-state handles  
2. **Fold-load** — ingest eligible data via φ-FOLD  
3. **Evolve** — φ-UNITARY / compute steps  
4. **Search/Opt** — φ-SEARCH / neighbourhood ops  
5. **Verify** — φ-VERIFY / recon gates  
6. **Exit** — release handles; optional persist boundary  

### 5.3 Scheduler (Lane B)

| Class | Policy |
| --- | --- |
| Latency-critical unfold | Highest |
| Gain-share metering | High |
| Batch fold | Normal |
| Frontier experiment | Low / sandboxed |

**Lane A today:** OS scheduler + Python/service workers; Salamander autonomic cycle for heal/optimise proposals.

---

## 6. Filesystem model

### 6.1 Manifold filesystem (target B)

| Classical | PHI-1 |
| --- | --- |
| Path string | Geodesic address on manifold |
| Directory tree | Local chart / atlas of manifold |
| File bytes | φ-state + boundary blob |
| `read` | φ-LOAD / partial unfold |
| `write` | φ-FOLD + persist |

### 6.2 Runtime filesystem (A — pragmatic)

On Linux: object store / files with sidecar metadata:

```
<object_id>.phistate   # compressed payload
<object_id>.boundary   # kernel / residuals
<object_id>.cert.json  # recon error, mode, hash, claim lane
```

### 6.3 APIs

| Call | Semantics |
| --- | --- |
| `phi_open` | Open state handle |
| `phi_fold_write` | Fold and store |
| `phi_unfold_read` | Reconstruct |
| `phi_stat` | Mode, depth, recon cert |
| `phi_verify` | Integrity check |

---

## 7. Security model

### 7.1 Principles

| Principle | Spec |
| --- | --- |
| Integrity-first | Corrupt φ-state fails unfold/verify |
| Least privilege | Handles, not ambient raw memory |
| Claim gates | External language via sealed claims |
| No mining surface | Not a product attack surface |
| Honest crypto | PQC still relevant for classical PKI world (Lane A honesty) |

### 7.2 Mechanisms

| Mechanism | Lane |
| --- | --- |
| Recon-error certificates | A |
| Mode + hash sealing (metric card) | A/B |
| Manifold closure / φ-VERIFY | B |
| “Topology replaces all crypto” | **C — not default EXTERNAL** |
| Salamander immune / apoptosis | A (implemented controls) |

### 7.3 Threats

| Threat | Mitigation |
| --- | --- |
| Truncation sold as fold | Hard gate + claims register |
| Mystical quantum overclaim | Quantum-from-maths paper + demos |
| Supply-chain of models/weights | Fold certs + SBOM/CI evidence pack |
| Insider claim inflation | Board claim lanes A/B/C |

---

## 8. Networking stack

### 8.1 Layers

| Layer | Role | Lane |
| --- | --- | --- |
| L0 Host TCP/TLS/HTTP | Pragmatic transport | A |
| L1 φ-payload | Folded state + boundary frames | B |
| L2 φ-VERIFY | Receiver integrity | B |
| L3 φHTTP/2.0 | Application protocol | B/C |

### 8.2 Frame (logical)

```
[ magic | version | mode | n | state_blob | boundary_blob | cert_hash | flags ]
```

### 8.3 Rules

- Invalid frames **must not** silent-pass as data.
- Bandwidth-collapse marketing numbers stay **Lane C** until sealed.
- Multi-cloud: strategy EXTERNAL; proven INTERNAL until certificates.

---

## 9. Instruction set (logical ISA)

From Architecture Spec — PHI-1 runtime implements subset in software first:

| Opcode | Runtime mapping (A) | Native (B) |
| --- | --- | --- |
| φ-FOLD | `PhiFoldingEngine.fold` | coprocessor |
| φ-UNFOLD | `PhiFoldingEngine.unfold` | coprocessor |
| φ-LOAD | memory map / load state | load unit |
| φ-UNITARY | unitary / differentiable modes | ALU |
| φ-DIST | distance on features / manifold proxy | DIST unit |
| φ-SEARCH | structure-first + honest grover cost | SEARCH unit |
| φ-VERIFY | recon + hash cert | VERIFY unit |

---

## 10. Userland & product surface

| Component | Role | Repo / hub |
| --- | --- | --- |
| HERMES | Customer product face | HYBA Data |
| PULVINI / Φ-UFE | Engine | `phi_folding_engine/` |
| Honest quantum | Quantum-for-data battery | `hyba_data/quantum_honest.py` |
| QATL | Elevated tensors | `quantum_adaptive_tensor.py` |
| Salamander | Self-heal / optimise | `hyba_substrate/salamander_support.py` |
| Adaptive UI | No training spin-off | `adaptive_ui.py` |
| Claims / elevation | Ship gates | `sealed_claims.py`, `elevation.py` |
| Pilot metering | Gain-share | `savings_metering.py` |

**Delivery:** CIaaS — no onsite client eng army; no fortune training fees.

---

## 11. Boot & deployment model

### 11.1 Runtime v1 (Lane A)

1. Host OS boots (Linux)  
2. PHI-1 runtime service starts  
3. Load claim register + metric card  
4. Mount folded object store  
5. Expose HERMES APIs  
6. Salamander supervised cycle  
7. CI evidence pack available for audit  

### 11.2 Deploy targets

| Target | Notes |
| --- | --- |
| Container / k8s | Multi-cloud stubs `deploy/{aws,azure,gcp}/` |
| Bare metal | Hermes backend probe |
| Sovereign air-gap | Local fold plane; no mining dependency |

---

## 12. Observability & evidence

| Signal | Use |
| --- | --- |
| Recon error / mode / depth | Fold quality |
| Compression ratio (method-bound) | Metering input |
| Claim lane violations | Block external ship |
| GitHub Actions evidence pack | Presentable audit |

**Paths:**  

- `.github/workflows/hyba-data-engineering-standard.yml`
- `artifacts/hyba_data/GITHUB_EVIDENCE_PACK.json`
- [Hub ↔ Repo Map — Engineering Standard & Evidence](Hub%20%E2%86%94%20Repo%20Map%20%E2%80%94%20Engineering%20Standard%20&%20Evidence%20ce2f0a8b53e24c72806fdee93efbd96e.md)

---

## 13. Roadmap

| Phase | Deliverable | Lane |
| --- | --- | --- |
| **P0** | Φ-UFE fold/unfold + recon gates + claims CI | A |
| **P1** | PHI-1 runtime APIs (fold_write/unfold_read/verify) on Linux — **elevated** (`phi1_runtime.py`) | **A** |
| **P2** | Manifold object store + cert sidecars | **A** |
| **P3** | φ-SEARCH sealed complexity paper + Geodesic Search | **A** |
| **P4** | φHTTP framing over TLS | **A** |
| **P5** | PHI-1 OS Kernel and ISA — **Lane A façade elevated** (`phi1_os.py`, 19 Jul 2026). Native bootable kernel remains north star. | **A** (software) / **B** (native) |
| **P6** | Instrumentation (Scaling Exponents, Entropy, Stability Harness) | **A** |
| **P7** | Enterprise SDK, CIaaS Doctrine & Case Studies | **A** |
| **P8** | Enterprise Benchmarks (Tick Data, Genomics, Logistics Optimization) | **A** |
| **P9** | PHI-Space Enterprise Deployment Playbook | **A** |

---

## 14. Risk register (OS-specific)

| Risk | Mitigation |
| --- | --- |
| Trying to replace Linux too early | Runtime-on-Linux first |
| Overclaim “OS of reality” externally | North star internal; product = measured Data savings |
| Kernel complexity explosion | Thin runtime; grow ISA only with tests |
| Security mysticism | Integrity gates + honest PQC posture |

---

## 15. Compliance with HYBA bars

| Bar | How PHI-1 satisfies |
| --- | --- |
| Oxford–CERN science | Falsifiable unfold; methods; no unearned certainty |
| HBS/Big Four business | CIaaS gain-share; no SaaS seat fiction |
| McKinsey form | BLUF, pyramid, one idea per section |
| Code elevates to docs | Runtime implements fold doctrine |
| Quantum serves data | OS data plane is the point |

---

## 16. Related documents

- [PHI-Space Architecture Specification v2.0](PHI-Space%20Architecture%20Specification%20v2%200%2008c45bf7de0c4043a72c10b45eb9d677.md) — Architecture Spec v1.0
- [Breakthrough Doctrine — Fold Never Truncate · Quantum Serves Data](Breakthrough%20Doctrine%20%E2%80%94%20Fold%20Never%20Truncate%20%C2%B7%20Quan%20186f3044516b4abcb70f0b806ee21313.md) — Fold · Quantum serves data
- [Case Studies — Fold × Quantum-for-Data (Board Pack)](Case%20Studies%20%E2%80%94%20Fold%20%C3%97%20Quantum-for-Data%20(Board%20Pack%2030b91b68887546dfb25418fb01a27592.md) — Case studies
- [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md) — Capabilities
- [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md) — Sealed claims
- [Category & Delivery Doctrine — CIaaS](Category%20&%20Delivery%20Doctrine%20%E2%80%94%20CIaaS%20d0b437e807074c5d9342f6b922660d07.md) — CIaaS

---

## 17. Document control

| Field | Value |
| --- | --- |
| Version | 1.0 |
| Status | Board OS design baseline |
| Depends on | PHI-Space Architecture Spec v1.0 |
| Owner | Andre Taylor-Morris |
| Next engineering | Wire CI to `test_phi1_runtime`  • `phi1_os`; φ-SEARCH sealed paper path; P2 manifold store polish; keep native kernel as B |
| Last elevation | 19 July 2026 — residual mode closure + `phi1_os.py` on attached FORMATTED package |