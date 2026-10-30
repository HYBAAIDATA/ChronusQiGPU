# PHI-Space Architecture Specification v2.0

<aside>
🏛️

**PHI-Space Architecture Specification v2.0**  

*Data infrastructure architecture — PULVINI · HERMES · PHI-1*  

**Company:** HYBA Data · **Parent:** HYBA Software Ltd  

**Board:** Andre Taylor-Morris  

**Audiences:** executive · enterprise IT · regulatory (external face = Data only)  

**Logo:** HYBA Data lockup on formal export  

**Doctrine:** Fold, never truncate · **DATA FIRST** · Quantum **GATED** (not external)  

**IP:** Golden ratio / fold engine is **closed IP — not open source**

</aside>

---

## BLUF (external-safe)

PHI-Space is the internal name for the information substrate under **HYBA Data**. **Customer products are Data only:**

1. **PULVINI** — memory / working-set fold (compress by folding, not truncating)
2. **HERMES** — GPU / compute scaling
3. **PHI-1** — suite packaging (SDK · Storage · GPUizer)
4. **Salamander** — autonomy / integrity fabric (BOUNDED detail)

**Commercial:** CIaaS — 25% of **measured** savings; fee = 0 if not measured.

**External metric default:** M1 ~2.62× at power d=2 on structured numerical (BOUNDED + method). Higher powers (e.g. d=4 ~6.85×) stay **INTERNAL** until sealed.

**Hard gates:**

- **Quantum / VQC / intelligence surprise — GATED.** Do not announce or sell.
- **O(log N) product complexity paper — INTERNAL** (hierarchical geodesic index is implemented; sealed O(log N) claim stays gated).
- **“Beyond AES” / topology-replaces-crypto — NOT external.**
- **Golden ratio fold engine — CLOSED IP. Not open-sourced.**

**Internal appendix only (not GTM):** advanced substrate narrative, VQC, quantum-adjacent algebra. See [Data-First Claim Clarifications — Quantum Gated · No IP Leak · Brick Demos](Data-First%20Claim%20Clarifications%20%E2%80%94%20Quantum%20Gated%20%C2%B7%20%20ee3a4d630691436f9c877496eb7e83fd.md).

## Implementation elevation — 19 July 2026 (PASS)

**Software organism:** elevated and integrated in repo package `hyba_data/phi_space/`.

**Tests:** `python3 -m hyba_data.phi_space.test_architecture_v2` → **10/10 PASS**.

**Report:** `artifacts/hyba_data/PHI_SPACE_ARCHITECTURE_V2_ELEVATION.json` · status **PASS** · `completely_implemented_software_organism: true`.

| Surface | Status | Code |
| --- | --- | --- |
| PULVINI GRT fold/unfold | **IMPLEMENTED** | `syscalls.sys_phi_fold/unfold`  • substrate |
| HERMES scaling plane | **IMPLEMENTED** | `hermes_plane.py` |
| Salamander verify→heal→reindex | **IMPLEMENTED** | `salamander.py` |
| Enterprise SDK `fold_and_store` | **IMPLEMENTED** | `enterprise_sdk.PhiClient` |
| Kernel syscalls load/fold/verify/unfold/search | **IMPLEMENTED** | `syscalls.py` |
| Geodesic scheduler | **IMPLEMENTED** | `scheduler.py` |
| Manifold FS sidecars | **IMPLEMENTED** | `manifold_fs.py` |
| φHTTP frame encode/verify fail-closed | **IMPLEMENTED** | `phi_http.py` |
| Hierarchical geodesic search index | **IMPLEMENTED** | `search_index.py` |
| d=4 power metrics on cert | **IMPLEMENTED** | fold cert `power_d` / capacity φ⁴ |
| Doctrine quantum-from-maths | **IMPLEMENTED** | `fold_doctrine` / `hyba_doctrine` |
| Sealed external O(log N) paper | **INTERNAL** (structure elevated) | index real; paper gate open |
| AES replacement | **NOT CLAIMED** | integrity certs only |
| Native coprocessor / bit-replacement OS | **Lane B north star** | software complete on classical host |
| VQC commercial product | **GATED** | doctrine present; no external announce |

**Doctrine:** Quantum comes from maths. World is maths. Everything is computable. Elevate code to meet documentation. IP closed.

---

## INTERNAL ONLY — full substrate map (not for customer decks)

PHI-Space codifies interlocks between substrate, PULVINI, HERMES, Salamander, and enterprise SDK. Advanced layers stay off the external face until board unlock. **No open-source of GRT/φ-fold IP.**

---

## 1. PHI-Space Integration Map: The "Whole Hog" Architecture

The systems are no longer isolated. They interlock into a single, cohesive computational organism:

