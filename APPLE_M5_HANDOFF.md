# Apple M5 Max — Pickup Note

Date (UTC): 2026-10-07
Checkpoint host: Windows (`andre` desktop)
Repo: https://github.com/QuantumPhiRedux/PhiMiner
Branch: `feat/kellogg-turing-products`
HEAD at handoff: `ec35d51ecaf8f29be1b2ef538c6490436f39cf75`
  (`ec35d51e Merge origin/main into feat/kellogg-turing-products`)
Tracked tree state: CLEAN (`git diff --stat` empty on checkpoint host)
Python on checkpoint host: 3.12.10

## Where we left off

Active task: **Complete Chronus as a production-ready standalone package**
(finish behind the readiness gates — do NOT publish while gates are red).

Authoritative instructions (from prior turn):

1. Create the standalone distribution from a dedicated build root with a
   standard `pyproject.toml`. Ship required Chronus modules, entry points,
   and assets only — not the whole miner. Derive dependencies from actual
   execution paths. Company/copyright holder: **HYBA Software Limited**,
   preserving existing licence terms and third-party notices. Verify
   distribution-name availability before publication.
2. Preserve both execution modes:
   - standalone software iGPU (no physical GPU required);
   - GPU enhancement scaling an existing GPU.
   Keep modes explicit. Missing physical hardware must NOT block standalone
   software readiness; hardware-specific results stay unavailable until
   exercised.
3. Close all six evidence gates by real execution — digest-bound EvidenceRefs
   for: software execution, independent verification, receipt identity,
   custody restart, clean installation, full suite. Bind to tested source
   revision + built artifact. No booleans-as-evidence, no fabrication,
   no weakening the readiness contract.
4. Verify the installed wheel OUTSIDE the checkout (fresh env, no repo paths
   masking missing deps). Real workloads, independent output validation,
   receipt identity, custody restart + readback/replay, failure paths.
   Run readiness against the evidence manifest and keep its actual verdict.
5. Consolidate real duplication only — one canonical Chronus, keep legitimate
   functional subpackages and required public APIs. Folder names alone are
   not duplication; publishing does not require flattening. Reconcile the
   mathematical engine (`chronus/v33`) and virtual runtime
   (`chronus/virtual_igpu`) via their documented contracts.
6. Preserve authority boundaries: Chronus = execution; TURING = VQC;
   THESEUS = durable custody; OVID = transformation/fold-materialise;
   Salamander = bounded recovery/optimisation; AL HARAS = security/governance.
   Follow the canonical Notion manual + standalone/two-mode design.
7. Build + validate wheel and sdist, run relevant suites, commit fixes, keep
   reproducible evidence. Prepare the verified RC without publishing while
   required gates are red.
8. Return: completed package, commit, verification commands + results,
   evidence manifest, final readiness verdict. If blocked, name the exact
   missing dependency or owner action. Otherwise continue without another
   general "shall I proceed?".

## Known repo facts (verified this session)

- `chronus/readiness.py` is the gate authority. Last live run on Windows host:
  5/5 source gates pass, 6/6 evidence gates fail
  (`software_execution`, `independent_verification`, `receipt_identity`,
  `custody_restart`, `clean_install`, `full_suite`) →
  `production_ready:false`, `core_production_ready:false`, exit 2.
- Root `pyproject.toml` = `name="pythia-mla1517"`, `version="0.1.0"` — no
  standalone `chronus` distribution exists yet. Standalone build root +
  `name="chronus"` pyproject still to be created.
- `chronos/` at repo root is a DEPRECATED facade forwarding to
  `chronus.v33` (emits DeprecationWarning). Publish `chronus`, never `chronos`.
- `chronus/spec/` has NO `__init__.py` (data dir, `mla1517_chronus_v1.json`
  only) — `chronus/spec.py` wins the import today. Keep as package-data,
  do not turn into a subpackage without resolving the collision.
- One-Chronus dedupe NOT done: `chronus/v33/` + `chronus/virtual_igpu/`
  still present as version folders. Prior directive: no legacy, dedupe —
  every module is canonical or duplicate; canonical→move, duplicate→delete,
  no file survives without a decision. `spec.py` vs `spec/` collision +
  every `chronus.v33.*` / `chronus.virtual_igpu.*` consumer must be
  enumerated and rewritten. Constraints: no `v33/`/`virtual_igpu/` folders
  remain, no duplicates in two locations, all cross-repo imports resolve,
  `pytest tests/` passes unchanged, `chronus/__init__.py` public API stable.
- Untracked scratch on checkpoint host (NOT committed, NOT pushed):
  `.agents/collide_scan.py`, `consumer_scan.py`, `dedupe_full.txt`,
  `dedupe_inventory.py`, `full_inventory.txt`, `hash_scan.py`,
  `inv_collide.py`, `inv_dupes.py`, `stem_scan.py`, `struct_scan.py`,
  `tree_scan.py`, `vi_import_inventory.txt`, `vi_import_inventory_final.txt`.
  Regenerable analysis output only.

## Resume on the M5 Max

```bash
git clone https://github.com/QuantumPhiRedux/PhiMiner.git
cd PhiMiner
git checkout feat/kellogg-turing-products
git pull --ff-only
git --no-pager log --oneline -5
git --no-pager status --short --untracked-files=all
python3 --version; pip --version
python3 -X utf8 -m chronus.readiness; echo EXIT:$?
```

Then continue the standalone-Chronus RC in this order:
1. Full module inventory + execution-path/dependency audit.
2. Dedicated build root + standalone `pyproject.toml`
   (HYBA Software Limited, licence preserved).
3. Two-mode handling (standalone software iGPU vs GPU enhancement).
4. Six evidence gates via real runs → evidence manifest (sha256-bound).
5. Fresh-venv wheel verification outside checkout.
6. One-Chronus dedupe + consumer import migration.
7. Suites + readiness verdict + commit + push. Do not publish while red.

Remote is `origin https://github.com/QuantumPhiRedux/PhiMiner.git`
(fetch + push) — already configured, nothing to `git init` or reset.
