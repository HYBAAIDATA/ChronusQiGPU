# Documentation Index — Fresh Implementation Baseline (v2)

**Source**: `git rev-parse HEAD (07c563e8)` | **Seeds**: `[1337, 42, 2026]` | **Status**: **MEASURED**  
**Repository**: `PhiEnterprise-main`  
**Base Branch**: `main` | **Working Branch**: `docs/fresh-from-implementation-20261019`  

---

## 1. Overview & Architectural Grounding

This documentation suite supersedes all legacy documents in the repository. All architectural claims, mathematical definitions, performance metrics, and operational procedures contained herein are derived strictly from verified executable code in `euclid/`, `Intelligence/`, `chronus/`, `millennium/`, `tensor/`, `quantum_compute_substrate/`, `turing_universal_quantum_computer/`, `src/api/routers/`, and verified pytest test suites (`tests/`).

Historical documentation, superseded research notes, and legacy audit documents have been relocated to [`_archive_docs_legacy_20261019/`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/_archive_docs_legacy_20261019) with pointers recorded in [`DOCS_GAP_TABLE.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/DOCS_GAP_TABLE.md).

---

## 2. Document Map

The source/seeds/status banner above records the original v2 baseline, not a
current qualification of every subsequent addition. The readiness supplement
below documents the engine merged in PR #142; its local assessment tests are not
whole-system production, hardware, pool or publication verification.

| Document | Title | Primary Source of Truth | Status |
| :--- | :--- | :--- | :--- |
| [`01_SYSTEM_TRUTH.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/v2/01_SYSTEM_TRUTH.md) | System Truth & Authority Boundaries | [`toe/intelligences/authority_boundary.py:1-100`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/toe/intelligences/authority_boundary.py#L1-L100), [`src/api/main.py`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/src/api/main.py), [`chronus/mla1517_platform/python/control_api.py`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/chronus/mla1517_platform/python/control_api.py) | **MEASURED** |
| [`02_EUCLID_IMPLEMENTED.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/v2/02_EUCLID_IMPLEMENTED.md) | EUCLID Implemented Cognitive Mechanics | [`euclid/cognition/reconciliation_gateway.py:1-400`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/euclid/cognition/reconciliation_gateway.py#L1-L400), [`Intelligence/recursive_self_learning.py:1-400`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/Intelligence/recursive_self_learning.py#L1-L400), [`src/api/routers/euclid_voice.py:1-250`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/src/api/routers/euclid_voice.py#L1-L250) | **MEASURED** |
| [`03_QUANTUM_TENSOR_STATUS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/v2/03_QUANTUM_TENSOR_STATUS.md) | Quantum Substrate & Tensor Reality | [`turing_universal_quantum_computer/`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/turing_universal_quantum_computer/), [`STRICT_QUANTUM_BOUNDARY.md:1-61`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/STRICT_QUANTUM_BOUNDARY.md#L1-L61), [`chronus/mla1517_platform/python/system_fabric.py:32`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/chronus/mla1517_platform/python/system_fabric.py#L32) | **MEASURED** |
| [`04_MILLENNIUM_EVIDENCE.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/v2/04_MILLENNIUM_EVIDENCE.md) | Millennium Probes & Discrete Computations | [`millennium/discrete/`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/millennium/discrete/), [`Intelligence/theoretical_foundations.py:380-450`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/Intelligence/theoretical_foundations.py#L380-L450) | **FINITE COMPUTATIONS** |
| [`05_RUNBOOKS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/v2/05_RUNBOOKS.md) | Operational Runbooks & Execution Harness | [`scripts/execute_sprint_1_to_4_pipeline.py`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/scripts/execute_sprint_1_to_4_pipeline.py), [`tests/`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/tests/) | **MEASURED** |
| [`06_GLOSSARY_BOUNDARIES.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/v2/06_GLOSSARY_BOUNDARIES.md) | Epistemic Glossary & Truth Classes | [`toe/intelligences/authority_boundary.py`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/toe/intelligences/authority_boundary.py), [`chronus/readiness.py:165`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/chronus/readiness.py#L165) | **MEASURED** |
| [`07_EVIDENCE_SCOPED_READINESS.md`](07_EVIDENCE_SCOPED_READINESS.md) | Evidence-scoped readiness: system impact and product distinction | [`tools/tomorrow_readiness.py`](../../tools/tomorrow_readiness.py), [`tests/test_tomorrow_readiness.py`](../../tests/test_tomorrow_readiness.py), [technical contract](../readiness/TOMORROW_READINESS_INDEX.md) | **IMPLEMENTED — assessment layer; not production certification** |

### Readiness documentation path

- Start with [system impact and product distinction](07_EVIDENCE_SCOPED_READINESS.md)
  for what changed, its relationship to TOE/EUCLID/PYTHIA/CHRONUS/SALAMANDER/
  AL HARAS/THESEUS, and supported product language.
- Use the [technical contract](../readiness/TOMORROW_READINESS_INDEX.md) for
  scoring, evidence scope, dependency rules, gate checks and CLI operation.
- Treat receipt-exporter integration and target-system validation as separate
  work. A maturity score or a healthy readiness probe is not release approval.

---

## 3. Legacy Documentation Archive

All previous markdown documents from `docs/` and root (except the inviolable governing directives [`OWNER_DECLARATIONS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/OWNER_DECLARATIONS.md), [`docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md), [`LICENSE`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/LICENSE), and active root doctrine files [`AGENTS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/AGENTS.md), [`GEMINI.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/GEMINI.md), [`STRICT_QUANTUM_BOUNDARY.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/STRICT_QUANTUM_BOUNDARY.md), and [`UNIVERSAL_PRINCIPLE_MAP.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/UNIVERSAL_PRINCIPLE_MAP.md)) have been relocated to `_archive_docs_legacy_20261019/`.
