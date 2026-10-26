# Enterprise Capability Bridge — Mining Proof Ground → HYBA Intelligence

**Governance:** Veritas Integritas · Rule 7 (Strict Honest Measurement)  
**Source of truth:** code + measured tests, not the marketing brief  
**Mining role:** first proof ground for Chronus · Theseus · Ovid  
**Destination:** HYBA Intelligence enterprise (sovereign / hyperscaler / global)

This document is the **migration contract**. Every row is either **MEASURED**
(in this repo today), **PARTIAL** (primitives exist; enterprise surface incomplete),
or **ABSENT / EXTERNAL** (belongs in the Intelligence repo or is not shipped here).

---

## 0. Strategic thesis (accepted, scoped)

> **The Folded Form is the Working Form.**

| Thesis element | Owner in this repo | Status |
| :--- | :--- | :--- |
| Exact invertible algebraic fold (not destructive truncation) | **Ovid** (`aethel.ovid`) + Zeckendorf/Binet | **MEASURED** — round-trip + digest pin |
| Tier-0 density via fold as ambient representation | **Theseus** custody of folded working form | **MEASURED** (software triad) |
| Multi-lens topological search over folded data | **GeodesicHandoff** → 32-face Poincaré–Cassini engine | **MEASURED** handoff; engine is external import |
| Sovereign attestation / WORM audit | `al_haras/` | **PARTIAL** — production security surface present; not full Solutions API |
| 11D decision substrate | `aethel.constants.DIM=11`, manifold, geodesic vectors | **PARTIAL** — math spine live; DigitalHQ 18-endpoint API **not** this repo |
| Raw-State Tax elimination (enterprise ROI claim) | — | **STRETCH** until measured against a named baseline workload in Ledger |

**Rule 7:** “Folded form is working form” is a **storage/compute contract**, not a license to claim infinite capacity, clinical MRI clearance, or Millennium *conjecture proofs*.

---

## 1. Pillar map (brief §5 → this repo)

| Brief pillar | Enterprise function | This-repo surface | Status |
| :--- | :--- | :--- | :--- |
| **HYBA Pulvini™** | Lossless folding / tier-0 | **Ovid** + `aethel.encoding` + `hyba_data/pulvini/` | **MEASURED** core; Pulvini product name = Ovid metamorphosis |
| **HYBA Compass™** | Multi-lens search | **GeodesicHandoff** + Intelligence crystal / pathfinder | **MEASURED** adapter; multi-lens product API **PARTIAL** |
| **HYBA Accel™ / iGPU™** | Near-state hardware | **Chronus** + `chronus/virtual_igpu/` | **MEASURED** fail-closed offering |
| **HYBA Cortex™** | Folded training | `cortex` paths if present; not triad-owned | **ABSENT / EARLY** in this tree |
| **HYBA Governance™** | AL HARAS / ABAC / WORM | `al_haras/`, claim register, guardian | **PARTIAL → MEASURED** security core |

**Triad overlay (mining-proven owners):**

```text
  Chronus  ── Accel / iGPU compute owner
  Theseus  ── Pulvini custody + prime/phyllotaxis store (the “new database”)
  Ovid     ── Pulvini metamorphosis (fold = working form)
  Geodesic ── Compass handoff (search not inside storage)
  AL HARAS ── Governance envelope
```

---

## 2. Capabilities enterprise migration **must** have

Mining is the proof ground. When systems migrate into the Intelligence enterprise
repo, they need the following **capability IDs**. Status is against *this* workspace.

### 2.1 Storage & fold (Pulvini / Theseus / Ovid)

