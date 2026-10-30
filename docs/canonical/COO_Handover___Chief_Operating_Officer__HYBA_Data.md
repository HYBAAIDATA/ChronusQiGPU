# COO Handover — Chief Operating Officer (HYBA Data)

<aside>
🏛️

**Role handover: Chief Operating Officer**  

**Company:** HYBA Data (under HYBA Software Ltd)  

**Reports to:** Board / CEO — Andre Taylor-Morris  

**Date:** 2026-07-15  

**Pack index:** [Executive Handover Pack — CPO · COO · Chief of Staff](../Executive%20Handover%20Pack%20%E2%80%94%20CPO%20%C2%B7%20COO%20%C2%B7%20Chief%20of%20Sta%20d9b7e31d77da485e843986a3af02e3f5.md)  

**Delivery doctrine:** [Category & Delivery Doctrine — CIaaS](../Category%20&%20Delivery%20Doctrine%20%E2%80%94%20CIaaS%20d0b437e807074c5d9342f6b922660d07.md)

</aside>

---

## 1. BLUF

You own **how we deliver, measure, and run** HYBA Data as a software business — not a services body shop. Pilots produce **measured savings**; commercial settlement is **25% of measured savings** (fee 0 if unmeasured). No onsite eng army. No training spin-off. Multi-cloud is **strategy EXTERNAL**; **proven production INTERNAL** until certificates.

**Primary success metric (90 days):** One instrumented pilot path (baseline → deploy → measure → fee calc) ready with CPO product and CoS board reporting.

---

## 2. Mandate

| Own | Do not own alone |
| --- | --- |
| Pilot operations & measurement protocol | Product roadmap (CPO) |
| Reliability, runbooks, multi-cloud deploy | External claim wording (CPO + CoS gate) |
| Savings metering in production path | Board doctrine |
| Vendor/cloud procurement ops | Pricing doctrine changes (Board/CPO) |
| Security/ops hygiene for delivery | Brand system (CoS hygiene / Board) |

---

## 3. Operating model

### What we deliver

- **Software artifact** + evidence pack + docs
- **CIaaS** — Computational Intelligence as a Service
- **Not SaaS** seats, not maintenance subscriptions

### What we refuse

- Onsite client engineering as the product
- Fortune training / training business spin-off
- Mining economics as HYBA Data customer proof
- Shipping d=4 / M2 / M3 / 99.999% / multi-cloud PROVEN without harness or certificates — elevate code; do not delete doctrine

### Measurement (source of cash)

```jsx
// φ-power law — folding and compression are one system
// capacity(d)=φ^d · reduction(d)=1−φ^{−d}
// Default pilot technical class: d=2 (M1 ~2.62×). d=4 = M2 ~6.85×/~85.41% W — same law.
Savings ≈ S_memory × f × (1 − 1/m_eff) − overhead
Fee = 0.25 × Savings_measured
Fee = 0 if not measured
m_eff external default ∈ {1.5, 2.0, 2.6} unless pilot measures otherwise
Always log: fold_power_d, recon_error, data_class, version hashes
```

Code: `python_backend/hyba_data/savings_metering.py` · `pricing_dashboard.py`  

Protocol: [HYBA Data — Pilot Measurement Protocol](../HYBA%20Data%20%E2%80%94%20Pilot%20Measurement%20Protocol%209c56caf52be040a28f37da830164758e.md) · Law: [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](../%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md) · Hub shelf: [HYBA DATA — Integrated Deployment Package & Discoveries](../../HYBA%20DATA%20%E2%80%94%20Integrated%20Deployment%20Package%20&%20Discov%200f9aedc5b415479cb34a9b1646f006b4.md)

---

## 4. Systems you operate

| System | Path / note | Lane |
| --- | --- | --- |
| PHI-1 runtime | `phi1_runtime.py` | fold/unfold/verify |
| Storage spike | `storage_engine.py` | `.phi` local proof |
| GPUizer harness | `gpuizer.py` | pilot measure |
| Local elevation | `local_elevation_runner.py` | pre-demo gate |
| Multi-cloud stubs | `deploy/{aws,azure,gcp}/` | strategy EXTERNAL |
| Multicloud cert pack | `MULTICLOUD_CERTIFICATE_PACK.json` | INTERNAL proven |
| Uptime pack | `UPTIME_PACK.json` | INTERNAL method |
| CI doctrine | `doctrine_enforcement.yml` | fail closed on banned lane |

Hub map: [Hub ↔ Repo Map — Engineering Standard & Evidence](../Hub%20%E2%86%94%20Repo%20Map%20%E2%80%94%20Engineering%20Standard%20&%20Evidence%20ce2f0a8b53e24c72806fdee93efbd96e.md)

---

## 5. Pilot factory (your core process)

