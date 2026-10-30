# CPO Handover — Chief Product Officer (HYBA Data)

<aside>
🏛️

**Role handover: Chief Product Officer**  

**Company:** HYBA Data (under HYBA Software Ltd)  

**Reports to:** Board / CEO — Andre Taylor-Morris  

**Date:** 2026-07-15  

**Pack index:** [Executive Handover Pack — CPO · COO · Chief of Staff](../Executive%20Handover%20Pack%20%E2%80%94%20CPO%20%C2%B7%20COO%20%C2%B7%20Chief%20of%20Sta%20d9b7e31d77da485e843986a3af02e3f5.md)  

**Claims authority:** [HYBA Data — Sealed Claims Register](../HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)

</aside>

---

## 1. BLUF

You own **what we build, how we package it, and what we are allowed to say** about product capability. **Two products:** **PULVINI** (memory fold) and **HERMES** (GPU scale) — distinct offers under HYBA Data; suite brand **PHI-1** (SDK · Storage · GPUizer) packages surfaces. You do **not** invent metrics. You elevate product to sealed documentation — never the reverse as the primary move.

**Primary success metric (90 days):** One measured pilot design ready for COO delivery, with external language only from sealed claims.

---

## 2. Mandate

| Own | Do not own alone |
| --- | --- |
| Product vision & roadmap | Board doctrine (non-negotiable) |
| SKU definition (Core / Pro / Storage / GPUizer) | Live multi-cloud production ops (COO) |
| External product claims (with claims register) | Wet-sign TAM $ figures (Board) |
| PRDs, UX bar (McKinsey product surface) | Day-to-day pilot ops (COO) |
| Pricing packaging (true-up to gain-share) | Board calendar / CoS hygiene |

---

## 3. Product truth stack

### Hierarchy (always)

HYBA Software Ltd → **HYBA Data** → **PULVINI** (memory fold product) + **HERMES** (GPU scale product) → **PHI-1** (runtime/suite packaging) → **Salamander** (autonomy, BOUNDED)

**Do not collapse** PULVINI into “engine under HERMES only.” Two products; may stack.

### Portfolio (reconciled)

| Layer | SKU | External metric language |
| --- | --- | --- |
| Memory product | **PULVINI** (+ PHI-1 SDK / Storage surfaces) | M1 d=2 ~2.62× BOUNDED + sensitivity 1.5/2.0/2.6 |
| GPU product | **HERMES** (+ PHI-1 GPUizer surface) | **Pilot-measured** GPU/throughput gains only |
| Stack | PULVINI + HERMES together | Optional when both memory and GPU pains exist |

Full pack: [PHI-1 Product Portfolio & GTM — Reconciled Packaging](../PHI-1%20Product%20Portfolio%20&%20GTM%20%E2%80%94%20Reconciled%20Packagi%20a6028e6229ad4ff48b8f560594fe3f95.md) · Fold standard: [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](../Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md) · CRO: [Sales Enablement & CRO Briefing](../Sales%20Enablement%20&%20CRO%20Briefing%20f139d0899a0a4ec19c72d0baf7562738.md)

### Metrics you must recite (φ-power ladder)

**Law:** `capacity(d)=φ^d`, `reduction(d)=1−φ^{−d}`. Folding and compression are linked — change power `d` to move the ratio. Ref: [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](../%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md)

| ID | Power d | Lane | Use |
| --- | --- | --- | --- |
| M1 ~2.62× / ~61.8% W | **2** (φ²) | BOUNDED | Default external technical |
| m ∈ {1.5, 2.0, 2.6} | — | EXTERNAL-safe | Customer savings math |
| M2 ~6.85× / ~85.41% W | **4** (φ⁴) | INTERNAL until d=4 seal | Same law as M1 — elevate harness |
| M3 7.155× | ≥4 measured | INTERNAL | Until T3 |

**Operating rules:** no universal compression · no fleet GPU guarantee without pilot · no SaaS seats/maintenance · no mining as Data proof · expose `fold_power_d` in product · elevate code to docs

---

## 4. Commercial doctrine (product side)

```
Fee = 0.25 × Measured_Savings
Fee = 0 if savings not measured
```

- Category: **CIaaS** not SaaS
- List packaging ($/GPU/mo, $/TB) = **advance/true-up wrappers**, not seat theatre
- Adaptive UI → **no training spin-off product**

---

## 5. Positioning

**External (Option B):** geometry of information · fold never truncate · eligible sets → measure → gain-share · GPUs do more with what you own (prove in pilot)

**DD only:** quantum-from-maths; quantum serves data; no physical QPU product claim  

**Option A** (“classical quantum computer” cold open) = RESTRICTED

---

## 6. Engineering elevation you drive

| Priority | Action | Repo / hub |
| --- | --- | --- |
| P0 | Keep GPUizer / SDK / Storage elevating to portfolio docs | `gpuizer.py` · `sdk_core.py` · `storage_engine.py` |
| P0 | Local runner green before any demo ship | `python3 -m hyba_data.local_elevation_runner` |
| P1 | PyTorch Lightning packaging path | elevation plan |
| P0 | Depth-4 / M2 harness seal (same φ-power law at d=4) | fold fidelity · `M2_RECONCILIATION.json` · expose `fold_power_d` |
| P1 | Free-tier Core (M1 demos at d=2) | `sdk_core.py` · pyproject sketch |
| P2 | S3 gateway toward architecture | storage spike → PHI-1 OS design |
| P2 | Whitepaper track | `whitepaper_phi_fold_methods_bounds.md` |
| P2 | Patent track (GPU φ-fold) | counsel + `PATENT_TRACK_GPU_PHI_FOLD.md` |

