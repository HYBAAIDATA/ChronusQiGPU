# HYBA Data — Sealed Claims Register

<aside>
🏛️

**HYBA Data** · Sealed claims register  

**Parent:** HYBA Software Ltd  

**Board:** Andre Taylor-Morris (sole shareholder & director)  

**Purpose:** Single source of truth for marketing language. If a claim is not here as **EXTERNAL**, it does not leave the ecosystem.  

**Logo:** HYBA Data lockup on formal exports — no generic icons.  

**Rule:** Produce nothing without research and citable evidence. Extraordinary claims require extraordinary proof.

</aside>

---

## BLUF

We **do not ban claims**. We **implement** them from first principles, **test** them, and **elevate code to meet documentation**. Lanes gate *external readiness*, not ambition.

| Lane | Meaning |
| --- | --- |
| **EXTERNAL** | May ship in customer/press/investor materials **as written** (with required citation/bounds) |
| **BOUNDED** | May ship only with explicit limits, method, and data class |
| **INTERNAL** | Not external yet — engineering / board; elevate until ready |
| **RESTRICTED** | Not external-ready *yet* — still implement, test, elevate (never “banned forever”) |

**Law:** Elevate code to documentation, always. If it is not ready externally, it is **RESTRICTED** — not abandoned.

**Hard locks (19 July 2026):**

- **Quantum / VQC — GATED** for all external materials (no announce, no pitch).
- **Golden ratio / fold engine — CLOSED IP. We are not open-sourcing it.** No public reference kernels, no “OSS MVP fold,” no GitHub dump of GRT/PULVINI internals.
- External Data face = **PULVINI + HERMES** only; proof via closed pilots + sealed metrics.

Code: `python_backend/hyba_data/sealed_claims.py` · Clarifications: [Data-First Claim Clarifications — Quantum Gated · No IP Leak · Brick Demos](Data-First%20Claim%20Clarifications%20%E2%80%94%20Quantum%20Gated%20%C2%B7%20%20ee3a4d630691436f9c877496eb7e83fd.md)

---

## 1. Category & company (EXTERNAL)

| Claim | Status | Required form |
| --- | --- | --- |
| Category is **Computational Intelligence as a Service (CIaaS)** | EXTERNAL | Always define; never default to SaaS |
| HYBA does **not** fit existing categories — we defined our own | EXTERNAL | Positioning |
| **HYBA Data** is first-to-market company under HYBA Software Ltd | EXTERNAL | Governance fact |
| Hierarchy: Company **HYBA Data** → two products: **PULVINI** (memory fold) · **HERMES** (GPU scale) | EXTERNAL | Always — distinct products, not engine-under-product collapse |
| Autonomy fabric: **Salamander** (+ meta-controller) | EXTERNAL as name | Capability detail = BOUNDED |
| Tagline: *Intelligent Solutions.* | EXTERNAL | House tagline |
| Not SaaS — do not bill or deliver as SaaS | EXTERNAL | Commercial doctrine |
| No maintenance fee — nothing to maintain under self-healing design | EXTERNAL | Pair with gain-share model |
| Pricing intent: **25% of measured savings** | EXTERNAL | “Measured” is mandatory |
| If no measured savings → no success fee | EXTERNAL | Doctrine |

---

## 2. Technical claims (BOUNDED / INTERNAL)

### φ-power law (canonical — folding and compression are one system)

Working-set fold depth is the **φ power** `d`. Compression is not a separate invention from folding.

```jsx
φ = (1+√5)/2 ≈ 1.6180339887…
reduction(d) = 1 − φ^{−d}     // fraction working-set shrinks
capacity(d)  = φ^{d}          // effective multiplier ≈ original/W
```

| Power d | capacity φ^d | reduction 1−φ^{−d} | Metric row |
| --- | --- | --- | --- |
| **2** | **~2.618×** | **~61.80%** | **M1** (default BOUNDED technical) |
| **4** | **~6.854×** | **~85.41%** | **M2** (depth-4 class — same law, higher power) |

**You move the fold from ~85.4% by changing `d` (the power), not by inventing a second metric.** 2.62× and 85.4% are **reconciled** algebraically. What still elevates is harness seal + kernels/residuals mode + data class for each `d` — not “whether 2.62 conflicts with 85.4.”

