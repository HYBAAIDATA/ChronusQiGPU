# Workflow map — actual entry points, responsibilities, lifecycle, journeys

Pin: `e09afab` (baseline); journey evidence recorded at `73a716d`. Wires
marked [verified] only where runtime evidence exists; static metadata claims
stay labelled.

## Entry points

| Entry | Kind | Verified |
|---|---|---|
| `python main.py --host … --web-root dist/public` | control API + static UI (root shim → `mla1517_platform_v3.4/python/control_api.py`) | [verified: wheel + source boot contract] |
| `pythia-api` (console script) | same as above via installed package | [verified: wheel --help] |
| `pythia-mine` → `mining_runtime:main` | headless Stratum miner (fail-closed) | [verified: wheel --help] |
| `headless_miner.py --device … --submit` | hardware miner, MMIO required | NOT_RUN (no device) |
| `python -m mla1517.remote_gpu_agent` | remote OpenCL agent (remote_opencl_v1) | NOT_RUN locally; blueprint documents |
| `python -m mla1517.prime …` | PRIME CLI (deploy/ingest/audit/reproduce real; feature/train/evaluate/promote/serve intentionally not_implemented, exit 2) | blueprint-documented |

## Backend call graph (verified by reading + import checks)

```
browser ─HTTP→ control_api.main (/api/* + statics)
                 ├─ startup_contract (fail-closed env validation)
                 ├─ system_fabric  (SUBSYSTEMS map, verification/selftest runners)
                 ├─ worker_lifecycle (arms spawn/retire/restart)
                 ├─ runtime_config (GET/PUT /api/v1/config, bounds-checked)
                 ├─ mining_runtime/coordinator → mla1517.mining.*
                 │     ├─ chooser (evidence→order) → solver (lane enum) → pow (sha256d)
                 │     ├─ toe_adapter (advisory context; fails closed per record)
                 │     └─ stratum client (negotiated job; only target accepts share)
                 └─ salamander_* (self-healing), telemetry_daemon, heartbeat dir
```

## Operator journeys

| Scenario | Expected honest behavior | Status |
|---|---|---|
| boot without stratum identity | StartupConfigError exit 1 (fail-closed) | **PASS** — executed: every missing env var aborts before serving (S1, headless evidence `phiminer_*` set @ `C:\Users\Administrator\screenshots`) |
| boot placeholder env, no device | API serves; workers report unavailable honestly; hashrate = policy string never a number; no fabricated state | **PASS** — 36 field-level asserts on `/api/v1/*`, `worker_unavailable` reason surfaces (S2) |
| operator UI standby/offline honesty | UI shows honest standby; flips to "API offline" within one poll when killed | **PASS** (S3, PNG evidence) |
| start→device-ready→compute→pool-ready→candidate | real evidence chain end-to-end | BLOCKED (no OpenCL device) |
| stop during compute/campaign/recovery | cessation visible; cleanup exercised | **PASS** — S5 baseline + B (PR #22): `try/finally retire_all` on every campaign exit, `campaign_record` preserved on non-completion, terminal `stopped` never `error`; SIGTERM/SIGBREAK now graceful (dead `__main__` handler removed) |
| Salamander fault→repair→verify | recovery verified by new observation before resume | **PASS** (B, PR #22): fault→ack-gated `retire`→RECOVERING/`recovery_id`→quiet observation→probation+3 self-tests→`readmit`; ack-fail=no repair; MIN_LANES→`degraded_mode` |
| CPU↔device route change | correct results + explicit route/fallback evidence | BLOCKED (no device) |
| pool reject/timeout/accept | distinct outcomes, correct counters | **PASS** (B, PR #22): real loopback StratumClient — accept→`true`, reject→`false`, timeout→`OUTCOME_UNKNOWN` (no invented acks); stale-job submit refused; failover once/cooldown/cancel |
| browser reconnect | backend evidence reconstructs progress | **PASS** (S6 + B recorded both consoles live vs real API) |
| unauthorized direct request | denied independent of UI | **PASS @bfceb68** — S4 found zero HTTP auth at baseline (real finding); the boundary landed via parallel work (`03f62ec` + mediation): `control_authorization` requires `Authorization: Bearer $EUCLID_ADMIN_API_KEY` with `hmac.compare_digest`, fail-closed 403 when no key configured, dev opt-out only via explicit `PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL=1`. B (PR #22) additionally fixed `pythia_guardian_api` binding `None` → all privileged AL HARAS routes were permanently 503; now live 400/402/403→allow verified. Verified by code-read + B's live deny checks |
| persistence/restore across restart | runtime_config + sidecars reload honestly | **PASS** (B, PR #22): config durable + corrupt→defaults; MiningSession share-log restore |
| honest telemetry | hashrate only from executed work; zeros real | **PASS** (B, PR #22): `measured_hs_avg:null` when unmeasured (0.0 is a real measurement, never a default); stale sidecars excluded via 30s TTL |

## Agent responsibilities (live modules)

- `Intelligence.agentic_mining` — 6-phase autonomous workflow (fabric label)
- `Intelligence.agentic_controller` — solver dispatch decisions (verified: self_test)
- `Intelligence.self_optimizing_agent` — tuner (unittest gate exists)
- `Intelligence.self_healing_agent` — repair loop (unittest gate exists)
- `Intelligence.salamander` / `salamander_engine`/`salamander_control` — engine + transaction layer (engine in platform py-modules; transaction layer idle)
- `mla1517.mining.chooser` — evidence-driven order selection
- `toe.bridge` → `IntelligenceController` — advisory analysis on vault records
- `registry` — 45-module registry