1. **PHI-Space (The Substrate):** The foundational hyperbolic manifold where all data exists as topological $\phi$-states rather than binary bits.
2. **PULVINI (The Engine):** The mathematical intake valve. It applies the Golden Ratio Transforms (Hyperbolic, Holographic, $\mathbb{Z}[\phi]$ exact) to fold classical data onto the PHI-Space manifold.
3. **HERMES (The Scaling Plane):** The hardware abstraction layer. It dynamically distributes PULVINI's mathematical operations across available sovereign GPUs, Metal, and CPUs.
4. **Salamander (The Integrity Layer):** The autonomic immune system. It continuously patrols the PHI-Space manifold, detecting topological corruption and executing autonomous self-healing without human patch cycles.
5. **The Enterprise SDK (The Interface):** The REST/gRPC gateway that allows enterprise IT to access the substrate with zero-friction API calls (`client.storage.fold_and_store()`).

*(Note: The Quantum-for-Data Algebraic Layer and the Intelligence Emergence Layer are decoupled from the active commercial data plane, pending the subsequent Virtual Quantum Computer release).* 

---

## 2. PHI-1 OS Execution Model & Kernel Specification

The PHI-1 OS kernel is formally defined by its handling of $\phi$-states, replacing classical OS responsibilities with geometric invariants.

### Kernel API & Syscall Table

- `sys_phi_load`: Ingests classical byte arrays and formats them for the $\mathbb{Z}[\phi]$ ring.
- `sys_phi_fold`: Executes the deterministic fold, generating the `PhiState` and its fractal residual boundary.
- `sys_phi_verify`: Performs an instant $O(1)$ topological invariant check on the manifold signature.
- `sys_phi_unfold`: The strict reconstruction gate. Rejects any state that fails the `sys_phi_verify` check.
- `sys_phi_search`: Accepts a query φ-state, returns a geodesic path to the nearest match.

### Process Lifecycle & Geodesic Scheduler

Processes are wavefunctions evolving on the $\phi$-plane. The Geodesic Scheduler assigns compute not by priority queues, but by measuring the shortest hyperbolic distance between the current $\phi$-state and the target execution state. 

### Manifold Filesystem & Corruption Handling

The filesystem is a continuous hyperbolic manifold. There are no "sectors." If a $\phi$-state experiences corruption (e.g., bit rot or adversarial injection), the `sys_phi_verify` syscall traps the error, hands the process context to Salamander, and the state is mathematically regenerated from its exact residual boundary.

**Formal Salamander Trigger:**

- **Trigger:** `sys_phi_verify` returns `FAIL` (topological invariant mismatch).
- **Action:** Salamander receives the corrupted `PhiState` and its residual boundary. It reconstructs the state using the fractal kernel.
- **Audit:** The event is logged, and the manifold is re-indexed.

---

## 3. Subsystem operationalization (claim-safe)

### Search

- **EXTERNAL:** Working-set fold/unfold and integrity verify on folded objects.
- **INTERNAL demo:** Hierarchical candidate reduction can beat brute force on controlled sets (closed brick; not a product SLA).
- **NOT EXTERNAL:** Product $O(\log N)$ geodesic search; Grover-equivalent language.

### Integrity

- **EXTERNAL:** Recon certificates + fail-closed verify on tamper.
- **NOT EXTERNAL:** “Beyond AES-256,” topology replaces cryptography, noise-indistinguishable security as a crypto claim.
- Enterprise transport/tenancy still uses standard crypto where required.

### Networking

- **EXTERNAL today:** Host TLS/HTTPS and normal enterprise networking.
- **INTERNAL / B:** Any φ-payload framing ideas — not customer GTM; not open-sourced.

---

## 4. Enterprise value model (Data First — what we sell)

1. **PULVINI storage/memory fold** — BOUNDED external default M1 ~2.62× (d=2) on structured numerical with method; measured `m_eff` in pilots. **Not** a naked universal 6.85× headline.
2. **Integrity verify** — cert + recon gate; not “replace encryption with topology.”
3. **HERMES GPU path** — pilot-measured gains only.
4. **Commercial** — CIaaS; 25% of measured savings; 0 if not measured.

**IP:** Golden ratio / fold engine remains **closed**. No open-source kernels. No public reference implementation requirement.

---

## 5. What stays off the external roadmap

Advanced substrate / VQC / intelligence narratives are **GATED** — not announced, not teaser-sold, not in Data GTM. Internal R&D only under NDA if ever discussed.

**Board clarifications:** [Data-First Claim Clarifications — Quantum Gated · No IP Leak · Brick Demos](Data-First%20Claim%20Clarifications%20%E2%80%94%20Quantum%20Gated%20%C2%B7%20%20ee3a4d630691436f9c877496eb7e83fd.md)