**d is unbounded.** Stopping a table at d=5 was display truncation only. The law continues (d=6,8,10,12,16,20,24,…). Higher powers are the same formula; external release is gated by elevation + Commercial Throttle ([The PHI-Space Commercial Throttle Doctrine](The%20PHI-Space%20Commercial%20Throttle%20Doctrine%20c1e59747818b474bb60eee5a5ec6abce.md)), not by a math ceiling at 5.

**Naming fix:** M1 is **φ² / power d=2** (not “depth-1 / φ²”). Older “depth-1 class” labels that pair with 2.62× were misnamed.

**Test lock (19 July 2026):** `phi_power_fold_law_test.py` PASS — pure law + discrete length model. Extended ladder verified through d=24+.

| Claim | Status | Bound / action |
| --- | --- | --- |
| PULVINI φ-folds **structured numerical / φ-pattern working sets** | **BOUNDED EXTERNAL** | Always state data class |
| Working-set law `reduction(d)=1−φ^{−d}`, `capacity(d)=φ^d` | **EXTERNAL** (math) | Always name power d; kernels retained for invertibility |
| ~**2.62×** (**φ² / power d=2**) on structured numerical arrays | **BOUNDED** | Method + error + test hash; M1 harness sealed |
| Reconstruction error claims (e.g. &lt;1e-8 / &lt;1e-14) | **BOUNDED** | Only with dataset + mode + test hash |
| ~**6.85× / 85.41%** (**φ⁴ / power d=4**) working-set class | **INTERNAL** until depth-4 harness external seal | **Same law as M1 at d=4** — elevate code/tests at power 4; do not treat as unreconciled with 2.62× |
| **7.155×** commercial / measured peak class | **INTERNAL** | May exceed pure φ⁴ on structured paths; needs T3 / mode card |
| Universal / all-memory compression | **RESTRICTED** | Not external-ready — structured/φ-pattern scope; implement + elevate honest product language |
| Self-healing / self-optimising software **implemented** | **BOUNDED EXTERNAL** | “Implemented with tests” — not customer SLA |
| **99.999% uptime** | **INTERNAL** | No sealed measurement pack yet |
| Multi-cloud availability **strategy** | **EXTERNAL** | Strategy only |
| Multi-cloud **proven production** on named providers | **INTERNAL** until certificates |  |
| Live mining economics as Data proof | **RESTRICTED** | Not external-ready — Data product is quantum-for-data, not mining; elevate product surface |
| Consciousness / IIT as product claim | **RESTRICTED** | Not external-ready — implement first principles + evidence before external |

### Sealed metric card (power ladder — one law)

| ID | Power d | Theory | Ratio language | Data class | Loss / mode | External? |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | **2** (φ²) | capacity ≈ 2.618×; W reduction ≈ 61.8% | ~2.62× | Structured numerical | Near-lossless with kernels | **BOUNDED** (harness sealed) |
| M2 | **4** (φ⁴) | capacity ≈ 6.854×; W reduction ≈ 85.41% | ~6.85× / ~85.4% | Structured | W-law + kernels for RT; net storage separate if kernels squeezed | **INTERNAL** — elevate depth-4 seal (not “ban”) |
| M3 | ≥4 measured / commercial | May exceed pure φ^d on structure | 7.155× class | Savings framing | Mode + T3 | **INTERNAL** |

**Board rule:** Always state **power d**. Customer economics may use sensitivity (1.5 / 2.0 / 2.6) until production `m_eff` measured. Moving GTM emphasis from 85.4% to 2.62× is **selecting d=2 vs d=4 on the same ladder**, not abandoning the fold law.

---

## 2b. Quantum & φ-resonance claims — verification-backed lanes (2 August 2026)

<aside>
🔬

These lanes were set by **independent replication from primitives** in a clean sandbox — not by document review. Method and results: [HYBA φ-Quantum Machine — 1,000-Logical-Qubit Engineering Record (24 July 2026)](Geodesic%20Tensor%20Engine%20&%20PULVINI%20V3%20Integration%20%E2%80%94%20/HYBA%20%CF%86-Quantum%20Machine%20%E2%80%94%201,000-Logical-Qubit%20Engin%204af52dc709194c5ea68e6d08736a9863.md) → *Independent Verification*.

</aside>

### Quantum — what survived testing

