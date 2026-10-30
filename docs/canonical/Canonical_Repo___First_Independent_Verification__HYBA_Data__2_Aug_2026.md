# Canonical Repo — First Independent Verification (HYBA_Data, 2 Aug 2026)

<aside>
🔬

**Method.** The repository was supplied as an archive and unpacked into a clean sandbox. No GitHub connector access was used, and no result from the repository's own CI was taken on trust. A pytest-compatible runner was written from scratch to execute the suite offline, and a separate probe was written to test the commercially material claims directly.

**Date:** 2 August 2026 · **Artifact:** `HYBA_Data-main.zip`, 804,430 bytes · **Environment:** Python 3.13, numpy 2.5.1, no network

</aside>

## 1. The headline finding — the repo is not what the record says it is

The canonical `HYBA_Data` repository does **not** contain the codebase this workspace has been describing. There is no `python_backend/hyba_data/` tree. The entire repository is a single package, `quantum_substrate/`, containing 285 Python files.

Specifically, **the two files cited as the source of the φ-resonance nonce claim do not exist in this repository**:

| Cited in the Notion record | Present in the canonical repo? |
| --- | --- |
| `pythia_mining/nonce_resonance_guidance.py` | **No** |
| `phi_grover_nonce_search.py` | **No** |
| Any function matching `def *resonance*` | **No — zero matches across all 285 files** |

This does not prove the mining work never existed; it may live in `HYBA_Pythia_Prod` or only on a local machine. But it does establish that **D13 has no supporting code in the repository HYBA proposes to commercialise.** Any due-diligence reader given this repo and the D13 claim together will find the gap immediately.

## 2. What genuinely stands — and it is substantial

This is the most disciplined artifact produced in this programme to date, and it deserves to be said plainly.

**The README already does what we have spent this whole engagement arguing for.** It contains an unprompted "What this is — and what it is not" section stating that every capability is a *classical, deterministic, CI-verified computation*, that "quantum" refers to classical simulation and not physical hardware, and — critically — this line:

> Grover-style search here is a classical simulation whose iteration count follows the standard Θ(√N) analysis; large marked fractions needing few iterations is a textbook property, not supremacy.
> 

That is the correct claim boundary, written by the team, before any external challenge. `grover_search.py` carries an explicit `Claim lane: INTERNAL` docstring and states that on classical hardware each iteration costs O(N) so no speedup is achieved. **This is the standard the rest of the record set should be raised to.**

**Independently executed test results** (my runner, not theirs):

| Result | Count |
| --- | --- |
| Passed | **1,320** |
| Assertion failures | 1 |
| Errors | 4 (3 require a live API server; 1 real defect) |
| Unrunnable — missing `scipy` / `hypothesis` / `fastapi` | 38 files |

1,320 passing assertions executed under an independent harness is a real result. The 38 unrunnable files are a sandbox limitation, not a repository defect.

**Grover is implemented correctly.** Measured directly:

| N | Iterations used | (π/4)√N | P(target) |
| --- | --- | --- | --- |
| 64 | 6 | 6.3 | 0.9966 |
| 256 | 12 | 12.6 | 0.9999 |
| 1024 | 25 | 25.1 | 0.9995 |
| 4096 | 50 | 50.3 | 0.9999 |

The amplitude amplification is textbook-correct and the iteration count tracks √N exactly. This is real mathematics, correctly coded.

## 3. Defects found — ordered by commercial exposure

### 3.1 `quantum_amplitude_estimation()` is vacuous — HIGH

In `amplitude_amplification.py`, this function returns `np.sum(np.abs(state)**2)` — the norm of a normalised state vector, which is **1 by construction**. Measured across seven targets including out-of-range and negative values:

```
target        0 -> 1.000000000000
target        7 -> 1.000000000000
target   999999 -> 1.000000000000
target       -5 -> 1.000000000000
distinct values returned : 1
```

It returns the same constant for every possible input, including inputs that are not in the search space. **It carries zero information.** This is the same defect class as the coin-flip-passable GHZ test: a function that cannot fail, and therefore cannot evidence anything.

### 3.2 The holographic compressor delivers exactly half its requested ratio — HIGH

`HolographicCompressor(ratio=R)` stores each retained element as an `(int64 index, float64 value)` record — **16 bytes to preserve 8 bytes of payload**. The effective ratio is therefore always `R/2`, by construction and independent of the data:

| Requested | Effective (measured) |
| --- | --- |
| 10× | 5.00× |
| 100× | 50.00× |
| 1000× | 500.00× |

The code's own `metrics()` reports this honestly, and the pipeline logs print `requested=1000x effective=42.67x`. The team is not hiding it. But **any external material quoting the requested ratio rather than the effective one is overstating by 2× or more.**

### 3.3 "Holographic" and "spectral" are misnomers — MEDIUM

The docstring describes "deterministic top-k **spectral** retention". Verified directly: the retained index set is **identical** to plain top-k by absolute value of the raw array. No basis transform of any kind is applied. It is magnitude thresholding. The technique is legitimate; the name will not survive a technical reviewer.

### 3.4 Hardcoded difficulty — MEDIUM

