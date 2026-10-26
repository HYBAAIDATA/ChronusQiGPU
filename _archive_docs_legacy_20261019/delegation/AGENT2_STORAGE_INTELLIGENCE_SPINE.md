# Devin Agent Lane — Storage + Intelligence spine (Agent 2)

You are one of four agents building/qualifying HYBA distributions for first publication.
Your lane: **THESEUS → OVID → TOE → EUCLID** — a serial internal-dependency chain.
The integrator merges lane branches, freezes the RC, and dispatches release workflows.

## Ground truth (do not re-derive)

- Repo checkout: `/Users/demouser/Desktop/PhiEnterprise` (remote
  `https://github.com/PhiEnterprise/PhiEnterprise.git` — **fetch/push BLOCKED, no
  credentials. The old PAT was pasted in chat and is treated as compromised. NEVER push.**)
- Branch `main` @ `e7e17560bb4983a1c84c3d3a5f9e1da3b238ca16`, clean tree.
- macOS arm64, CLT installed. System `python3` is 3.9 — **never use it**.
  Use `~/.local/bin/uv`; CPython 3.12.15 is already installed.
- Shared dep-wheel exchange: **`/tmp/pythia-dist/`** — copy every wheel+sdist you build
  there; check there FIRST before building any in-tree dependency.
  `hyba_kellogg_tensor-1.0.0` is already present (also `packaging/kellogg-tensor/dist/`).
- First read `packaging/HYBA_PUBLICATION_CATALOG.md` (boundaries: THESEUS owns
  `aethel/**`; OVID owns `hyba_db/**` and consumes `hyba-theseus-storage==1.0.0`;
  EUCLID public wheel comes ONLY from `packaging/euclid-engine/pyproject.toml` —
  `euclid/pyproject.toml` is legacy metadata, NOT a second package).

## Setup

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /Users/demouser/Desktop/PhiEnterprise
git worktree add ../PhiEnterprise-spine -b lane/storage-intel-spine
cd ../PhiEnterprise-spine
uv venv --seed --python 3.12 .venv
.venv/bin/python -m pip install -q build wheel twine pytest
mkdir -p /tmp/pythia-dist artifacts/spine-lane
```

## Version scheme (owner-delegated)

Every public distribution's first public version is `1.0.0` — the manifests in your
lane already declare it; do not change them. If any manifest disagrees, report it,
do not invent a scheme. Keep internal pins as declared
(`hyba-theseus-storage==1.0.0`, `hyba-kellogg-tensor>=1.0,<2`, `hyba-toe-intelligence>=1.0,<2`).

## Tasks (serial — each consumes the previous lane artifact from /tmp/pythia-dist)

### T1. THESEUS — `hyba-theseus-storage==1.0.0`
- Read `packaging/theseus/{pyproject.toml,PUBLICATION_REQUIREMENTS.json,OWNER_DECISIONS.json}`.
- Determine the staging story (it ships `aethel/**` — inspect how `packages.find`/
  `package-dir` reach it; if the manifest assumes a staged root, create the staging
  dir the same way `packaging/chronos-core/build_and_verify.py` does).
- Build wheel+sdist; `twine check`; boundary scan (only `aethel/` + dist-info);
  secret scan (grep `ghp_`, `pypi-`, `PRIVATE KEY`, repo-abs paths).
- Clean venv: install from `--find-links /tmp/pythia-dist`, `python -I` import sweep
  of the aethel surface; `pip check`.
- Copy artifacts to `packaging/theseus/dist/` and `/tmp/pythia-dist/`.

### T2. OVID — `hyba-ovid-data-organisation==1.0.0`
- Same protocol; consumes the THESEUS wheel from `/tmp/pythia-dist` (==1.0.0 pin).
- Ships `hyba_db/**` only. Verify installed import + a transform round-trip if the
  package exposes one.

### T3. TOE — `hyba-toe-intelligence==1.0.0`
- `packaging/toe/build_and_verify.py` exists — run it; require `VERIFIED`
  (version is `dynamic = toe.__version__`; confirm it resolves to 1.0.0).
- Copy `packaging/toe/dist/*` to `/tmp/pythia-dist/`.

### T4. EUCLID — `hyba-euclid-intelligence==1.0.0`
- `packaging/euclid-engine/build_and_verify.py` — run it with deps resolved from
  `/tmp/pythia-dist` (kellogg, toe, theseus all present by now).
- Ships `euclid`, `hyba_substrate`, `resonance_intelligence` namespaces.
- Confirm the `euclid-v17-research` CLI entry point works from the installed wheel.
- Copy artifacts to `/tmp/pythia-dist/`.

### T5. Co-installation + RECORD collision proof
Clean venv: install ALL four lane wheels + kellogg from `/tmp/pythia-dist`;
`pip check`; per-module owner-wheel map; zero shared RECORD paths.

### T6. Product tests (in your worktree)
Discover and run tests covering `aethel`, `hyba_db`, `toe`, `euclid`:
```bash
.venv/bin/python -m pytest -q --junitxml=artifacts/spine-lane/tests.xml \
  tests/ -k "aethel or hyba_db or toe or euclid or zeckendorf or cassini"
```
(adjust selection to what actually collects; zero collection = failure).
Also run `packaging/salamander` nothing — that's another lane. Stay in scope.

## Hard rules
- Commit ONLY on `lane/storage-intel-spine` in YOUR worktree. Conventional commits.
  Never touch the shared checkout, `main`, other lanes' files, or `euclid/pyproject.toml`
  (legacy — report, don't publish/edit unless trivially wrong; canonical is
  `packaging/euclid-engine/`).
- `publishable` stays `false`; no twine upload, no push, no GitHub release.
- No claims of GPU/QPU/pool evidence; CPU labelled CPU.
- No secrets anywhere. Wheels get boundary+secret+abs-path scans.
- THE OVID↔THESEUS ordering is strict: never substitute a source import for the
  installed THESEUS wheel to make OVID pass.
- If a gate fails: fix the real defect in your lane or report `BLOCKED` with evidence.
  Never weaken/skip/fabricate.

## Deliverable (return to integrator)
`artifacts/spine-lane/EVIDENCE.md` + JSON containing:
- worktree SHA + lane branch + commits; `git status` clean/dirty
- per distribution: name, version, wheel+sdist paths, sha256, verdict JSON paths
- co-install proof: pip check output, owner-wheel map, RECORD collisions (must be 0)
- test counts (collected/passed/failed), failing test names
- any manifest/pin anomalies found
- explicit `LANE_STATUS: PASS | BLOCKED(<reason>)`