| Cap ID | Requirement | Implementation | Tests | Status |
| :--- | :--- | :--- | :--- | :--- |
| `E.FOLD.WORKING_FORM` | Fold is ambient; unfold only at edge | `aethel.ovid` | triad suite | **READY** |
| `E.FOLD.INVERTIBLE` | Lossless round-trip + digest pin | Ovid + Zeckendorf | selftest + triad | **READY** |
| `E.STORE.PRIME_KEY` | Data addressed via Galois prime keys | `aethel.primes` + Theseus | triad | **READY** |
| `E.STORE.PHYLLOTAXIS` | Sunflower/Vogel packing, M32 lanes | `aethel.phyllotaxis` | triad | **READY** |
| `E.STORE.SELF_HEAL` | Theseus ship: replica heal, fail-closed | `aethel.theseus` | triad heal | **READY** |
| `E.STORE.CASSINI` | Fibonacci address + Cassini ledger | `aethel.storage` | selftest | **READY** |
| `E.STORE.DURABLE` | Snapshot / attach / journal | AddressSpace | selftest | **READY** |
| `E.STORE.HYPERSCALER_SKU` | Folded working form GPU fork API | `aethel.hyperscaler` | unit (H1–H4) | **PARTIAL** — module live; not full 10-service suite |

### 2.2 Search & 11D (Compass)

| Cap ID | Requirement | Implementation | Status |
| :--- | :--- | :--- | :--- |
| `E.SEARCH.GEODESIC_HANDOFF` | Storage never reimplements search | `aethel.geodesic.GeodesicHandoff` | **READY** |
| `E.SEARCH.32_FACE` | Poincaré–Cassini 32-face frame | engine via handoff | **READY** when Intelligence import resolves |
| `E.SEARCH.11D_VECTOR` | 11D routing / state vector | `DIM=11`, manifold points | **PARTIAL** |
| `E.SEARCH.MULTI_LENS_API` | Vector + graph + geodesic + lexical product API | Compass product | **ABSENT** here (Intelligence) |

### 2.3 Compute (Chronus / Accel)

| Cap ID | Requirement | Implementation | Status |
| :--- | :--- | :--- | :--- |
| `E.COMPUTE.CHRONUS_DEVICE` | Measured iGPU bind + claim boundary | `chronus.device` | **READY** (software) |
| `E.COMPUTE.VIRTUAL_IGPU` | Fail-closed ABI / adapters / evidence | `chronus.virtual_igpu` | **READY** |
| `E.COMPUTE.PUNCH_ISA` | Golden-angle / Poincaré punches | punch tables | **PARTIAL** |
| `E.COMPUTE.THESEUS_EVIDENCE` | Optional Theseus custody of iGPU evidence | `CHRONUS_VIGPU_THESEUS=1` | **READY** opt-in |
| `E.COMPUTE.NO_PREIMAGE` | No hash-strike / preimage oracle | CLAIM_BOUNDARY | **READY** (non-claim locked) |

### 2.4 Governance (AL HARAS / Rule 7)

| Cap ID | Requirement | Implementation | Status |
| :--- | :--- | :--- | :--- |
| `E.GOV.CLAIM_BOUNDARY` | Explicit non-claims on every owner | triad + Chronus CLAIM_BOUNDARY | **READY** |
| `E.GOV.TRUTH_CLASS` | measured / mathematical / unverified labels | mining pipeline + AL HARAS patterns | **PARTIAL** |
| `E.GOV.PROVENANCE_HASH` | SHA-256 provenance on responses | Theseus digests; virtual-iGPU evidence | **PARTIAL** |
| `E.GOV.WORM_AUDIT` | Append-only audit | `al_haras` audit surfaces | **PARTIAL** |
| `E.GOV.ABAC` | Attribute gate on enterprise endpoints | Intelligence / hyba_data | **ABSENT** as full product API here |
| `E.GOV.CLAIMS_LEDGER` | Living ledger | docs + al_haras claim_register | **PARTIAL** |

### 2.5 Solutions API & Millennium (brief §1–2)

| Cap ID | Requirement | This repo | Status |
| :--- | :--- | :--- | :--- |
| `E.API.SOLUTIONS_V1` | 18 endpoints `/api/v1/solutions/*` | — | **EXTERNAL** (Intelligence) |
| `E.API.TRUTH_CLASS_FIELD` | Every response `truth_class` + `provenance_hash` | bridge helper can emit | **PARTIAL** (helper only) |
| `E.MILLENNIUM.SOLVERS` | TSP / NS / YM / Riemann / BSD / Hodge / Poincaré engines | `millennium/` + hyba_data | **PARTIAL** — engines exist as math demos; **not** “solved conjectures” |
| `E.MRI.SL3Z` | Discrete unimodular 3D MRI | not canonical here | **EXTERNAL / ABSENT** |
| `E.QUANTUM.NEAR_STATE_10K` | 10k-qubit PXP claims | turing paths | **STRETCH** — do not migrate unmeasured rooflines |