`estimate_solutions()` contains `difficulty = 10  # Simplified`. Consequence: the solution count is always `N/1024` and the optimal iteration count is **25 regardless of search space size**, including at N = 2³². Also note `search_space=2**32` is silently clamped to 2²⁰.

### 3.5 Broken export — LOW but trivially fixable

`test_yang_mills_unified.py` cannot be collected: `cannot import name 'UnifiedQuantumSystem' from 'quantum_compute_substrate'`. The module `unified_quantum_system.py` exists but is not exported from `__init__.py`. This test has therefore not run in CI.

### 3.6 Boilerplate `SECURITY.md` — LOW, but visible

`SECURITY.md` is the **unedited GitHub template**, still reading "Use this section to tell people…" and listing fictional versions 5.1.x / 4.0.x. For an organisation selling defence-grade assurance, this is the first file a government reviewer opens.

### 3.7 `HYBA_Platform_Scope` contradicts the README — CRITICAL

The repository root contains a 39 KB document, `HYBA_Platform_Scope`, whose claims are irreconcilable with the disciplined README sitting beside it. Extracts, verbatim:

> Replacing 19+ Systems with One **Magic Code** … **Cost Reduction**: $5M+ annually … **Magic Code Efficiency**: 98% cost reduction
> 

> **AGI Diagnostics**: Quantum-enhanced medical analysis with 99% accuracy
> 

> **Drug Discovery**: P vs NP algorithms for molecular modeling
> 

> **Risk Management**: Quantum-enhanced portfolio optimization with 99.9% VaR accuracy
> 

It asserts replacement of OpenAI, Anthropic, Gemini, Azure AI, SageMaker, Tableau, PowerBI, Qlik, Looker, SAS, SPSS, R, Jupyter, Matlab, Snowflake, Databricks, Spark, H2O.ai and DataRobot — and separately Epic, Cerner, Bloomberg, SAP and BlackRock Aladdin.

Three distinct problems, in ascending order of severity:

1. **The code examples import module names that are absent — but the capability is not.** `core_engine.agi_interface`, `interface_marketplace.healthcare` and `executive_intelligence_dashboard` return zero matches. **However**, `quantum_substrate/intelligence/engine.py` implements `UnifiedIntelligenceEngine.analyze(domain, data, context)` over a `SUPPORTED_DOMAINS` tuple, with the docstring "One backend serves every sector … Sector is a request parameter, never a code path." That is the same architecture the scope document describes, under a different name. This is **name drift between document and code, not fabrication** — an important distinction, and my initial reading of it was too harsh.
2. **Every headline number is unsourced and unbacked by any test.** "99% accuracy", "99.9% VaR accuracy", "98% cost reduction" have no CI assertion anywhere in the 1,320 tests that do pass. This breaches the repository's own stated policy that "any stated property must be an assertion in CI".
3. **"AGI Diagnostics … 99% accuracy" is a regulated medical-device claim.** Under EU MDR and FDA SaMD rules, software making diagnostic claims requires conformity assessment and clinical evidence. Publishing this in a public repository creates regulatory exposure that is independent of whether anyone buys the product.

<aside>
🛑

**Corrected recommendation.** My first instinct was to delete this file. That was wrong. The right action is to **re-point it at the code that actually shipped**: replace the phantom `core_engine` / `interface_marketplace` examples with real `intelligence.engine.UnifiedIntelligenceEngine` calls, and strike every unsourced percentage. The architecture claim survives; the numbers and the medical-diagnostic language do not. What must not survive contact with a reviewer is the *gap* between a disciplined README and an undisciplined scope doc in the same repository root.

</aside>

## 4. What I did not find

Being even-handed: I found **no** evidence of fabricated results, no stubbed functions returning hardcoded success, and no tests asserting claim *strings* rather than behaviour — all defect classes present in the earlier mining codebase. The compression reconstruction error at high ratios is poor on Gaussian noise, but white noise is incompressible by construction and that is **not** a fair test; it is not counted as a defect here.

## 5. Disposition

| Item | Lane | Action |
| --- | --- | --- |
| 1,320 independently executed passing tests | EXTERNAL | Quotable, with the runner and count stated |
| README claims-discipline section | EXTERNAL | Promote to the standard for all repos |
| Grover correctness (Θ(√N) iteration scaling) | EXTERNAL | Quotable as *correctness*, never as speedup |
| Compression ratios | BOUNDED | Quote **effective** ratio only, never requested |
| `quantum_amplitude_estimation` | RESTRICTED | Remove or reimplement; cite nowhere |
| "Holographic" / "spectral" naming | RESTRICTED | Rename to top-k magnitude retention |
| D13 φ-resonance | INTERNAL | No supporting code in canonical repo; suspension upheld |

<aside>
⚠️

**Standing rule reaffirmed — tests must be able to fail.** `quantum_amplitude_estimation` returning a mathematical constant for all inputs is the third instance of this defect class found in this programme, after the GHZ correlation test and `assert isinstance(is_intact, bool)`. Recommend the control-arm rule be extended into a CI check that flags any test whose assertion cannot discriminate between correct and incorrect behaviour.

</aside>