Plan: [PHI-1 Local Elevation Plan — IDE Executable](../PHI-1%20Local%20Elevation%20Plan%20%E2%80%94%20IDE%20Executable%203772c88ac0ee41489d4743ac3bbad590.md)

---

## 7. 30 / 60 / 90 days

### Days 1–30 — Absorb & lock language

- [ ]  Read claims register, φ-power law page, fold standard, marketing master, portfolio GTM, CRO pack, breakthrough doctrine
- [ ]  Run local elevation suite; demo SDK + storage + GPUizer pilot report
- [ ]  Audit all external decks against RESTRICTED language gate
- [ ]  Freeze Q3 product narrative (one page) for CoS board pack

### Days 31–60 — Ship packaging

- [ ]  PRD: PHI-1 Core free tier (M1 only)
- [ ]  PRD: GPUizer callback + benchmark harness (illustrative until T3)
- [ ]  PRD: Storage Engine pilot path with recon certs
- [ ]  Joint with COO: pilot measurement protocol instrumented
- [ ]  Pricing one-pager: list wrappers → true-up to 25% measured

### Days 61–90 — Pilot-ready product

- [ ]  One early-target segment chosen (AI/ML or storage)
- [ ]  External demo script using **only** EXTERNAL/BOUNDED claims
- [ ]  DD annex prepared (M2 INTERNAL, quantum moat Option B)
- [ ]  Board review: product readiness vs sealed claims

---

## 8. Interfaces

| Partner | You give | You get |
| --- | --- | --- |
| **COO** | Pilot-ready SKU + measurement hooks | Delivery, reliability, multi-cloud ops |
| **CoS** | Claim-clean product narrative | Board cadence, deck form, decision log |
| **Board** | Roadmap + sealed language | Doctrine, capital, final claim seals |
| **CRO / Sales** | Claim-clean SKUs, demos, power-d language | Field demand; pilot candidates; pricing friction |
| **EUCLID** | Product elevation tickets | Code/tests/docs elevation under doctrine |

---

## 9. Decision rights

| Decision | CPO alone | Needs Board |
| --- | --- | --- |
| Feature priority within sealed doctrine | Yes | — |
| External metric beyond M1/sensitivity | No | Yes + evidence |
| Rename SKU packaging | Yes (consult CoS brand) | If company/product hierarchy changes |
| Open-source Core scope | Propose | Approve IP boundary |
| “Classical quantum” mass GTM | No | Explicit override |

---

## 10. Key risks

| Risk | Mitigation |
| --- | --- |
| Sales ships d=4 ratios without harness seal | Claims gate + CoS; elevate d=4 code — do not delete M2 doctrine |
| Product outruns code | Elevation rule; keep claim INTERNAL/RESTRICTED until tests green |
| SaaS pricing drift | CIaaS true-up mandatory |
| Mining / quantum confusion | Quantum serves data; mining not Data proof |

---

## 11. Reading list (order)

1. [HYBA Data — Sealed Claims Register](../HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)  
2. [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](../Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md) · [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](../%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md)  
3. [HYBA Data — Marketing Master (External-Ready)](../HYBA%20Data%20%E2%80%94%20Marketing%20Master%20(External-Ready)%202dd867f3c9674fe99353a4ab21ef67f5.md)  
4. [PHI-1 Product Portfolio & GTM — Reconciled Packaging](../PHI-1%20Product%20Portfolio%20&%20GTM%20%E2%80%94%20Reconciled%20Packagi%20a6028e6229ad4ff48b8f560594fe3f95.md)  
5. [Sales Enablement & CRO Briefing](../Sales%20Enablement%20&%20CRO%20Briefing%20f139d0899a0a4ec19c72d0baf7562738.md) · [Quantum-Adjacent Commercial Maturity Map — PQC · QKD · Optimisation · Simulation · QML (HYBA Packaging)](../Quantum-Adjacent%20Commercial%20Maturity%20Map%20%E2%80%94%20PQC%20%C2%B7%20Q%20eb9bc67a18934f358ee36274bab8fa2f.md)  
6. [PHI-1 Local Elevation Plan — IDE Executable](../PHI-1%20Local%20Elevation%20Plan%20%E2%80%94%20IDE%20Executable%203772c88ac0ee41489d4743ac3bbad590.md)  
7. [HYBA Data — Capabilities (Evidence-Tiered)](../HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md)  
8. [Case Studies — Early Targets (Board Draft)](../Case%20Studies%20%E2%80%94%20Early%20Targets%20(Board%20Draft)%20e93eff9fc58b453bb1fc23d2c6ac929f.md) · [Case Studies — Fold × Quantum-for-Data (Board Pack)](../Case%20Studies%20%E2%80%94%20Fold%20%C3%97%20Quantum-for-Data%20(Board%20Pack%2030b91b68887546dfb25418fb01a27592.md)  
9. [PHI-1 OS Design Document (v1.0)](../PHI-1%20OS%20Design%20Document%20(v1%200)%20d0a77a19280c45b7a08964b4a54d6c75.md)  

**Repo:** `doctrine_execution/PHI1_PRODUCT_PORTFOLIO_GTM.md` · `ELEVATION_PLAN_LOCAL.md` · `python_backend/hyba_data/*`

---

## 12. Handover checklist

- [ ]  Accept mandate & metric lanes
- [ ]  Green local elevation run
- [ ]  Sign product language commitment (sealed claims only)
- [ ]  90-day plan filed with CoS
- [ ]  First board product update scheduled