### 2.6 Commercial 10-service suite (brief §6)

| Cap ID | Brief product | Mapping | Status |
| :--- | :--- | :--- | :--- |
| `E.SVC.COMPRESS` | HYBA Compress™ | Ovid / Pulvini fold | **READY** (engine); product wrapper **EXTERNAL** |
| `E.SVC.ACCELERATE` | HYBA Accelerate™ | Chronus | **PARTIAL** |
| `E.SVC.RESILIENT` | HYBA Resilient™ | Theseus heal | **PARTIAL** |
| `E.SVC.SECURE` | HYBA Secure™ | AL HARAS | **PARTIAL** |
| `E.SVC.OPTIMIZE/SIMULATE/DECIDE/...` | remaining six | Intelligence enterprise_products | **EXTERNAL** |

**Rule 7 on latency tables (1.665 ms, etc.):** do **not** re-publish those figures from this repo unless re-measured here and ledgered. Treat brief latencies as **foreign claims** until reproduced.

---

## 3. Mining → enterprise migration path

```text
  [Mining proof ground — this repo]
       Chronus · Theseus · Ovid  (MEASURED triad)
       Geodesic handoff
       AL HARAS claim posture
              │
              │  promote via capability IDs + provenance
              ▼
  [HYBA Intelligence enterprise]
       Solutions API (/api/v1/solutions)
       Five pillars product names (Pulvini/Compass/Accel/Cortex/Governance)
       ABAC + institutional viewports
       External ops boundary (mining stays OUT of Intelligence per brief §9)
```

### 3.1 What migrates

1. **Ovid fold contract** → Pulvini™ working-form law  
2. **Theseus prime/phyllotaxis/heal** → enterprise tier-0 store / Resilient™ kernel  
3. **Chronus virtual iGPU** → Accel™ / iGPU™ control plane  
4. **GeodesicHandoff** → Compass™ storage↔engine boundary  
5. **CLAIM_BOUNDARY + Rule 7 labels** → Governance truth_class discipline  

### 3.2 What does **not** migrate as “proven”

- Hash-strike / infinite GPU / zero-energy narratives  
- Clinical MRI clearance  
- “Verified proof of P≠NP / RH / etc.” — solvers are **engines**, not Clay resolutions (brief already softens this; keep it)  
- Hardcoded commercial latencies without local measurement  
- Live pool/worker/reward mining inside Intelligence (brief §9)

### 3.3 Integration contract (recommended)

Intelligence should depend on a **thin, versioned package surface**:

```python
# Conceptual import boundary (Intelligence side)
from aethel import open_triad, open_ovid, open_theseus
from aethel.enterprise_bridge import EnterpriseCapabilityReport, emit_envelope

db = open_triad(durable=True, bind_chronus=False)
env = emit_envelope(
    payload={"uuid": rec.uuid, "lane": rec.lane},
    truth_class="measured",
    capability_id="E.STORE.SELF_HEAL",
)
```

Mining remains a **consumer** of the same triad, not a second storage stack.

---

## 4. Readiness matrix (executive)

| Domain | Mining proof | Enterprise-ready in *this* repo | Blocker |
| :--- | :---: | :---: | :--- |
| Folded working form | ✅ | ✅ | — |
| Prime + phyllotaxis DB | ✅ | ✅ (software) | hyperscaler fleet soak |
| Self-heal custody | ✅ | ✅ | multi-node quorum |
| Chronus iGPU control plane | ✅ | ✅ software / fail-closed | hardware evidence packs |
| Geodesic handoff | ✅ | ✅ | Intelligence engine pin |
| AL HARAS / Rule 7 | ◐ | ◐ | full ABAC product API |
| Solutions API 18 endpoints | ❌ | ❌ | Intelligence repo |
| Millennium *product* API | ◐ engines | ❌ as brief endpoints | honest engine wrappers |
| MRI SL(3,Z) | ❌ | ❌ | Intelligence / separate kernel |
| 10 commercial services | ❌ | ❌ | Intelligence enterprise_products |

