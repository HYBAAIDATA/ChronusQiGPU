# Hub ↔ Repo Map — Engineering Standard & Evidence

<aside>
🏛️

**Purpose:** Cross-reference the HYBA DATA Hub with exact **repository paths** so readers without repo access still know where code, tests, CI, and evidence live.  

**Company:** HYBA Data · **Category:** CIaaS (not SaaS)  

**Board:** Andre Taylor-Morris

</aside>

---

## BLUF

GitHub Actions produces a downloadable **evidence pack**. Hub pages cite **repo paths**. Code elevates to documentation. Quantum is **ubiquitous** (not mining-bound). Mining is **not** a product surface.

---

## Delivery doctrine (locked)

| Rule | Position |
| --- | --- |
| Not SaaS | CIaaS |
| Onsite client engineers for integration | **No** |
| Fortune training fees / training spin-off | **No** — adaptive UI |
| Maintenance fees | **No** |
| Commercial | Gain-share on **measured** savings |
| Quantum | Ubiquitous Hilbert maths; hardware-agnostic |
| Mining | Not a product surface in this repo |

---

## CI/CD (pull a run as evidence)

| What | Repo path |
| --- | --- |
| **Primary evidence workflow** | `.github/workflows/hyba-data-engineering-standard.yml` |
| Trifecta + Quantum CI | `.github/workflows/hyba-data-trifecta-cicd.yml` |
| Workflows index | `.github/workflows/README.md` |
| Evidence pack (generated on run) | `artifacts/hyba_data/GITHUB_EVIDENCE_PACK.json` |
| Artifact name on Actions | `hyba-data-engineering-evidence` |

**How to present evidence:** open the Actions run URL → download artifact → cite `pass_flags` + `github.run_url` from the pack.

---

## Test suite (organized to engineering standard)

| Suite | Repo path |
| --- | --- |
| Engineering standard master suite | `tests/hyba_data/test_engineering_standard_suite.py` |
| Suite README | `tests/hyba_data/README.md` |
| Elevation gates | `python_backend/hyba_data/test_elevation_standard.py` |
| Claim closures | `python_backend/hyba_data/test_claim_closures.py` |
| Honest quantum | `tests/hyba_ciaas/test_honest_quantum.py` |
| Quantum neural / CFT / supremacy / QATL | `tests/hyba_ciaas/test_quantum_*.py` |
| CIaaS full suite | `tests/hyba_ciaas/test_ciaas_full_suite.py` |
| E2E wired | `tests/hyba_ciaas/test_hyba_e2e_wired.py` |

**Local run:**

```bash
export PYTHONPATH=python_backend
python3 tests/hyba_data/test_engineering_standard_suite.py
python3 tests/hyba_ciaas/test_honest_quantum.py
```

---

## Code modules (standards)

| Module | Repo path |
| --- | --- |
| Sealed claims | `python_backend/hyba_data/sealed_claims.py` |
| Claim closures | `python_backend/hyba_data/claim_closures.py` |
| Elevation report | `python_backend/hyba_data/elevation.py` |
| Metric card | `python_backend/hyba_data/sealed_metric_card.py` |
| Savings metering | `python_backend/hyba_data/savings_metering.py` |
| Data-class gate | `python_backend/hyba_data/data_class_gate.py` |
| **Honest quantum** | `python_backend/hyba_data/quantum_honest.py` |
| Honest quantum demo | `python_backend/hyba_data/honest_quantum_demo.py` |
| Quantum substrate / QNN / CFT / supremacy / QATL | `python_backend/hyba_data/quantum_*.py` |
| Platform + delivery doctrine | `python_backend/hyba_substrate/platform.py` |
| Adaptive UI | `python_backend/hyba_substrate/adaptive_ui.py` |
| Trifecta demo | `python_backend/hyba_ciaas/demo_trifecta.py` |
| E2E customer demo | `python_backend/hyba_ciaas/demo_e2e.py` |
| Master control plane | `python_backend/hyba_data/master.py` |
| Repo posture | `REPO_POSTURE.md` |

---

## Demos (kept — quantum restored)

| Demo | Repo path | Status |
| --- | --- | --- |
| Honest quantum demo | `python_backend/hyba_data/honest_quantum_demo.py` | **Active** — ubiquitous quantum; not mining |
| Trifecta (Pulvini · Φ-UFE · Hermes) | `python_backend/hyba_ciaas/demo_trifecta.py` | Active |
| CIaaS e2e customer journey | `python_backend/hyba_ciaas/demo_e2e.py` | Active |
| Quantum plane batteries | via `hyba_data.master`  • `tests/hyba_ciaas/test_quantum_*` | Active |

### Clarification (mining purge)

**Removed:** mining product implementation, mining tests/CI paths, pool/stratum surfaces, mining-as-proof.  

**Not removed (and restored if touched):** honest quantum, quantum substrate/QNN/CFT/supremacy/QATL, product demos.  

**Why quantum looked thin briefly:** honest quantum was re-homed off `pythia_mining` into `hyba_data.quantum_honest` so quantum no longer depends on mining packages. Quantum remains ubiquitous.

---

## Evidence artifacts (after CI or local run)

| Artifact | Repo path |
| --- | --- |
| GitHub evidence pack | `artifacts/hyba_data/GITHUB_EVIDENCE_PACK.json` |
| Claim closures | `artifacts/hyba_data/CLAIM_CLOSURES.json` |
| Code elevation | `artifacts/hyba_data/CODE_ELEVATION_REPORT.json` |
| M1 seal | `artifacts/hyba_data/M1_SEAL.json` |
| Honest quantum demo report | `artifacts/hyba_data/HONEST_QUANTUM_DEMO_REPORT.json` |
| Honest quantum test report | `artifacts/hyba_data/honest_quantum_report.json` |
| Engineering suite report | `artifacts/hyba_data/ENGINEERING_STANDARD_SUITE.json` |
| Master status | `artifacts/hyba_data/MASTER_STATUS.json` |
| Mining purge manifest | `artifacts/hyba_data/MINING_PURGE_MANIFEST.json` |

---

## Related hub pages

- [HYBA Data — Code Elevation Pack (Engineering Standard)](HYBA%20Data%20%E2%80%94%20Code%20Elevation%20Pack%20(Engineering%20Stand%20080cf1c058b14a8692d9431695ed928f.md)
- [HYBA Data Only — Mining Purge & Claim Closures](HYBA%20Data%20Only%20%E2%80%94%20Mining%20Purge%20&%20Claim%20Closures%20601ef7c53bd04c6691385e8b6639d941.md)
- [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)
- [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md)
- [Category & Delivery Doctrine — CIaaS](Category%20&%20Delivery%20Doctrine%20%E2%80%94%20CIaaS%20d0b437e807074c5d9342f6b922660d07.md)