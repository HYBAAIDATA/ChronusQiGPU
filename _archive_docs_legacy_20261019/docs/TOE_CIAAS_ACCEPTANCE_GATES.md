# CIaaS Acceptance Gates

> **Document**: `docs/TOE_CIAAS_ACCEPTANCE_GATES.md`
> **Date**: 2026-10-07
> **Status**: ALL GATES PENDING
> **Plan reference**: `docs/TOE_INTELLIGENCE_PRODUCTION_READINESS_PLAN.md` Section 10

Production readiness is achieved when gates A through H are all green.
Each gate requires a passing test or a generated report.  No gate may be
marked green by assertion alone.

---

## Gate A — CI Green

| Field | Value |
|-------|-------|
| **ID** | A |
| **Name** | CI Green |
| **Criteria** | All existing TOE/unit tests pass in CI |
| **Command** | `python -m pytest tests/ -q` |
| **Current status** | PENDING |
| **Blocking notes** | `pytest` not available in current environment; must be verified in CI pipeline |
| **Production implication** | Without green CI, no code change can be safely merged |

### Evidence required

- `pytest tests/ -q` exits 0
- No new failures vs baseline (1,640 passed, 16 skipped per production audit)
- `flake8 --count` returns 0

---

## Gate B — Stack-Collapse Proof Green

| Field | Value |
|-------|-------|
| **ID** | B |
| **Name** | Enterprise-stack collapse proof |
| **Criteria** | All 16 checks (T1–T16) in `experiments/toe_enterprise_collapse.py` pass |
| **Command** | `python experiments/toe_enterprise_collapse.py` |
| **Current status** | PENDING |
| **Blocking notes** | Must exit 0; result JSON must be versioned |
| **Production implication** | Proves the collapse is structural, not cosmetic |

### Evidence required

- Exit code 0
- `experiments/toe_enterprise_collapse_results.json` written and versioned
- All 10 sectors produce identical output schema (T3)
- Zero domain vocabulary in engine source (T11)
- 18+ intelligence outputs from one predict() call (T10)

---

## Gate C — Mining Consensus Boundary

| Field | Value |
|-------|-------|
| **ID** | C |
| **Name** | Mining consensus boundary |
| **Criteria** | TOE output never reaches SHA256d, target, header, nonce, or share |
| **Command** | `python -m pytest chronus/mla1517_platform/python/test_toe_consensus_boundary.py -q` |
| **Current status** | PENDING |
| **Blocking notes** | 7 boundary tests must pass; boundary token must be tamper-evident |
| **Production implication** | Prevents block invalidation and financial loss |

### Evidence required

- `TOEConsensusBoundaryError` raised on any consensus field
- Boundary token `TOE-BND-<sha256>` self-attests payload
- Tamper fails closed
- Vocabulary rejection (top-level and nested)
- `test_throttle_does_not_touch_consensus` passes (monkeypatches consensus to raise)

### Production invariant

TOE can influence "where to look first," never "what counts as valid."

---

## Gate D — Feedback Loop Wired

| Field | Value |
|-------|-------|
| **ID** | D |
| **Name** | Feedback loop receipts stored |
| **Criteria** | Decision/outcome/calibration receipts stored; bounded parameter updates |
| **Command** | `python -m pytest tests/test_toe_runtime.py -q` |
| **Current status** | PENDING |
| **Blocking notes** | `TOEIntelligenceRuntime` composition root must be wired and tested |
| **Production implication** | Without feedback, intelligence cannot learn from outcomes |

### Evidence required

- `TOEIntelligenceRuntime.predict()` records decision in `IntelligenceFeedbackCore`
- `record_outcome()` processes outcome and returns calibration report
- Evidence chain appends receipt on every prediction
- Parameter updates are bounded (no unbounded drift)
- Receipt contains: `receipt_id`, `tenant_id`, `payload_digest`, `result_digest`, `evidence_status`, `observe_only`, `production_ready`

### Files

- `toe/runtime.py` — composition root
- `tests/test_toe_runtime.py` — runtime tests
- `resonance_intelligence/feedback_core.py` — feedback core
- `euclid/evidence.py` — evidence chain

---

## Gate E — ASI Observe-Only

| Field | Value |
|-------|-------|
| **ID** | E |
| **Name** | ASI self-healing observe-only |
| **Criteria** | Self-healing runs in observe mode; zero destructive changes; two-stage approval gate |
| **Command** | `python -m pytest tests/test_asi_core.py -q` |
| **Current status** | PENDING |
| **Blocking notes** | ASI must never call fix/apply/implement methods without approval |
| **Production implication** | Prevents autonomous destructive changes |

### Evidence required

