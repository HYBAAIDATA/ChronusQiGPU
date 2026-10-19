# M5 Session Handoff — 2026-10-09

For the Windows agent picking up from here. Repo: `~/Desktop/PhiMiner`,
branch `feat/lucas-scaling-extension` (HEAD ≈ `e0f94aae`; the branch is ahead
of `main` and contains it). Venv: `.venv-m5` (Python 3.12.15, arm64).

## LIVE state right now

- **A live `--mine --submit` miner is running** (launched by the operator with
  the strict M3 env). It completed `mining.authorize` against Braiins —
  **literal `Authorized: true` captured** — and is hashing at pool-set
  difficulty 2048. No share candidates yet (`pool_outcome: NO_CANDIDATE` —
  expected at that difficulty on CPU/software hashing). Do not kill it; it is
  the external-pool evidence leg.
- **Operator API/UI** serving `dist/public` at `http://127.0.0.1:3000`
  (booted with a distinct `PYTHIA_BOOT_LOCK=/tmp/pythia-ui/...` so it does not
  collide with the miner). `/readyz` 200, `/api/v1/mla1517/status` 200,
  `/api/v1/stratum/status` 200 (disconnected — it is not the miner),
  `/ready-to-mine` 503 honest.
- Durable state: `~/Library/Application Support/HYBA/PhiMiner/`
  (runtime_config.json digest `3fddfed5…`, causal_ledger.jsonl, heartbeats).
- Causal ledger shows digest-bound cycles SCAN→PLAN→MINE→VERIFY→EVALUATE,
  `chronus107_execution_evidence`, per-symbol implementation manifests,
  `substrate: cpu/native_c_midstate`, `execution_mode: resident_software`.

## Gates flipped green this session

- Preflight 11/11 mandatory PASS at `53d28663`
  (`artifacts/m5-transfer-preflight.json`).
- All three matrix collection errors fixed and committed:
  - `scripts/assert_gate_rollup.py`: merge `4292a511` had dropped the
    tamper-evident implementation (`load_manifest`, digest validation) —
    restored the `d306606b` superset.
  - `config/assurance-gates.json`: added missing `repo-ownership` gate.
  - `.github/workflows/promotion.yml`: `if-no-files-found: error` on the
    gate-results upload.
  - `tests/test_chronus_production_route.py`: migrated to the canonical exact
    substrate + sealed resident-hendrix plans (`compile_hendrix_plan` +
    `evidence_refs.resident_hendrix`).
  - `tests/test_a_mining_math.py`: approved `reference_execution` fixture for
    `mining.GroverStyleSearch`.
  - `tests/test_braiins_sv2.py`: bare sibling import per suite convention.
- Frontend: Node 22.20.0 user-space, `vite build` green, bundle served.
- **`kellogg` de-vendored** from `hyba-pythia-mining`: RECORD collisions = 0,
  `import kellogg` resolves via `hyba-kellogg-tensor`; `pip check` clean.
- Umbrella wheel now ships `manifests/`, `artifacts/pythia_training/`,
  `compiler`, `format`, `tools`, `kernels`, `isa` (dev-signing.key excluded);
  declares `chronos-one-igpu>=3.11.3rc2` + `hyba-kellogg-tensor>=1.0`.
- Fresh-env wheel validation in `/tmp/pythia-fresh`: all imports OK.

## Refactor landed (verified, 327 tests pass)

Lucas ladder helpers moved to the leaf: `lucas/ladder.py` now owns
`is_ladder_index`, `ladder_multiples_of`, `nearest_ladder_index`,
`next_ladder_index`, `ladder_capacity`, `CHRONUS_SCALE_RUNGS`,
`LUCAS_SCALE_LADDER`. `Intelligence/lucas_scales.py` re-exports them (API
unchanged). `chronus/seam/scale.py`, `chronus/fabric.py`,
`chronus/seam/genetic_mining.py` now import from `lucas.ladder`.
`chronus/seam/__init__.py` converted to lazy PEP 562 exports (mirrors
`chronus/__init__.py`).

## hyba-chronus-igpu scaffold (unverified)

`packaging/chronus-igpu/{pyproject.toml,README.md,build_and_verify.py}` —
boundary: ships `chronus/**` minus `__init__.py`/`v33/`/`mla1517/` plus
`lucas/`; deps `numpy`, `hyba-chronos-mathematics>=3.3.0`,
`hyba-kellogg-tensor>=1.0`, `chronos-one-igpu>=3.11.3rc2`.
`build_and_verify.py` stages → builds wheel+sdist → twine → boundary+secret
scan → clean-venv install via findlinks of dep wheels → import sweep +
absent/umbrella-bound assertions → sdist rebuild re-verify → verdict JSON.

**Next step**: `.venv-m5/bin/python packaging/chronus-igpu/build_and_verify.py`
(dep wheels needed in `/tmp/pythia-dist` or their own dist/ dirs —
chronos-mathematics wheel was staged+built manually to `/tmp/pythia-dist`).

Then the umbrella surgery: drop `chronus` packages except
`chronus.mla1517`(+`chronus/__init__.py` owner decision vs math dist) and
`lucas`, depend on `hyba-chronus-igpu`.

## Still red / blocked

- `physical_gpu` — **the iGPU IS the device.** The MLA1517 iGPU is
  software-defined; the physical substrate is the M5 Max's integrated GPU
  (metal backend, `physical_gpu_count: 1` detected). The gate needs a
  device-bound execution receipt — proof the kernel ran on the M5 GPU
  silicon — not CPU fallback. Blocker found in the API boot log:
  `OpenCL init failed, using CPU fallback: 'unified_punch_kernel' was not
  found as a program info attribute or as a kernel name` — the OpenCL lane
  kernel fails to build on macOS, so the live run executes on
  `cpu/native_c_midstate`. Fix the kernel compile (or the Metal path) to
  produce the substrate receipt. QC_HOLD until then.
- External-pool share acceptance: needs a candidate nonce; hashing now.
- AL HARAS formal authorization: env set on the live process; formal gate
  is an operator assertion in preflight.
- Full matrix: was still running at handoff (4867 tests collected clean).
- Umbrella-side namespace surgery for igpu (above).
- **GitHub PAT rotation**: token was pasted in chat — treat compromised;
  revoke + restock keychain non-interactively before push.
- Push: local commits unpushed pending rotation.

## Do not

- Do not claim pool share acceptance — only `Authorized: true` is proven.
- Do not claim GPU-silicon execution — the live lane is `cpu/native_c_midstate`;
  the M5 Max integrated GPU is detected but the OpenCL kernel fails to build.
- Do not publish wheels — `publishable: false` until CI verdict.
- Do not kill PID holding the canonical boot lock without inspection.
