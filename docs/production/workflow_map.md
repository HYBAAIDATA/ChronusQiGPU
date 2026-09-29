# Workflow map — actual entry points, responsibilities, lifecycle, journeys

Pin: `e09afab`. Wires marked [verified] only where runtime evidence exists at
baseline; static metadata claims stay labelled.

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

## Operator journeys (Owner B evidence pending)

| Scenario | Expected honest behavior | Status |
|---|---|---|
| boot without stratum identity | StartupConfigError exit 1 (fail-closed) | [verified baseline: documented + code-read; runtime recheck by B] |
| boot placeholder env, no device | API serves; workers `armed_no_device`; hashrate = policy string; no fabricated state | PENDING-B |
| start→device-ready→compute→pool-ready→candidate | real evidence chain end-to-end | BLOCKED (no device) |
| stop during compute/campaign/recovery | cessation visible; cleanup exercised | PENDING-B |
| Salamander fault→repair→verify | recovery verified by new observation before resume | PENDING-B |
| CPU↔device route change | correct results + explicit route/fallback evidence | PENDING-B |
| pool reject/timeout/accept | distinct outcomes, correct counters | PENDING-B |
| browser reconnect | backend evidence reconstructs progress | PENDING-B |
| unauthorized direct request | denied independent of UI | PENDING-B |
| persistence/restore across restart | runtime_config + sidecars reload honestly | PENDING-B |

## Agent responsibilities (live modules)

- `Intelligence.agentic_mining` — 6-phase autonomous workflow (fabric label)
- `Intelligence.agentic_controller` — solver dispatch decisions (verified: self_test)
- `Intelligence.self_optimizing_agent` — tuner (unittest gate exists)
- `Intelligence.self_healing_agent` — repair loop (unittest gate exists)
- `Intelligence.salamander` / `salamander_engine`/`salamander_control` — engine + transaction layer (engine in platform py-modules; transaction layer idle)
- `mla1517.mining.chooser` — evidence-driven order selection
- `toe.bridge` → `IntelligenceController` — advisory analysis on vault records
- `registry` — 45-module registry