- `ASICore.capability_report()` returns availability and statistics only
- `SelfHealingEngine.start_monitoring()` is NOT called by default in runtime
- `SystemOptimizer.optimize()` creates actions but does not implement them
- `ContinuousWebLearner.start()` is NOT called by default in runtime
- No file deletion, code mutation, or config overwrite without explicit approval
- Two-stage escalation: observe → recommend → (approval) → quarantine → (approval) → act

### Hard gates

- `ASI_CAPABILITIES` includes only: `self_healing`, `novel_problem_solving`, `quantum_algorithm_creation`, `continuous_learning`, `system_optimization`
- `_PROBES` map calls only `get_health_report`, `get_stats`, `analyze_system` — never `fix`, `apply`, `implement`

---

## Gate F — Domain Pack Validated

| Field | Value |
|-------|-------|
| **ID** | F |
| **Name** | Domain pack validated |
| **Criteria** | Fixtures, negative controls, human review workflow per domain |
| **Command** | Per-domain eval suite (not yet built) |
| **Current status** | PENDING |
| **Blocking notes** | Each domain pack requires domain-specific validation before production claims |
| **Production implication** | Prevents false domain claims |

### Evidence required per domain

| Domain | Eval suite | Negative control | Human review |
|--------|-----------|-------------------|-------------|
| Islamic finance | Shariah compliance screening test | Non-halal instrument rejected | Shariah scholar review |
| Arabic NLP | Arabic benchmark (AraBERT-level) | Non-Arabic text handled | Linguist review |
| Cybersecurity | SIEM anomaly detection (FP rate < 5%) | In-distribution probe > anomaly | SOC analyst review |
| Logistics | Lead-time forecasting (MAPE < 15%) | Disruption detected vs normal | Logistics analyst review |
| Healthcare | Clinical vitals monitoring (sensitivity ≥ 90%) | Non-clinical data handled | IRB approval + decision-support-only labelling |
| Mining | Hash-rate prediction + anomaly detection | Consensus boundary test | Mining operator review |

### Domain packs must include