| Claim | Lane | Bound / basis |
| --- | --- | --- |
| Exact 1,000-logical-qubit Clifford algebra on commodity hardware at 4 MB | **EXTERNAL** (when the quantum gate is lifted) | **Independently reproduced.** Tableau footprint 4,002,000 bytes matched to the byte; GHZ stabilizer group verified algebraically |
| 1,000 stabilizer syndrome channels for QEC research | **BOUNDED** | Strongest honest product surface — QEC is predominantly Clifford, so the substrate is genuinely fit for purpose |
| Deterministic reproducibility · PULVINI recon error 4.05e-16 | **BOUNDED** | State with method and depth (d=20) |
| Substrate-agnostic quantum algebra (D2 doctrine) | **EXTERNAL** | **Upheld and independently confirmed.** The algebra genuinely ports to any substrate |
| Any quantum **speedup**, **advantage**, or **“supremacy”** | **RESTRICTED** | Precluded by **Gottesman–Knill**. Not an evidence gap — a theorem. This lane cannot be elevated on a Clifford substrate |
| Shor / factoring / period-finding capability | **RESTRICTED** | T-gate probe confirmed no non-Clifford update rule exists. Not executable at any modulus width |
| Comparison to IBM Condor / Google Willow | **RESTRICTED** | Category error — universal devices vs an exact Clifford simulator. Qubit counts are not comparable |
| PQC cryptanalysis · “sovereign PQC audit service” · probing Kyber/Dilithium with φ-Grover | **RESTRICTED — do not offer** | Grover requires non-Clifford gates and cannot run here; φ-Grover is a classical Fibonacci-strided heuristic. Lattice security rests on Module-LWE/SIS, which resonance search does not address. **Offering this to a signals-intelligence customer would be tested in week one** |

**Note on elevation.** Most RESTRICTED lanes in this register mean *not ready yet — implement and elevate*. **The advantage and Shor lanes are different in kind:** they are closed by a proved theorem, not by missing work. The only path to universality is a non-Clifford gate (T, or magic-state injection) — and that path **reintroduces exponential cost**, which is precisely what the 4 MB footprint currently avoids. This trade-off should be stated plainly in any technical annex.

### φ-resonance — suspended pending control arm

| Claim | Lane | Condition for elevation |
| --- | --- | --- |
| “60% of Bitcoin nonces exhibit φ-resonance ≥ 0.5” (D13) | **INTERNAL** — downgraded T2 → T1 | Run the production metric over ≥200,000 CSPRNG words and report the **measured** null rate beside the observed rate |
| “7.58-sigma statistical validation” | **INTERNAL** | Computed against an *assumed* 50% null with no control arm; implies a sample of only ~1,436 |
| 177× structured-search speedup (D17) | **INTERNAL** | Rests on the same 60% figure — suspended with it |
| 804× Grover speedup (D15) | **RESTRICTED** | Rests on the same figure, and “Grover” is a misnomer for a classical strided search |
| 1000× database search acceleration (D1) | **INTERNAL** | Requires a named baseline, comparator implementation, and cache state |

<aside>
⚖️

**New standing rule — the control arm.** Any claim that a metric detects structure in data **must** report that metric’s hit rate on a matched random control, alongside effect size and a test against the **measured** null — never an assumed one.

**Why this is now a hard rule:** five reasonable readings of “φ-resonance ≥ 0.5”, run over 200,000 random words, returned **50.1%, 50.0%, 50.0%, 99.0% and 100.0%**. A deliberately vacuous metric was constructed that fires at **60.05% on pure noise**. Without a control arm, a headline percentage carries **no information at all**.

**Corollary — tests must be able to fail.** The 1,000-qubit GHZ correlation test was reproduced and then passed by a classical impostor that flips **one coin** and copies the bit 1,000 times. Same defect class as `assert isinstance(is_intact, bool)`. A test no impostor can fail is not evidence, and a pass count is not a proof.

</aside>

---

## 3. Market & financial claims

| Claim | Status | Rule |
| --- | --- | --- |
| Memory is a material bottleneck for AI/infra workloads | **BOUNDED EXTERNAL** | Qualitative OK; quantitative only with citation |
| Hyperscaler / data-centre CAPEX is large (2026–2030) | **BOUNDED EXTERNAL** | **Must cite** primary source (e.g. FT / Goldman / earnings) on every $ figure |
| Specific **$5T / $5.3T / $8T / $17T** lines from freeze | **INTERNAL** until single cited TAM sheet signed | Orphan $T figures do not ship |
| Meta/Google/AWS **$1.5–1.8T** procurement splits in freeze | **INTERNAL** | Not independently sealed here |
| “$750B / $278B HYBA revenue” class projections | **RESTRICTED** | Not external-ready — seal TAM citation card + T3 evidence, then elevate |
| Illustrative savings = spend × f × (1−1/m) | **BOUNDED EXTERNAL** | Label illustrative; show sensitivity |
| Gain-share 25% of **measured** savings | **EXTERNAL** | Core commercial doctrine |

