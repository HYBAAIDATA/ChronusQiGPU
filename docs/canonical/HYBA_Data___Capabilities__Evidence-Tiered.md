# HYBA Data — Capabilities (Evidence-Tiered)

<aside>
🏛️

**HYBA Data** · Computational Intelligence as a Service (CIaaS)  

**Parent:** HYBA Software Ltd  

**Board authority:** Andre Taylor-Morris (sole shareholder & director)  

**Source:** Deployment freeze review 2026-07-15  

**Logo rule:** HYBA Data lockup only (not generic icons).  

**Rule:** Extraordinary claims require extraordinary proof. Fail the bar → does not leave the ecosystem.

</aside>

---

## BLUF

HYBA Data sells **infrastructure intelligence**, not SaaS seats. Hierarchy:

| Layer | Name | Role |
| --- | --- | --- |
| Company | **HYBA Data** | First-to-market company under HYBA Software Ltd |
| Product | **HERMES** | What the customer buys |
| Engine | **PULVINI** | φ-folding compression |
| Autonomy fabric | **Salamander** (+ meta-controller) | Self-heal / self-optimise |
| Category | **CIaaS** | Not SaaS, not MLaaS, not IaaS |

Commercial posture: **gain-share on measured savings** (doctrine: 25% of proven savings). **No maintenance fee** — nothing to maintain under self-healing model.

---

## Evidence tiers (mandatory)

| Tier | Meaning | External use |
| --- | --- | --- |
| **T0 — Designed** | Spec / architecture only | Internal |
| **T1 — Implemented** | Production code exists | Internal + technical annex |
| **T2 — Measured** | Reproducible internal benchmarks + tests | External **with method, data class, bounds** |
| **T3 — Customer-validated** | Named customer production evidence | Full commercial claim |

Nothing at T0/T1 ships as a customer “proven” number. T2 ships only with bounds. T3 required for paradigm-shift commercial claims.

---

## Capability catalogue

### 1. φ-Memory compression (PULVINI)

| Attribute | Sealed language |
| --- | --- |
| What it does | Folds structured numerical / φ-pattern working sets to raise effective memory capacity |
| What it is not | Universal compression of arbitrary data |
| Tier | **T2 BOUNDED** for M1 (harness-sealed); M2/M3 **INTERNAL**; customer fleet T3 open |
| Code evidence | `phi_folding_engine/` · `phi1_runtime.py` · `data_class_gate.py` · `sealed_metric_card.py` · fold fidelity + depth-4 tests |

**φ-power law (folding = compression control):** `reduction(d)=1−φ^{−d}`, `capacity(d)=φ^d`. Same system; change power `d` to move the ratio. Ref: [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md) · [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)

**Sealed metric card (power ladder — M1 harness sealed):**

| ID | Power d | Ratio | Data class | Loss / error | External status |
| --- | --- | --- | --- | --- | --- |
| **M1** | **2** (φ²) | ~**2.62×** capacity / ~61.8% W-reduction | Structured numerical | Near-lossless; harness max_error ≈ **1.7e-9** | **BOUNDED** — method + data class + **test_hash sealed** (`02b3c4ac…097cf19`) |
| **M2** | **4** (φ⁴) | ~**6.85×** / ~**85.41%** W-reduction | Structured workloads | W-law + kernels for RT; elevate d=4 harness | **INTERNAL** — same law as M1 at higher power; not a rival metric |
| **M3** | ≥4 measured | 7.155× commercial class | Savings framing | Mode + T3 | **INTERNAL** until T3 customer seal |

**Artifacts:** `artifacts/hyba_data/M1_SEAL.json` · `SEALED_METRIC_CARD.json` · `CAPABILITY_ELEVATION_CLOSURE.json`  

**External sentence:**  

*PULVINI applies φ-folding to structured numerical working sets under power d. M1 (d=2, ~2.62×) is BOUNDED with sealed harness hash and recon-error bound; M2 (d=4, ~6.85× / ~85.41% W-reduction) is the same law — elevate depth-4 seal. Customer savings invoiced only after production measurement under gain-share.*

---

### 2. Self-healing / self-optimisation (Salamander + autonomy)

| Attribute | Sealed language |
| --- | --- |
| What it does | Immune validation, sandboxed mutation (“dream”), economic pruning (apoptosis), resonance tuning; **online-gated** heal/optimize |
| What it is not | Magical zero-ops; heal/optimize while system offline; 99.999% without pack |
| Tier | **T2 implemented** (code + tests + online gate) |
| Code evidence | `salamander_support.py` · `system_runtime.py` (start/online) · `test_autonomy_fabric` · `test_capability_elevation` |

