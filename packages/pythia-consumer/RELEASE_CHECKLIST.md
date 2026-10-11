# PYTHIA Consumer — Release Checklist (v0.1.0)

Every claim below is anchored to verifiable evidence. Nothing here is a
marketing assertion — each row names the artifact or command that proves it.

## Compatibility

| Requirement | Value | Evidence |
|---|---|---|
| Python | ≥3.10 (built/tested on 3.12) | `pyproject.toml`, `pytest` 63/63 on cpython-3.12 |
| macOS | 13+; **arm64 only** today | `build_app.py` runtime `cpython-3.12-macos-aarch64`; universal2 untested |
| Linux/Windows | wheel is `py3-none-any`; untested, no claim | — |
| Dependencies | numpy ≥2.1,<3 · sympy ≥1.14,<2 (+mpmath transitively); MLX/CoreML optional (`apple` extra, Darwin-arm64 only) | `pyproject.toml`, clean-venv install |

## Install & demo path

| Step | Command | Evidence |
|---|---|---|
| Build | `python build_bundle.py` → `dist/*.whl` + sdist | wheel SHA256 recorded per build |
| Install | `pip install dist/hyba_pythia_consumer-*.whl` | clean-venv install verified |
| Demo | `python demo_verify.py` | genuine receipt pass → tamper → fail, ~60 s |
| Console | `pythia console` → http://127.0.0.1:8777 | served + `/api/status` verified on macOS |
| App | `python build_app.py` → `dist/PYTHIA.app` | standalone runtime, zero host deps |

## Claims the product may make (and may not)

| Claim | Status | Evidence anchor |
|---|---|---|
| "Receipts you can check" — structural + canonical binding | ✅ supported | `verify.py`, 63 tests, `demo_verify.py` |
| Local-first, offline verification | ✅ supported | stdlib server on 127.0.0.1, no network calls |
| Bundled iGPU/OVID/THESEUS availability | ✅ supported | `pythia products` — `available/bundled` |
| Provenance/authenticity of receipts | ❌ unsupported | `levels.provenance_authentication == "unsupported"` |
| Mining, hashrate, GPU throughput | ❌ no claim | `mining_performed: false` in census |
| Quantum computation | ❌ never claimed | positioning doc — "exact mathematics" only |

## Data integrity & privacy

- Verifier is structural + canonical-binding; tampered bound fields are rejected (test-covered).
- Console binds 127.0.0.1 only; POST body capped 1 MiB; `json.loads` only — no eval.
- Census is read-only probing (sysctl/system_profiler with timeouts); app writes nothing outside its bundle.
- Fixture provenance recorded (`tests/fixtures/PROVENANCE.md`, sha256-pinned).

## Apple distribution (direct, NOT Mac App Store)

| Gate | Status |
|---|---|
| Unsigned .app build | ✅ done — `dist/PYTHIA.app` |
| Developer ID signing | ⛔ owner-gated — `codesign --deep --options runtime` |
| Hardened runtime entitlements | ⛔ evaluate at signing; none expected needed for stdlib HTTP + embedded Python |
| Notarization | ⛔ owner-gated — `notarytool`, requires Apple ID + team credentials |
| Gatekeeper/SPKI assessment | ⛔ blocked until signed |
| Clean-machine launch/uninstall | ⚠️ verified only on build host; uninstall = drag-delete by design |
| Mac App Store | ❌ not targeted — bundled runtime + mining-adjacent lineage argue direct distribution |

## Known limitations carried into release

- `packaging/publication_catalog.json` checker: previously reported post-audit baseline drift; resolved by the 2026-10-11 identity reconciliation (`hyba-chronos-one-igpu` rename + 1.0.0 first-public versions). Catalog now PASSes.
- Unverified fields (`slot_address`, `truth_class`, etc.) remain forgeable — documented, assertion-pinned.
- App is 124 MB (full standalone runtime); slimming is a future increment.
