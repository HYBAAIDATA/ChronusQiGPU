**Status: DRAFT CHECKLIST — RC NOT FROZEN. Production/publication HOLD.**

Reference source: `02375987e36a776ac2591aacdf25430349c5338c`. This is the assessment revision, not an approved release candidate. Set `RC_SHA` only after selecting the integrated runtime candidate; record its full immutable SHA. No tag, readiness change, paid workflow, deployment or publication is authorized by this checklist.

## 1. RC admission and source identity

- [ ] Name the candidate, owner and scope. Record `RC_SHA`, integration/base SHA, selected product/package versions and the supervisor approving qualification. Do not infer release approval from permission to test.
- [ ] Use a complete authenticated checkout and detached qualification worktree at that SHA, not the current partial MCP export. Record submodule/LFS status if used; verify expected source, fixtures and dependency files. A clean Git status alone does not establish source completeness.
- [ ] Before generating evidence: record `git rev-parse HEAD`, `git status --porcelain --untracked-files=all` (empty required), tracked-source manifest with SHA-256, Python/Node/npm versions, OS, architecture, installed dependencies and device availability. Keep secrets out of logs.
- [ ] Install declared dependencies in an isolated environment; run `npm ci` from the root with its committed lockfile. Capture exit status/log and confirm dependency setup did not alter tracked source. Missing dependencies are setup blockers, not product passes or justified emulation.
- [ ] Set `PYTHONPATH` to repository root plus `turing_universal_quantum_computer` using the platform path separator. Use unique per-gate basetemps, `-p no:cacheprovider`, full logs and JUnit for pytest commands. Record plugin configuration rather than silently changing test semantics.
- [ ] Store evidence outside the tested source tree where possible: `EVIDENCE_ROOT/<RC_SHA>/<run_id>/`. Preserve initial failures and reruns as separate attempts. No fixed expected test count substitutes for complete collected outcomes.

## 2. Gate command and evidence matrix

Run from the RC repository root. `EVIDENCE_ROOT` and basetemps must resolve to unique actual paths before execution. Record complete argv, environment, start/end times and exit code for each command; do not lose failure status through a shell pipeline.

| Gate | Command / required execution | Evidence and acceptance |
| --- | --- | --- |
| A | `python -m pytest tests/ -q -p no:cacheprovider --basetemp=<EVIDENCE>/tmp/A --junitxml=<EVIDENCE>/A.xml` and `python -m flake8 --count` | `A.log`, `A.xml`, `A_lint.log`; full collection, no new failures, zero lint errors. Reconcile every skip against supported scope and historical baseline; no subset substitution |
| B | `python experiments/toe_enterprise_collapse.py` after successful `npm ci` | `B.log`; versioned `experiments/toe_enterprise_collapse_results.json` plus immutable evidence copy/hash. Exit 0, exactly unique T1–T16, each actual `passed=true`, no skipped/missing/duplicate check. Validate T3/T10/T11 and T16 output freshness |
| C | `python -m pytest tests/test_toe_consensus_boundary.py -q -p no:cacheprovider --basetemp=<EVIDENCE>/tmp/C --junitxml=<EVIDENCE>/C.xml` | `C.log`, `C.xml`; nested consensus vocabulary refusal, tamper-evident token checks, proof-path isolation. See source-path correction below |
| D | `python -m pytest tests/test_toe_runtime.py -q -p no:cacheprovider --basetemp=<EVIDENCE>/tmp/D --junitxml=<EVIDENCE>/D.xml` | `D.log`, `D.xml`; actual decision/outcome/calibration and required tenant-bound receipt fields, bounded updates |
| E | `python -m pytest tests/test_asi_core.py -q -p no:cacheprovider --basetemp=<EVIDENCE>/tmp/E --junitxml=<EVIDENCE>/E.xml` | `E.log`, `E.xml`; observe-only defaults, no unapproved fix/apply/implement or destructive background loop |
| F | Actual domain-specific evaluation suites and signed expert reviews; commands must be selected and versioned for each real pack | `F/<domain>/`: fixtures/dataset identity, negative controls, planted-driver rank-1, drift results, metrics, named reviewer decision. Synthetic technical checks or catalog bindings cannot close F |
| G | `python -m pytest tests/test_toe_ciaas_api.py tests/test_toe_machine.py tests/test_toe_cross_domain.py tests/test_toe_http_closeout.py -q -p no:cacheprovider --basetemp=<EVIDENCE>/tmp/G --junitxml=<EVIDENCE>/G.xml` | `G.log`, `G.xml`; auth/rate/payload/framing/receipts/tenant isolation plus required deployed identity, multiworker, audit-export and endpoint checks. Unit passes alone do not prove deployment obligations |
| H | Finalize existing `docs/PRODUCTION_READINESS_REPORT.md` from this RC's artifacts | Explicit gate/domain true/false and source/run identities; outstanding evidence and approvals stay false. Report generation is not independent acceptance |

Paid CI is unavailable. Full local/self-hosted execution is mandatory, but the original Gate A says CI: label evidence as local/self-hosted and obtain supervisor acceptance of the qualification route. Never relabel it as paid/hosted CI or bypass repository protection.

### Gate F required domains

| Domain | Domain validation in acceptance document | Human boundary |
| --- | --- | --- |
| Islamic finance | Compliance screening; non-halal negative control | Shariah scholar |
| Arabic NLP | Arabic benchmark with the specified comparison protocol; non-Arabic handling | Linguist |
| Cybersecurity | SIEM anomaly evaluation, false-positive rate <5%, declared in-distribution/anomaly negative control | SOC analyst |
| Logistics | Lead-time MAPE <15%, disruption versus normal | Logistics analyst |
| Healthcare | Vitals sensitivity ≥90%, non-clinical input handling | IRB/clinical approval, decision-support-only label |
| Mining | Hashrate prediction/anomaly plus unchanged consensus authority | Mining operator |