**Hard rule:** Self-heal and self-optimise **only when system is ONLINE** (`python3 -m hyba_data.system_runtime start`).  

**External sentence (safe):**  

*HYBA Data’s autonomy fabric implements self-healing and self-optimisation in software, gated to online runtime, with test coverage. Customer SLA language (including 99.999%) requires the sealed availability method pack plus long-window production evidence.*

---

### 3. CIaaS delivery model (not SaaS)

| Attribute | Sealed language |
| --- | --- |
| What it is | Autonomous infrastructure intelligence; gain-share economics |
| What it is not | Seat-based SaaS; maintenance subscriptions |
| Tier | **T2 hermetic metering** (formula + telemetry adapter); **T3** customer sign-off for production invoices |
| Code evidence | `savings_metering.py` · `pilot_telemetry.py` · `pricing_dashboard.py` · pilot protocol |

**Fee law in code:** `Fee = 0.25 × Measured_Savings`; **Fee = 0 if unmeasured.**  

**Artifact:** `artifacts/hyba_data/elevation/PILOT_TELEMETRY_MEASUREMENT.json`  

**External sentence (safe):**  

*HYBA Data is not SaaS. It is CIaaS: no maintenance charge; pricing is a share of measured savings only — hermetic pilot telemetry is wired; customer T3 requires signed production measurement.*

---

### 4. Multi-cloud service availability

| Attribute | Sealed language |
| --- | --- |
| Strategy | Service availability across major cloud providers |
| Tier | **T1 strategy + named runbooks**; **PROVEN production INTERNAL** until live certificates |
| Code / ops evidence | `deploy/{aws,azure,gcp}/hyba-data.yaml` · `runbooks/{aws,azure,gcp}/HYBA_DATA_PILOT.md` · multicloud certificate pack |

**External sentence (safe):**  

*Deployment strategy and named pilot runbooks cover AWS, Azure, and GCP. Provider-by-provider production certificates remain internal until live deploy evidence is board-signed.*

---

### 5. Measurement & falsifiability (Scrutiny / evidence boundary)

| Attribute | Sealed language |
| --- | --- |
| What it does | Transparent benchmarking, claim boundaries, NO_GO when acceptance missing |
| Tier | **T2** for framework existence |
| Freeze evidence | Evidence boundary V1 status **NO_GO** for operational acceptance (2026-06-19 artifact) |

**External sentence (safe):**  

*HYBA separates protocol/code evidence from operational and economic claims. Operational advantage is not claimed without acceptance artifacts.*

---

### 6. Explicitly out of external HYBA Data GTM (internal only)

| Item | Why |
| --- | --- |
| Live mining revenue / pool economics | R&D / treasury path — not Data customer proof |
| Universal compression | Violates honest positioning / information theory bounds |
| 7.155× / $100T-class without power-d, mode, harness, or TAM citation | Elevate seal / citations — algebra already reconciles 2.62× with 85.4% via d |
| 99.999% uptime without pack | Fail extraordinary-proof rule |
| Consciousness / IIT as customer product | Freeze itself marks mining/IIT domain as unvalidated for product claims |

---

## Capability matrix (board view)

| Capability | Customer value | Tier | Leave ecosystem? |
| --- | --- | --- | --- |
| PULVINI structured compression (M1 hash) | More effective memory / lower memory TCO | **T2 BOUNDED** | **Yes — method + data class + test_hash** |
| HERMES product wrapper | Single commercial face for Data | T1 naming | Yes as **name hierarchy** |
| Salamander self-heal (online-gated) | Lower ops burden, resilience | **T2 implemented** | **Implemented**, not SLA |
| Gain-share billing + pilot telemetry | Align incentives; not SaaS | **T2 hermetic** | Doctrine + metering yes; **T3** customer sign-off |
| Multi-cloud availability | Sovereign / enterprise fit | **T1 runbooks** | Strategy yes; **PROVEN** internal |
| Scrutiny / claim gates (RESTRICTED lanes) | Trust under scrutiny | T2 | Yes |
| Learn-to-learn + φ-fold memory | Acquire knowledge; store folded | T1–T2 | Architecture yes |

---

## Code ↔ documentation elevation