### TAM protocol (plug the gap)

Before any $T leaves the ecosystem:

1. One figure  
2. One source (publisher, title/date, URL or document ID)  
3. Scope (who, what spend type, which years)  
4. HYBA derivation if transformed (show formula)  
5. Board or Andre sign-off on the sealed TAM card  

---

## 4. Restricted external language (not ready yet — implement & elevate)

These phrases do **not** leave the ecosystem until elevated. They are **RESTRICTED**, not abandoned:

- SaaS (as HYBA Data category) → elevate CIaaS narrative
- Universal compression → elevate structured/φ-pattern product truth
- Depth-4 / 85.4% / 6.85× / 7.155× without power-d + mode + harness → elevate seal (algebra already reconciles 2.62× with 85.4% via d)
- $100T / monopoly without evidence annex → seal citations + proof
- 99.999% uptime without pack → implement measurement pack
- Mining hashrate as Data proof → not Data GTM
- “No competition” without bound → elevate with competitive proof
- Maintenance fees / seat model → CIaaS gain-share only
- Quantum / VQC / “quantum from maths” as external slogan → **GATED**
- O(log N) geodesic product search · topology replaces AES → **not external**
- **Open-source golden ratio / fold / GRT / PULVINI kernels** → **FORBIDDEN** (IP lock, not a lane to elevate into public OSS)

**Method:** first principles → implement → test → elevate code to documentation → then EXTERNAL/BOUNDED. **Elevation never requires open-sourcing IP.**  

---

## 5. Approved external narrative (master copy block)

**Category**  

HYBA operates in **Computational Intelligence as a Service (CIaaS)** — a category HYBA defined because existing labels do not fit.

**Company**  

**HYBA Data** is the first-to-market company under HYBA Software Ltd.

**Offer**  

HYBA Data sells two products: **PULVINI** (φ-fold memory / working-set compression) and **HERMES** (GPU / compute scaling), plus an autonomy fabric that **heals and optimises itself**. We are **not SaaS**. We do **not charge maintenance**.

**Fold doctrine**  

φ is an instruction: **compress by folding, not by truncating.** Reconstruction is the product test.

**Quantum**  

**GATED externally.** Do not use in customer/press materials. Data GTM is silent on quantum/VQC.

**IP**  

Golden ratio fold engine and related kernels are **closed IP — not open source.**

**Commercial**  

Pricing is a **share of measured savings** (doctrine: 25%). If savings are not measured, there is no success fee. No onsite client engineering army; no training spin-off — adaptive UI.

**Proof posture**  

Claims are separated into implemented / measured / customer-validated. Operational and economic advantage require acceptance artifacts. It is not hyperbole if it is true and evidenced.

---

## 6. Freeze file disposition

| Freeze source | Disposition |
| --- | --- |
| `HONEST_POSITIONING.md` | **Prefer** — align external claims |
| `CIAAS_CATEGORY_DEFINITION.md` | **Prefer** category definition; strip non-Data tiers if needed |
| `HYBA_POSITIONING_SHEET.md` | **BOUNDED** — use 2.62× only with bounds; drop unverified competitor table rows |
| `CASE_STUDY_HYPERSCALERS.md` | **INTERNAL** as-is; replaced by board case studies (illustrative) |
| `PULVINI_TRILLION_DOLLAR_OPPORTUNITY.md` | **INTERNAL — do not externalize** |
| `FT_PULVINI_PITCH_PACKAGE.md` | **INTERNAL** until TAM citations sealed |
| Mining deploy / revenue docs | **INTERNAL R&D** — not Data GTM |

---

## 7. Related

- [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md)
- [Case Studies — Early Targets (Board Draft)](Case%20Studies%20%E2%80%94%20Early%20Targets%20(Board%20Draft)%20e93eff9fc58b453bb1fc23d2c6ac929f.md)
- [Board Review — Freeze Package vs Doctrine (2026-07-15)](Board%20Review%20%E2%80%94%20Freeze%20Package%20vs%20Doctrine%20(2026-07%20696a8142b5a04c5081a273f4f57f38b2.md)
- [Category & Delivery Doctrine — CIaaS](Category%20&%20Delivery%20Doctrine%20%E2%80%94%20CIaaS%20d0b437e807074c5d9342f6b922660d07.md)