# HYBA Data — Pilot Measurement Protocol

<aside>
🏛️

**HYBA Data** · Pilot measurement protocol  

**Closes gap:** customer pilot path from baseline → measured savings → gain-share  

**Board:** Andre Taylor-Morris, HYBA Software Ltd  

**Logo:** HYBA Data lockup on customer-facing pilot pack  

**Rule:** No success fee without measurement. Extraordinary claims require extraordinary proof.

</aside>

---

## BLUF

A HYBA Data pilot is a **measurement engagement**, not a SaaS trial. Success is defined only when baseline and post-deploy metrics are agreed, captured, and signed. Pricing (25% of measured savings) invoices only after the measurement report.

**φ-power lock:** fold depth is power `d`. `capacity(d)=φ^d`, `reduction(d)=1−φ^{−d}`. Record **agreed `d`** (default pilot technical class **d=2 / M1** unless scope signs d=4). M1 and M2 are the same law — change power to move the fold. Ref: [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md) · [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md).

---

## 1. Objectives

1. Prove (or falsify) eligible-workload savings under PULVINI/HERMES on a **named** production or production-like surface.  
2. Establish a repeatable FinOps-grade measurement method.  
3. Produce a **Tier T3 path** artifact (customer-validated) or a clean negative result.  
4. Keep all claims within the [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md).

---

## 2. Scope definition (Day 0)

| Field | Required |
| --- | --- |
| Workload name | e.g. LLM KV-cache tier, Redis hot set, Spark shuffle memory |
| Environment | Cloud provider + region + cluster ID |
| Data class | Structured numerical / other (state eligibility) |
| Fold power d | Default **2** (M1); **4** only if scope + harness path agreed (M2 class) |
| In-scope spend | Memory-related TCO definition (hardware allocation, instance $ , power proxy) |
| Eligibility fraction f | % of in-scope spend expected compressible |
| Success criteria | Minimum m or $ savings threshold (optional) |
| Duration | Default **90 days** (14-day baseline + 60-day deploy + 16-day report) |
| Out of scope | Mining, unrelated clusters, universal memory claims |

**Gate:** If data class is not eligible, pilot does not start.

---

## 3. Phases

### Phase A — Baseline (Days 1–14)

Capture without HERMES/PULVINI:

| Metric | Method |
| --- | --- |
| Memory used (GB peak / p95) | Provider metrics + agent |
| Memory-related cost ($/day) | FinOps export |
| Throughput / latency SLOs | Existing APM |
| Error rate / restarts | Existing ops |
| Workload volume | Requests, jobs, tokens, etc. |

**Output:** `Baseline Report v1` signed by customer + HYBA.

### Phase B — Deploy (Days 15–74)

1. Install HERMES/PULVINI per runbook (single cloud first).  
2. Enable telemetry for compression ratio, reconstruct error, CPU/GPU overhead.  
3. Hold workload mix as constant as practical; document changes.  
4. Autonomy (Salamander) in **supervised** mode unless otherwise agreed.

### Phase C — Measure & report (Days 75–90)

| Metric | Definition |
| --- | --- |
| fold_power_d | Configured φ-power for the run (must match scope) |
| m_eff | Measured effective capacity multiplier on eligible set (compare to φ^d theory band) |
| Overhead | Incremental compute % vs baseline |
| Savings $ | Agreed formula (see §4) |
| SLO impact | Latency/error delta vs baseline |

**Output:** `Measurement Report v1` + optional gain-share invoice test.

---

## 4. Savings formula (standard)

```
Eligible spend S_e = S_memory × f
Gross savings G = S_e × (1 − 1/m_eff) − S_overhead
HYBA fee = 0.25 × max(G, 0)   # doctrine; only if G measured and signed
```

| Symbol | Meaning |
| --- | --- |
| S_memory | Agreed memory-related spend in window |
| f | Eligibility fraction (agreed) |
| m_eff | Measured effective multiplier |
| S_overhead | Extra compute/storage cost induced by solution |

**Rules:**

- If G ≤ 0 → fee = 0
- No projections of full-fleet savings without scale factors agreed in writing
- Default pilot assumption: **d=2 / M1 class** unless signed otherwise
- d=4 / ~6.85× / ~85.41% W is the **same law** at higher power — use only when scope sets d=4 and telemetry records it; elevate harness, do not invent a second metric
- Always log `fold_power_d`, recon error, data class, version hashes

---

## 5. Evidence pack (minimum)

| Artifact | Required |
| --- | --- |
| Signed scope sheet | Yes |
| Baseline raw metrics export | Yes |
| Deploy config + version hashes | Yes |
| Compression telemetry (fold_power_d, ratio, error) | Yes |
| Cost exports (before/after) | Yes |
| Measurement report PDF | Yes |
| Claim lane check vs claims register | Yes |
| Customer sign-off | Yes for T3 |

---

## 6. Pass / fail / extend

| Outcome | Action |
| --- | --- |
| Pass (G > 0, SLOs held) | Term sheet; optional expand scope |
| Inconclusive | Extend 30 days or narrow workload |
| Fail (G ≤ 0 or SLO breach) | Document; no fee; optional redesign |

Negative results are success for science bar — they do not leave as marketing wins.

---

## 7. Roles

| Role | Owner |
| --- | --- |
| Executive sponsor (customer) | Named |
| FinOps lead (customer) | Named |
| HYBA pilot lead | Named |
| HYBA technical operator | Named |
| Board authority (HYBA) | Andre Taylor-Morris |

---

## 8. Related

- [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)
- [φ-Power Fold Law — Investigation, Test & Fix (19 July 2026)](%CF%86-Power%20Fold%20Law%20%E2%80%94%20Investigation,%20Test%20&%20Fix%20(19%20J%2036b8e3d5002d427791863e417addf262.md)
- [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md)
- [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md)
- [PHI-1 Product Portfolio & GTM — Reconciled Packaging](PHI-1%20Product%20Portfolio%20&%20GTM%20%E2%80%94%20Reconciled%20Packagi%20a6028e6229ad4ff48b8f560594fe3f95.md)
- [Sales Enablement & CRO Briefing](Sales%20Enablement%20&%20CRO%20Briefing%20f139d0899a0a4ec19c72d0baf7562738.md)
- [Case Studies — Early Targets (Board Draft)](Case%20Studies%20%E2%80%94%20Early%20Targets%20(Board%20Draft)%20e93eff9fc58b453bb1fc23d2c6ac929f.md)