| Stage | COO action | Artifact |
| --- | --- | --- |
| 1. Select workload | With CPO — memory-bound, structured-eligible; agree fold_power_d (default **2**) | Scope note |
| 2. Baseline | Capture S_memory, f estimate, current cost | Baseline pack |
| 3. Deploy | Software-only; adaptive UI; no onsite army; set fold_power_d | Deploy log |
| 4. Measure | fold_power_d, m_eff vs φ^d band, recon certs, savings | Measurement pack |
| 5. Settle | Fee only if measured & signed | Invoice calc |
| 6. Elevate | Feed T3 evidence for M3 path | T3 seal request to Board |

**Early targets:** see case studies hub pages (hyperscaler / enterprise / sovereign framing — illustrative until customer seal).

---

## 6. 30 / 60 / 90 days

### Days 1–30 — Control plane

- [ ]  Run `python3 -m hyba_data.local_elevation_runner` green
- [ ]  Inventory deploy stubs + runbooks (AWS/Azure/GCP)
- [ ]  Stand up pilot measurement checklist from protocol page
- [ ]  Define “production ready local” vs “customer production” gate
- [ ]  Risk register: security, data handling, claim leakage

### Days 31–60 — Pilot path live

- [ ]  One dry-run pilot on synthetic/structured data (no customer yet)
- [ ]  Savings dashboard wired to measured flag
- [ ]  Multi-cloud certificate checklist (what evidence elevates PROVEN)
- [ ]  On-call / incident lite process (self-heal is BOUNDED, not SLA yet)
- [ ]  With CPO: instrument GPUizer or Storage pilot path

### Days 61–90 — Customer-ready ops

- [ ]  First real pilot candidate (legal/commercial with Board)
- [ ]  Evidence pack template (CI artifacts + recon certs + fee sheet)
- [ ]  Decision: which provider first for PROVEN cert
- [ ]  Board ops review: delivery doctrine still clean (no services creep)

---

## 7. Interfaces

| Partner | You give | You get |
| --- | --- | --- |
| **CPO** | Feasibility, SLOs, pilot constraints | SKU, PRDs, sealed product language |
| **CoS** | Ops KPIs, risk, pilot status | Board agenda, decision tracking |
| **Board** | Delivery truth, cost, risk | Authority, customer intros, seals |
| **CRO / Sales** | Pilot capacity, measurement truth | Qualified opportunities; claim-clean demos |
| **EUCLID** | Ops elevation tickets | Implementation under doctrine |

---

## 8. Decision rights

| Decision | COO alone | Needs Board |
| --- | --- | --- |
| Pilot runbook & tooling | Yes | — |
| Declare multi-cloud PROVEN | No | Yes + certificates |
| 99.999% external SLA | No | Yes + long-window pack |
| Hire delivery contractors | Propose | Approve model (must not become onsite product) |
| Change gain-share rate | No | Yes |

---

## 9. Key risks

| Risk | Mitigation |
| --- | --- |
| Services creep (onsite/training) | Delivery doctrine; adaptive UI; refuse spin-off |
| Unmeasured “success fees” | Code + process: fee=0 if unmeasured |
| Ops claims ahead of packs | INTERNAL until UPTIME/MULTICLOUD elevated |
| Demo theatre without recon | Elevation runner gate before external demo |

---

## 10. Reading list

1. [HYBA DATA — Integrated Deployment Package & Discoveries](../../HYBA%20DATA%20%E2%80%94%20Integrated%20Deployment%20Package%20&%20Discov%200f9aedc5b415479cb34a9b1646f006b4.md) — hub + revenue shelf  
2. [Category & Delivery Doctrine — CIaaS](../Category%20&%20Delivery%20Doctrine%20%E2%80%94%20CIaaS%20d0b437e807074c5d9342f6b922660d07.md)  
3. [HYBA Data — Pilot Measurement Protocol](../HYBA%20Data%20%E2%80%94%20Pilot%20Measurement%20Protocol%209c56caf52be040a28f37da830164758e.md)  
4. [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](../%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md) · [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](../Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md)  
5. [HYBA Data — Sealed Claims Register](../HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)  
6. [PHI-1 Local Elevation Plan — IDE Executable](../PHI-1%20Local%20Elevation%20Plan%20%E2%80%94%20IDE%20Executable%203772c88ac0ee41489d4743ac3bbad590.md)  
7. [Hub ↔ Repo Map — Engineering Standard & Evidence](../Hub%20%E2%86%94%20Repo%20Map%20%E2%80%94%20Engineering%20Standard%20&%20Evidence%20ce2f0a8b53e24c72806fdee93efbd96e.md)  
8. [HYBA Data — Code Elevation Pack (Engineering Standard)](../HYBA%20Data%20%E2%80%94%20Code%20Elevation%20Pack%20(Engineering%20Stand%20080cf1c058b14a8692d9431695ed928f.md)  
9. `LOCAL_PRODUCTION_README.md` · `DOCTRINE_DELIVERY.md`  

---

## 11. Handover checklist

- [ ]  Accept delivery doctrine (no onsite/training product)
- [ ]  Green local elevation + savings metering tests
- [ ]  Pilot measurement checklist signed with CPO
- [ ]  Risk register v1 with CoS
- [ ]  90-day ops plan filed