1. Domain-specific fixtures (telemetry shapes)
2. Negative controls (in-distribution vs anomaly)
3. Causal validation (planted driver ranked #1)
4. Drift test (graceful degradation under distribution shift)
5. Human review workflow (sign-off required)

---

## Gate G — Tenant/API Security

| Field | Value |
|-------|-------|
| **ID** | G |
| **Name** | Tenant/API security |
| **Criteria** | Auth, rate limits, payload limits, audit trail, tenant isolation enforced |
| **Command** | `python -m pytest tests/test_toe_ciaas_api.py -q` |
| **Current status** | PENDING |
| **Blocking notes** | CIaaS API must be fail-closed on auth, rate, payload, and tenant boundaries |
| **Production implication** | Prevents data breach, compliance violation, tenant leakage |

### Evidence required

- API key ≥ 32 chars, timing-safe comparison (`hmac.compare_digest`)
- Missing/short key → 401 (fail-closed)
- Unknown tenant → 403
- Rate limit: 60 req/min per tenant (configurable)
- Payload limit: 1 MB max body size
- Every response carries evidence receipt (digest, claim_id, confidence, source)
- Exportable audit trail (tenant can export all decisions/receipts)
- Health/readiness: `/healthz`, `/readyz`, Prometheus `/metrics`
- Tenant data isolation: per-tenant state vectors; Zeckendorf dedup within-tenant only

### Files

- `toe/ciaas_api.py` — CIaaS service + HTTP adapter
- `tests/test_toe_ciaas_api.py` — API tests
- `toe/runtime.py` — composition root (tenant validation)

---

## Gate H — Production Readiness Report

| Field | Value |
|-------|-------|
| **ID** | H |
| **Name** | Production readiness report generated |
| **Criteria** | Explicit true/false flags per domain; all gates A–G green |
| **Command** | Generate `docs/PRODUCTION_READINESS_REPORT.md` |
| **Current status** | PENDING |
| **Blocking notes** | Report must cite test results and evidence; no assertion-only flags |
| **Production implication** | Final sign-off for production deployment |

### Report structure

```markdown
# Production Readiness Report

Date: <ISO8601>
Generated by: CI pipeline

## Gate Summary

| Gate | Name | Status | Evidence |
|------|------|--------|----------|
| A | CI Green | PASS/FAIL | <test count> |
| B | Stack-Collapse Proof | PASS/FAIL | <exit code> |
| C | Mining Consensus Boundary | PASS/FAIL | <test count> |
| D | Feedback Loop Wired | PASS/FAIL | <test count> |
| E | ASI Observe-Only | PASS/FAIL | <test count> |
| F | Domain Pack Validated | PASS/FAIL | <per domain> |
| G | Tenant/API Security | PASS/FAIL | <test count> |

## Domain Readiness

| Domain | Ready | Eval | Negative Control | Human Review |
|--------|-------|------|-------------------|-------------|
| Mining | true/false | ... | ... | ... |
| Islamic finance | true/false | ... | ... | ... |
| Arabic NLP | true/false | ... | ... | ... |
| Cybersecurity | true/false | ... | ... | ... |
| Logistics | true/false | ... | ... | ... |
| Healthcare | true/false | ... | ... | ... |

## Verdict

PRODUCTION READY: true/false
```

### Production readiness is achieved when gates A through H are all green.

---

## Summary Table

| Gate | Name | Status | Command | File |
|------|------|--------|---------|------|
| A | CI Green | PENDING | `pytest tests/ -q` | CI pipeline |
| B | Stack-Collapse Proof | PENDING | `python experiments/toe_enterprise_collapse.py` | `experiments/toe_enterprise_collapse.py` |
| C | Mining Consensus Boundary | PENDING | `pytest test_toe_consensus_boundary.py` | `chronus/.../toe_signal.py` |
| D | Feedback Loop Wired | PENDING | `pytest tests/test_toe_runtime.py` | `toe/runtime.py` |
| E | ASI Observe-Only | PENDING | `pytest tests/test_asi_core.py` | `asi/asi_core.py` |
| F | Domain Pack Validated | PENDING | Per-domain eval suite | `toe/adapters/` (future) |
| G | Tenant/API Security | PENDING | `pytest tests/test_toe_ciaas_api.py` | `toe/ciaas_api.py` |
| H | Production Report | PENDING | Generate report | `docs/PRODUCTION_READINESS_REPORT.md` |

---

## New Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `toe/runtime.py` | TOEIntelligenceRuntime composition root | 799 |
| `toe/ciaas_api.py` | CIaaS API service + HTTP adapter | 474 |
| `tests/test_toe_runtime.py` | Runtime tests (20 tests) | 369 |
| `tests/test_toe_ciaas_api.py` | CIaaS API tests (18 tests) | 277 |
| `docs/TOE_CIAAS_ACCEPTANCE_GATES.md` | This document | — |

## Implementation Notes

### Composition Root (`toe/runtime.py`)

The `TOEIntelligenceRuntime` wires the five concentric loops:

1. **Inner loop** — `TOEBridge` (encode → |ψ⟩ → measure → evolve → compare → intervene)
2. **Middle loop** — `IntelligenceFeedbackCore` (record decision → process outcome → calibrate → attribute → learn)
3. **Outer loop** — `ASICore` hooks (observe-only: `capability_report()` only, never `start()` or `fix()`)
4. **Governance** — `EvidenceChain` (append-only hash-linked receipts)
5. **Delivery** — `UnifiedAnalyticsPlatform` (optional; requires connector credentials)

Every `predict()` / `explain()` / `forecast()` / `causal()` call flows through:
validate tenant → validate payload → check engine → execute TOE → normalise result → mining boundary check → build receipt → record decision + evidence → ASI observe-only probe → return response.

Fail-closed on: empty tenant, oversized payload, engine unavailable, consensus vocabulary in mining mode.

### CIaaS API (`toe/ciaas_api.py`)

Stdlib `http.server` adapter with:
- `GET /healthz`, `GET /readyz`, `GET /metrics`
- `POST /api/v1/ciaas/predict`, `/explain`, `/forecast`, `/causal`, `/feedback`
- `X-CIAAS-Tenant` + `X-CIAAS-Key` headers (≥32 chars, timing-safe)
- In-memory per-tenant rate limiter (single-process; replace with Redis for multi-process)
- 1 MB payload limit
- Every response carries evidence receipt

### Tests

- `tests/test_toe_runtime.py` — 20 tests covering predict, explain, forecast, causal, record_outcome, mining boundary, feedback, evidence, health, readiness, degraded mode, receipt tamper-evidence, ASI observe-only
- `tests/test_toe_ciaas_api.py` — 18 tests covering rate limiter, auth, tenant management, all operations, health/ready/metrics, error counting

### What Is NOT Claimed

- Tests have not been run in this environment (`pytest` unavailable)
- `production_ready` is `False` on every receipt and health report
- ASI background loops are NOT started by the runtime
- Mining consensus boundary is enforced at the runtime level (mirrors `toe_signal.py`)
- Multi-tenant isolation is by design (per-tenant state vectors) but not yet stress-tested at scale
- Domain packs (Gate F) require per-domain evaluation suites that do not yet exist
- Container packaging and SLA monitoring (Phase 7) are not yet implemented