**The code must always be elevated to meet documentation.** External capability language is not a substitute for implementation. Engineering priority: raise code, tests, telemetry, and evidence packs to match sealed docs — not the reverse.

| Doc claim class | Code elevation required |
| --- | --- |
| PULVINI ratio language | Sealed benchmark harness + hash + data-class gates |
| Self-heal / self-optimise | Tests + supervised runtime evidence |
| Gain-share commercial | Metering of savings inputs (m_eff, overhead, spend) |
| Multi-cloud strategy | Named-provider deploy proofs |
| 99.999% availability | Measurement pack before any external use |

## Seals — elevated (engineering closed what engineering can)

| # | Seal | Status | Evidence |
| --- | --- | --- | --- |
| 1 | M1 production test hash | **CLOSED — BOUNDED** | `sealed_metric_card.py` · `M1_SEAL.json` · hash `02b3c4ac…097cf19` |
| 2 | Pilot telemetry → savings | **CLOSED — T2 hermetic** | `pilot_telemetry.py` · `PILOT_TELEMETRY_MEASUREMENT.json` |
| 3 | Availability method pack | **CLOSED — INTERNAL method** | `UPTIME_PACK.json` (EXTERNAL 99.999% still needs long-window production) |
| 4 | Named multi-cloud runbooks | **CLOSED — strategy** | `runbooks/{aws,azure,gcp}/HYBA_DATA_PILOT.md` |
| 5 | Claims register | **CLOSED** | [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)  • `sealed_claims.py` (RESTRICTED not banned) |
| 6 | Marketing master | **CLOSED** | [HYBA Data — Marketing Master (External-Ready)](HYBA%20Data%20%E2%80%94%20Marketing%20Master%20(External-Ready)%202dd867f3c9674fe99353a4ab21ef67f5.md) |
| 7 | Code elevation pack | **CLOSED** | [HYBA Data — Code Elevation Pack (Engineering Standard)](HYBA%20Data%20%E2%80%94%20Code%20Elevation%20Pack%20(Engineering%20Stand%20080cf1c058b14a8692d9431695ed928f.md) · elevation 9/9 · capability tests 7/7 |
| 8 | Customer T3 / multi-cloud PROVEN / PDF lockup craft | **Human / production residual** | Cannot invent customers or live provider certs; brand optical craft open |

**Tracker:** `doctrine_execution/CAPABILITY_ELEVATION_STATUS.md` · `artifacts/hyba_data/CAPABILITY_ELEVATION_CLOSURE.json`

## Code elevation status

| Layer | Status |
| --- | --- |
| Sealed claims (EXTERNAL/BOUNDED/INTERNAL/**RESTRICTED**) | **Active** |
| Metric card M1 **harness-sealed**; M2/M3 INTERNAL | **Active** |
| Data-class gate | **Active** |
| Savings metering + **pilot telemetry wire** | **Active** |
| Copy / restricted-language gate | **Active** |
| Online-gated Salamander | **Active** |
| Learn-to-learn + φ-fold memory | **Active** |
| Master control plane wired | **HYBA_DATA_MASTER_OK** |
| Self-test artifacts | `CODE_ELEVATION_REPORT.json` · `CAPABILITY_ELEVATION_CLOSURE.json` · `M1_SEAL.json` |

---

## Related

- [HYBA Discoveries & Impact — Institutional Record (Posterity)](HYBA%20Discoveries%20&%20Impact%20%E2%80%94%20Institutional%20Record%20(%207b395586dd8d4fbfb0a221e8e13cdaa5.md) — discoveries + impact for audit
- [Board Review — Freeze Package vs Doctrine (2026-07-15)](Board%20Review%20%E2%80%94%20Freeze%20Package%20vs%20Doctrine%20(2026-07%20696a8142b5a04c5081a273f4f57f38b2.md)
- [Category & Delivery Doctrine — CIaaS](Category%20&%20Delivery%20Doctrine%20%E2%80%94%20CIaaS%20d0b437e807074c5d9342f6b922660d07.md)
- [Product Documentation](Product%20Documentation%20d88232dd6f99437e8a318360809b41a7.md)
- [HYBA Data — Code Elevation Pack (Engineering Standard)](HYBA%20Data%20%E2%80%94%20Code%20Elevation%20Pack%20(Engineering%20Stand%20080cf1c058b14a8692d9431695ed928f.md)
- [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md)
- [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md)