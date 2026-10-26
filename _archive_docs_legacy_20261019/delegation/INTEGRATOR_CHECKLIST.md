# Integrator checklist — build-all / publish-qualified (RC freeze → dispatch)

Working state lives in `/tmp/pythia-dist` (shared findlinks) and each lane's
`artifacts/<lane>/EVIDENCE.md`. Lane branches: `lane/chronus-consolidation`,
`lane/storage-intel-spine`, `lane/platform-matrix`.

## Phase 0 — lane intake (per lane, before merge)

- [ ] `LANE_STATUS: PASS` in evidence packet (BLOCKED lanes do not merge)
- [ ] worktree SHA == expected base `e7e17560` + lane commits only
- [ ] `git diff --stat main..lane/<branch>` touches ONLY the lane's file set
- [ ] every built artifact: wheel + sdist + sha256 recorded, twine PASSED
- [ ] no secrets in diff (`ghp_`, `pypi-`, `PRIVATE KEY`, `PYTHIA_*KEY_HEX=` values)
- [ ] test counts non-zero; failures classified
- [ ] cross-lane pin report collected (Agent 1's sweep)

## Phase 1 — merge

- [ ] merge `lane/chronus-consolidation` first (root pyproject + pins —
      other lanes may pin names it renames; verify no stale references)
- [ ] merge `lane/storage-intel-spine`
- [ ] merge `lane/platform-matrix`
- [ ] resolve any cross-lane pins the CHRONUS rename left behind
      (`chronos-one-igpu` → `hyba-chronos-one-igpu`, version floors → 1.0)
- [ ] `packaging/check_publication_catalog.py` — reconcile catalog vs manifests
      (distribution names/versions changed: chronos-mathematics 1.0.0,
      hyba-chronos-one-igpu 1.0.0, pythia-mining 1.0.0, mining-runtime 1.0.0 —
      catalog fingerprints + version fields may need an authorized update)
- [ ] `git status` clean; commit merge; record MERGE_SHA

## Phase 2 — co-installation proof on MERGE_SHA (the release-critical gate)

- [ ] fresh venv, install ALL wheels from /tmp/pythia-dist + lane dist dirs
- [ ] `record_collision_scan.py` → 0 collisions across all dists
- [ ] `pip check` clean
- [ ] `python -I` import sweep from outside checkout: per-module owner-wheel map
      (chronus→maths facade, chronus.v33→maths, chronus.*→igpu,
       chronus.mla1517→pythia-mining, lucas→igpu, aethel→theseus,
       hyba_db→ovid, toe, euclid, kellogg, turing, salamander+al_haras, mla1517)
- [ ] umbrella-bound modules fail closed (ModuleNotFoundError, no fake success)

## Phase 3 — gates on MERGE_SHA (final, replaces baseline runs)

- [ ] `scripts/m5_transfer_preflight.py --execute`
- [ ] `scripts/euclid_v17_integration_gate.py`
- [ ] `scripts/m3_evidence_pack.py`
- [ ] `scripts/production_preflight.py --profile application --strict`
- [ ] full pytest matrix, junit xml (baseline deltas classified)
- [ ] EXPECTED REDS, documented not fixed: `physical_gpu` (macOS OpenCL kernel),
      external pool acceptance (UNAVAILABLE)

## Phase 4 — RC freeze + dispatch (owner + OIDC path only)

- [ ] tag/branch `release/standalone-qualification-rc` at MERGE_SHA
- [ ] remote auth: ONLY after owner rotates compromised PAT / restocks keychain
- [ ] push RC ref; `gh workflow run kellogg-tensor.yml -f rc_sha=$RC -f publish=pypi`
- [ ] on executed TestPyPI+PyPI receipts: `gh workflow run turing-release.yml
      -f rc_sha=$RC -f publish=pypi -f kellogg_release_run_id=$RUN_ID`
- [ ] same-artifact promotion rule: never rebuild between TestPyPI verify and
      PyPI upload; registry existence ≠ verification
- [ ] remaining distributions publish via their own tracks only after their
      gates execute on RC SHA — never inherited

## Standing prohibitions (all phases)

- publishable stays false in every verdict until an executed CI verdict binds
  the exact artifact sha256
- no GPU/pool/QPU claims; CPU labelled CPU
- no `--profile live`, no live-submit env gates, no pool credentials
- no force-push, no version scheme changes post-freeze without owner sign-off