All packs additionally need their own causal planted-driver and drift checks. The document's phrase “AraBERT-level” does not define a metric or dataset by itself: fix the benchmark protocol with the reviewer before executing, not after seeing results. None of these domain results is claimed by this checklist.

## 3. TURING and package boundaries

Execute separately with the RC import environment:

```bash
python -c 'from turing_universal_quantum_computer.product_registry import verify_registry; r=verify_registry(); print(r); raise SystemExit(0 if r.get("ok") is True else 1)'
python -m turing_universal_quantum_computer.benchmark --quick
```

Capture `turing_registry.log` and `turing_benchmark.log`. Resolve unexpected import/extra failures. A registry pass checks module coverage, carve-outs and imports—not wheel installation, independent release or rollback. Separately build/install pinned wheels in clean environments without the source root on PYTHONPATH, verify supported dependency versions and caller compatibility, exercise custody/restore and rollback, and record licenses/SBOM, legal/security/operations approvals. TOE A–H do not substitute for the entire portfolio's gates.

## 4. Source-drift and result-publication discipline

- Compare before/after manifests and sample monitored source identity during long runs if mid-run stability is claimed. The existing runner performs per-command before/after checks, not a sampled mid-run monitor.
- Review every changed tracked path. Gate B intentionally rewrites results JSON; copy/hash the original and generated result and version the selected result in a separate evidence commit referencing the tested RC. Do not silently clean dirty JSON or treat generated artifacts as source-code drift, and do not exempt source files to force a stability pass.
- Record the tested RC SHA separately from the later evidence/documentation commit. If any executable source, lockfile, fixture or gate semantics changes, select a new candidate and rerun affected qualification; never transfer passes silently.
- No readiness promotion from the 16 catalog tests, 26-family map, 19-class inventory or 232 raw labels. Sector-agnostic architecture remains separate from domain-specific acceptance.

## 5. Existing local runner — useful, conservative, not sufficient alone

`python scripts/run_toe_production_gates.py --full` exists at the reference source. It captures source/run metadata, commands/log hashes, JUnit, collapse JSON, TURING checks and a generated report under `release-evidence/toe/<run_id>/`. Use `--full` only with a complete checkout; `--scoped` cannot qualify A.

Important source behavior:

- F is explicitly false even when `F_technical` synthetic fixtures pass; exit 1/HOLD can therefore be the correct outcome. Do not edit that false away to claim real-domain qualification.
- Its JUnit helper rejects skips, while the acceptance document cites a historical baseline with 16 skips. Preserve both facts: do not manufacture zero skips, edit tests or downgrade the runner to bypass the disagreement. Record scope and obtain a reviewer disposition; a failing runner remains failing until a reviewed resolution.
- `--full` is an assertion, not complete-source verification. Its sampled manifest does not cover every possible tracked format/path; add full tracked-source identity records as qualification evidence.
- Runtime `production_ready` is configurable and defaults false; the runner does not change it. Report flags are not authorization to set receipts true.

## 6. Gate H skeleton — finalization, not a new claim

```markdown
# TOE RC Qualification Report
RC SHA: <full immutable SHA>
Assessment reference: 02375987e36a776ac2591aacdf25430349c5338c
Evidence commit: <later commit; not the tested runtime SHA>
Run ID / time / platform / Python / Node / dependency-lock hashes: <actual>
Qualification route / supervisor acceptance: <local/self-hosted/CI; actual>
Source completeness / clean initial status / before-after and mid-run records: <artifacts>

| Gate | Passed | Commands/counts | Evidence path + SHA-256 | Owner/disposition |
| --- | --- | --- | --- | --- |
| A–G, one row each | false | PENDING | PENDING | UNASSIGNED |

| Domain | Ready | Eval + metrics | Negative/causal/drift | Human approval |
| --- | --- | --- | --- | --- |
| Each of six required domains, separately | false | PENDING | PENDING | PENDING |

TURING registry / benchmark / installed artifacts: <separate status and evidence>
Remaining portfolio custody/mining/hardware/security/legal/ops blockers: <explicit>
Exceptions and failed attempts: <all dispositions, no concealed reruns>
PRODUCTION READY: false
PUBLICATION APPROVED: false
Supervisor decision / owners / date: PENDING
```

## 7. Source corrections and authority

The acceptance document is historical: its blanket PENDING text, old test counts and “pytest unavailable” statement are not new observations of the current environment. Prior operator results and PR #124's npm ci + 16/16 remain intact at their original source identities. RC reruns qualify a new candidate; they do not erase that history.

The Gate C path printed there (`chronus/mla1517_platform/python/test_toe_consensus_boundary.py`) does not exist at reference `0237598`. The actual seven-test file is `tests/test_toe_consensus_boundary.py`, also used by the existing runner. Revalidate paths on the selected RC before running; missing source is a blocker, not permission to replace a test with a stub.

Sources: [acceptance gates](https://github.com/PhiEnterprise1/EuclidPhiEnterprise/blob/02375987e36a776ac2591aacdf25430349c5338c/docs/TOE_CIAAS_ACCEPTANCE_GATES.md), [local runner](https://github.com/PhiEnterprise1/EuclidPhiEnterprise/blob/02375987e36a776ac2591aacdf25430349c5338c/scripts/run_toe_production_gates.py), [actual Gate C tests](https://github.com/PhiEnterprise1/EuclidPhiEnterprise/blob/02375987e36a776ac2591aacdf25430349c5338c/tests/test_toe_consensus_boundary.py).
