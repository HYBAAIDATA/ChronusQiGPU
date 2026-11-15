# Synthetic Audit Report — Chronus Quantum iGPU v36

**Date:** 2026-11-09
**Audit scope:** `src/chronus/`, `frontend/`, `src/chronus/service/`, build config, scripts
**Excluded:** `vendor/`, `archive/`, `chronus_source_backup/`

---

## Phase 1 — Synthetic Audit Findings

### Table 1: Synthetic Blocks Detected in Production Paths

| File | Line | What it fakes | Replacement |
|------|------|---------------|-------------|
| `src/chronus/execution/master_e2e_engine.py` | 460 | Hardcoded genesis block Merkle Root (`4a5e1e4b...`) instead of live block header | Request real blockchain header via RPC or allow upstream pool to supply `coinb1` + `merkle_branch`; compute Merkle root from given data |
| `src/chronus/execution/master_e2e_engine.py` | 468 | Hardcoded `target_nonce = 2083236893` (0x7c2bac1d) | Replace with pool-supplied `extranonce2` range from `mining.notify`; do not hard-code genesis nonce |
| `src/chronus/execution/master_e2e_engine.py` | 467-474 | Simulates Myrmidon Swarm with `winning_searcher` always found by scanning for a fixed nonce | Real candidate search is performed in `mining.search_nonce_range()` against the actual target; no pool simulation |
| `src/chronus/execution/master_e2e_engine.py` | 504-506 | Logs `ALL DECISION CONTRACT POINTS & STRATUM HANDSHAKES PASSED 100% PERFECTLY!` — claims 100% external acceptance without any external verification | Remove hardcoded success claims; only log externally verified results (stratum `mining.submit` returns `true`) |
| `src/chronus/execution/mining_admin.py` | 57-62 | Counters `accepted_shares`, `rejected_shares`, `blocks_found`, `anomaly_injected`, `dsw_healed` never incremented by real mining work | Real counters must be incremented by the Stratum `submit` result (accepted/rejected by pool), not by admin convenience methods |
| `src/chronus/execution/mining_admin.py` | 158-162 | `inject_anomaly()` sets `anomaly_injected=True` without any actual network or consensus perturbation | Remove this method; move anomaly handling into real Stratum session error handling |
| `src/chronus/execution/mining_admin.py` | 164-168 | `execute_dsw_heal()` sets `dsw_healed=True` with 1-cycle DSW instanton claim | Remove; replace with real recovery process that monitors pool connectivity and share acceptance after a failure |
| `src/chronus/execution/mining_admin.py` | 252-253 | `avoided_loss_gbp = 116120.00 if counterfactual_weight > 0 else 0.0` — deterministic counterfactual | Compute from actual electricity tariff and hashrate data, or remove |
| `src/chronus/execution/mining_admin.py` | 241-243 | `h1_error = 1.4142 if anomaly_injected else 0.0000` and `resonance_pct` — fabricated sheaf obstruction | Compute sheaf cohomology from actual message-passing traces; return measured values |
| `frontend/app/mining/page.tsx` | ~37-40 | Hardcoded state `baseHashrate: 712.80`, `activeWarps: 72` on component mount | Initialize from live API `/v1/mining/admin/status`; do not preseed with constants |
| `frontend/app/mining/page.tsx` | ~68-69 | `anomalyInjected` and `dswHealed` booleans preseeded false | Remove; derive from API telemetry |
| `frontend/app/mining/page.tsx` | 852-866 | Buttons "Inject Reorg" and "Execute DSW Heal" | Remove; replace with actual health-check/failure payloads |
| `frontend/lib/api-client.ts` | 175 | `simulatePatroclusMining()` posts to `/v1/mining/admin/patroclus/simulate` which runs `execute_master_end_to_end()` | Point to real pool list endpoint, or disable and replace with actual pool management UI |
### Table 2: Unresolved Synthetic Blocks (Legacy / Backup)

