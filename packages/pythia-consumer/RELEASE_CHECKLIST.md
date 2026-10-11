# PYTHIA Consumer — Release Checklist (v0.1.0)

Every claim below is anchored to verifiable evidence. Nothing here is a
marketing assertion — each row names the artifact or command that proves it.

## Compatibility

| Requirement | Value | Evidence |
|---|---|---|
| Python | ≥3.10 (built/tested on 3.12) | `pyproject.toml`, `pytest` 86/86 on cpython-3.12 |
| macOS | 13+; **arm64 only** today | `build_app.py` runtime `cpython-3.12-macos-aarch64`; universal2 untested |
| iPhone | companion PWA via `pythia console --lan` → `/companion`; Add-to-Home-Screen install | `companion/` assets, route tests, live serve on M5 Max |
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
| "Receipts you can check" — structural + canonical binding | ✅ supported | `verify.py`, 86 tests, `demo_verify.py` |
| "…and make" — local receipt minting closes the loop | ✅ supported | `mint.py`, `/api/mint`, companion Mint card; minted receipts pass `verify` (JS mint parity tested: identical canonical_int/token/masks) |
| Honest offer catalog | ✅ supported | `offers.py` → `pythia offers`, `/api/offers`; states: `installed`/`this-device`/`served`/`absent`/`not-productized` |
| "…on your iPhone" — JS verifier parity with the Python contract | ✅ supported | `companion/verify.js`, JXA parity test (8 case classes incl. >2^53 canonical, non-ASCII context) |
| Local-first, offline verification | ✅ supported | stdlib server on 127.0.0.1, no network calls; client-side JS needs none |
| Device-aware offer tier (MacBook/iMac/Mac Studio memory) | ✅ supported | `census.device_block` — model family + unified GiB → `offer_tier` |
| Bundled iGPU/OVID/THESEUS availability | ✅ supported | `pythia products` — `available/bundled` |
| iPhone offline (service-worker) caching | ⚠️ platform-limited | iOS requires secure origin; plain-LAN http loads + verifies but does not cache |
| Provenance/authenticity of receipts | ❌ unsupported | `levels.provenance_authentication == "unsupported"` |
| Mining, hashrate, GPU throughput | ❌ no claim | `mining_performed: false` in census |
| Quantum computation | ❌ never claimed | positioning doc — "exact mathematics" only |

## Data integrity & privacy

- Verifier is structural + canonical-binding; tampered bound fields are rejected (test-covered).
- Console binds 127.0.0.1 by default; `--lan` is opt-in and exposes only read-only census + stateless verify (no auth, no mutation surface).
- POST body capped 1 MiB; `json.loads` only — no eval. Companion assets are static files with path-traversal rejection.
- Census is read-only probing (sysctl/system_profiler with timeouts); **serial number and UUID are never collected**. App writes nothing outside its bundle; companion wallet is localStorage-only on the iPhone.
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
| iPhone App Store | ❌ not required — companion is a PWA; verification is client-side so no App Store review exposure |

## Publication lane

`.github/workflows/consumer-publication.yml` mirrors the storage lane:
guards → bundled build + digests → installed-wheel smoke matrix (3.10–3.13) →
catalog/PyPI-state verdict → reviewer-gated OIDC TestPyPI → TestPyPI smoke →
same-bytes PyPI promotion → PyPI smoke → evidence-linked GitHub release.
Upload authorization lives only in the `testpypi`/`pypi` environments;
trusted-publisher configuration and the `hyba-pythia-consumer` PyPI namespace
remain owner-controlled.

## Known limitations carried into release

- `packaging/publication_catalog.json` checker: previously reported post-audit baseline drift; resolved by the 2026-10-11 identity reconciliation (`hyba-chronos-one-igpu` rename + 1.0.0 first-public versions). Catalog now PASSes.
- Unverified fields (`slot_address`, `truth_class`, etc.) remain forgeable — documented, assertion-pinned.
- App is 124 MB (full standalone runtime); slimming is a future increment.
