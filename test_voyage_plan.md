# Test Plan — Repaired Intelligence Voyage (branch repair/A-intelligence)

## Scope
End-to-end verification of the TOE/CIaaS intelligence voyage over real HTTP:
predict/explain/forecast/causal → decision_id → feedback → durable learned-state
handoff across a server restart → fail-closed replay protection.

## Method
- `server_boot.py`: boots `CIaaSServer(service=CIaaSService(runtime=TOEIntelligenceRuntime(config)))`
  with `feedback_state_path` set, prints `STARTUP_HEALTH <json>` (runtime.health()) then serves.
- `voyage.py`: subprocess orchestrator — starts instance 1, runs assertions over
  `urllib` HTTP, kills it, starts instance 2 with the same state path, runs
  restart assertions. All HTTP assertions have expected values below.
- Auth: no `CIAAS_API_KEY` configured → key check skipped (dev mode);
  `X-CIAAS-Tenant` header is still required (401 `missing_tenant` without it).
- State file: `tmp_test_voyage/fb_state.json` (deleted before the run).

## Assertions

### Instance 1 (fresh state path)
1. `POST /api/v1/ciaas/predict` body `{"payload":{"series":[0.1,0.4,0.2,0.9,0.5,0.7,0.3,0.8]}}`
   → **PASS iff** HTTP 200, `ok:true`, non-empty `decision_id` string (= D1),
   `receipt.receipt_id` present, `result.state_tomography` present.
   *Regression target: previously no decision_id was returned, so feedback was unreachable.*
2. Same for `/explain`, `/forecast`, `/causal` → each **PASS iff** 200 + `ok:true`
   + distinct `decision_id` (D2,D3,D4, all ≠ D1 and each other).
3. `GET /healthz` → 200; record body. Expected `status:"ok"`, `engine_available:true`.
   NOTE: `learned_module_performance`/`feedback_state` are NOT in the /healthz
   handler (handle_health only returns status/engine_available/degraded) — assert
   those on the STARTUP_HEALTH print instead (`runtime.health()`), and report the
   HTTP-surface gap to the lead.
4. STARTUP_HEALTH (instance 1): **PASS iff** `feedback_available:true`,
   `learned_module_performance` key present (empty {} ok pre-learning),
   `feedback_state.path` == state path, `feedback_state.restored` == null.
5. `POST /api/v1/ciaas/feedback` body `{"payload":true,"metadata":{"decision_id":D1}}`
   → **PASS iff** HTTP 200, `ok:true`, `result.calibration_score` is a float,
   `result.learning_signal` is a float, `result.recommendations` is a list.
   *Pre-fix behaviour was always "Decision ID not found".*
6. State file `fb_state.json` exists; parsed JSON **PASS iff**
   `model_parameters` is a non-empty dict, `counts.decisions >= 4`.
7. Negative: `POST /feedback` with `metadata.decision_id="totally-bogus-id"`
   → **PASS iff** non-2xx (422), `ok:false`, `error.message` contains
   "Decision ID totally-bogus-id not found". Must NOT be 500.
8. Negative: `POST /predict` with malformed JSON body `{not json`
   → **PASS iff** HTTP 4xx (400, code `body_error`), not 5xx.
9. Negative: `POST /predict` without `X-CIAAS-Tenant` → **PASS iff** 401.
10. Re-feedback on D1 (already processed) → **PASS iff** ok:false
    "has already been processed" — decision ids are single-use.

### Instance 2 (restart, same state path)
11. STARTUP_HEALTH (instance 2): **PASS iff** `feedback_state.restored` is a dict
    with `restored:true`, `model_parameters` count > 0, and
    `learned_module_performance` non-empty (learned params carried over).
12. `GET /healthz` → 200 (server alive after restore).
13. `POST /feedback` with OLD D1 → **PASS iff** ok:false,
    "Decision ID ... not found" — pre-restart ids must not resurrect
    (fail-closed replay). Must NOT return ok:true.
14. New `POST /predict` → D5; `POST /feedback` with D5 → **PASS iff** ok:true —
    the loop still functions post-restore.

## Evidence
- Full stdout/stderr of the orchestrator saved to `tmp_test_voyage/voyage_output.log`.
- No screen recording (shell-only API testing per guidance — recording would show an idle desktop).