| File | Line | What it fakes | Recommendation |
|------|------|---------------|----------------|
| `archive/legacy/master_repo/console/chronus_console.htm` | 2099 | `// OVID Durable Storage Mock Bucket` | Ignore — legacy archive file |
| `archive/legacy/master_repo/console/chronus_console.htm` | 2269, 2347, 2404, 2459 | `signEd25519Mock`, `verifyEd25519Mock` | Ignore — legacy HTML console mock |
| `chronus_source_backup/chronus-quantum-igpu/src/chronus/security/al_haras/*.py` | — | Various `sign_mldsa("mock_mldsa_key", ...)`, `verify_ed25519(b"mock_pub", ...)`, `Poseidon2FiatShamirIVCFolder.fold_with_transcript_binding(u1_mock, u2_mock, T_vec)` | Documentation/spec files. Do not ship for production. |
| `chronus_source_backup/chronus-quantum-igpu/docs/directives/*.md` | — | Engineering directives and close-out criteria | Governing docs; follow directive that production code must not contain mock cryptography |

---

## Phase 2 — Wiring Map

### UI-to-API Mapping

| UI Element / Screen | Frontend File | Route | Handler | Service | Data Store | External Dependency |
|---------------------|---------------|-------|---------|---------|------------|---------------------|
| Dashboard / Overview | `frontend/app/page.tsx` | `GET /health/ready` | `health.py::readiness_probe` | `service/routers/health.py` | — | `CHRONUS_EXECUTION_BASE_URL` |
| Mining Dashboard | `frontend/app/mining/page.tsx` | `GET /v1/mining/admin/status` | `mining_admin.py::get_mining_status` | `execution/mining_admin.py` | In-memory | — |
| Start Mining | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/start` | `mining_admin.py::start_mining` | `execution/mining_admin.py` | In-memory | — |
| Stop Mining | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/stop` | `mining_admin.py::stop_mining` | `execution/mining_admin.py` | In-memory | — |
| Configure Capacity | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/configure` | `mining_admin.py::configure_capacity` | `execution/mining_admin.py` | In-memory | — |
| Configure Intelligence | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/intelligence` | `mining_admin.py::configure_intelligence_modes` | `execution/mining_admin.py` | In-memory | — |
| Causal Intervention | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/intervene` | `mining_admin.py::apply_causal_intervention` | `execution/mining_admin.py` | In-memory | — |
| Stealth Config | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/stealth` | `mining_admin.py::configure_stealth` | `execution/mining_admin.py` | In-memory | — |
| Patroclus Telemetry | `frontend/app/mining/page.tsx` | `GET /v1/mining/admin/patroclus` | `mining_admin.py::get_patroclus_telemetry` | `execution/mining_admin.py` | In-memory | — |
| Simulate Patroclus | `frontend/app/mining/page.tsx` | `POST /v1/mining/admin/patroclus/simulate` | `master_e2e_engine.py::execute_master_end_to_end()` | `execution/master_e2e_engine.py` | In-memory | **FAKE POOLS** |

### API Route Index (Backend)

| Route | Method | Auth | Handler |
|-------|--------|------|---------|
| `/` | GET | No | Root endpoint with service status |
| `/health` | GET | Yes | `health.py::get_health` |
| `/health/ready` | GET | No (public readiness) | `health.py::readiness_probe` |
| `/v1/mining/admin/status` | GET | Yes | `mining_admin.py::get_mining_status` |
| `/v1/mining/admin/start` | POST | Yes | `mining_admin.py::start_mining` |
| `/v1/mining/admin/stop` | POST | Yes | `mining_admin.py::stop_mining` |
| `/v1/mining/admin/configure` | POST | Yes | `mining_admin.py::configure_capacity` |
| `/v1/mining/admin/intelligence` | POST | Yes | `mining_admin.py::configure_intelligence_modes` |
| `/v1/mining/admin/intervene` | POST | Yes | `mining_admin.py::apply_causal_intervention` |
| `/v1/mining/admin/anomaly/inject` | POST | Yes | `mining_admin.py::inject_anomaly` |
| `/v1/mining/admin/anomaly/heal` | POST | Yes | `mining_admin.py::execute_dsw_heal` |
| `/v1/mining/admin/patroclus` | GET | Yes | `mining_admin.py::get_patroclus_telemetry` |
| `/v1/mining/admin/stealth` | POST | Yes | `mining_admin.py::configure_stealth` |
| `/v1/mining/admin/patroclus/simulate` | POST | Yes | `master_e2e_engine.py::execute_master_end_to_end` |

| `frontend/lib/api-client.ts` | 95-105 | CBDCS, orbital telemetry, ZK neural, T-ISA unrelated demo methods | Remove from `ChronusAPIClient` or relocate to correct domain clients |