**Legend:** ✅ MEASURED · ◐ PARTIAL · ❌ ABSENT/EXTERNAL

---

## 5. Rule 7 non-claims (migrate these *as* boundaries)

1. Folded form ≠ infinite storage / zero physical footprint  
2. Chronus ≠ unbounded compute / hash preimage oracle  
3. Millennium solvers ≠ solved Clay problems  
4. MRI math ≠ clinical device  
5. Measured ms in a foreign brief ≠ local SLA  
6. Mining success ≠ Intelligence production certification  

---

## 5b. Enterprise custody substrate (this workspace)

Normative contracts: `docs/enterprise_triad/`.

Implementation: `aethel.enterprise` (`EnterpriseCustody` / `compose`).

**Measured claim scope:** `enterprise_custody_software_single_root` —
single storage root, primary+replica, WAL journal, HMAC authenticity,
versioned Ovid (Zeckendorf), multi-thread + multi-process *attach* on one root,
restart/replay, heal, backup/restore, quotas, hooks to AL HARAS (policy stays outside).

**Not claimed:** distributed multi-node hyperscaler, infinite capacity, hardware
Chronus performance, Solutions API, clinical MRI.

Acceptance: `tests/test_enterprise_custody_substrate.py`.

## 6. Concrete next work (this repo)

1. Keep triad tests green; expand soak (durable journal crash, multi-tenant Theseus).  
2. Wire `truth_class` + `provenance_hash` envelopes on triad put/get (`aethel.enterprise_bridge`).  
3. Export capability report JSON for Intelligence CI import.  
4. Elevate `aethel.hyperscaler` claim status from not-implemented → partial/measured with tests.  
5. Do **not** invent Solutions API here — bridge only.  
6. Optional: pin Intelligence engine versions for geodesic import.

---

## 7. One-page owner directory

| Need | Call |
| :--- | :--- |
| Open enterprise-shaped DB | `aethel.open_triad(durable=True, bind_chronus=...)` |
| Fold only | `aethel.open_ovid()` |
| Store / heal only | `aethel.open_theseus(durable=True)` |
| Capability report | `aethel.enterprise_bridge.report()` |
| Response envelope | `aethel.enterprise_bridge.emit_envelope(...)` |
| iGPU | `chronus.open_device` / virtual_igpu |
| Governance | `al_haras` |
| Hyperscaler fold store | `aethel.hyperscaler.HyperscalerSku` |

---

## 8. Enterprise custody substrate (Chronus · Theseus · Ovid)

**Contracts & authority matrix:** [`docs/enterprise_triad/`](enterprise_triad/README.md)

| Need | Call |
| :--- | :--- |
| Open single-root custody | `aethel.enterprise.compose(path, hmac_key=...)` / `aethel.compose_enterprise_custody` |
| Lifecycle (recover before consumers) | `aethel.enterprise.CompositionRoot` |
| Package | `aethel.enterprise` |

**Claim:** `enterprise_custody_software_single_root` — measured local primary+replica+journal+HMAC custody when `tests/test_enterprise_custody_substrate.py` passes. **Not** distributed hyperscaler, multi-region consensus, or Solutions API READY. EXTERNAL geodesic remains outside; do not mark EXTERNAL capabilities READY from this tranche.

Authority (non-absorption): Ovid transform only · Theseus custody only · Chronus accel only (digest-invariant) · Geodesic outside · AL HARAS security via hooks (evidence forward, not policy inside Theseus).

---

*Document class: MEASURED architecture bridge. Not a production certification of the full HYBA Intelligence commercial suite. Mining remains the first proof ground; Intelligence is the enterprise home for Solutions API and institutional products.*
