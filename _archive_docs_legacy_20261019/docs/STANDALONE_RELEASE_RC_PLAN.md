# Standalone release qualification — pinned baseline audit and execution plan

## Decision and scope

Standalone KELLOGG/Tensor and TURING/VQC publication is a separate qualification
from whole-platform production readiness; neither may borrow the other's status.
KELLOGG is first; TURING consumes the exact same-RC published KELLOGG archive.
CHRONUS/iGPU, ONE iGPU and SALAMANDER platform composition are outside this
standalone publication increment. No physical QPU, iGPU-qualified VQC, live-pool
mining or whole-platform production certification is asserted.

Audit baseline: `c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7` on `main`.
PRs #135, #142 and #148 were merged. PR state is not qualification and is not an
execution blocker. A new RC must be frozen after these gate repairs. All final
release evidence must identify that exact RC, not the audit baseline or an older
lane commit. Do not commit a self-referential RC SHA into its own source tree:
record the returned commit in the dispatch input, CI evidence and release tag.
Any later source change invalidates the RC and requires a new full qualification.

## Pinned evidence audit

| Product/evidence | Recorded result | Qualification limit at this baseline |
| --- | --- | --- |
| `packaging/kellogg-tensor/release-evidence/tests.json` | 211 passed, zero skipped; SHA `a4df7dc7976a15ab6a6a901cd49aa11715b410e8` | Historical/stale for integrated `c63ff4d...` and the new RC; rerun full product suites |
| `reports/CHRONUS_V33_FULL_VALIDATION.txt` | 48 passed | Explicitly a targeted audit subset, despite filename; not whole-product certification |
| `reports/salamander_local_pytest.log` and `reports/salamander_increment_evidence.json` | 53 passed, 26 subtests; seven mutants killed | Source-subset/local-contract only; production composition UNAVAILABLE |
| `reports/PR140_CLOSURE.json` | Focused installed/restart checks; NOT_CERTIFIED / QC_HOLD | Whole-product and platform evidence missing; retain limitations |
| TURING release workflow | Source, installed, formal and benchmark design exists | Old `testpypi_verified` was package metadata existence, not clean installation/execution; repaired here, not yet executed |
| GitHub releases | None returned by the live review | No GitHub publication evidence observed; creation remains an action |
| Public registry review | Metadata lookups unavailable | Publication not independently confirmed; neither PASS nor proof of absence |
| `packaging/toe/OWNER_DECISIONS.md` | Approved `hyba-toe==1.0.0` | README corrected; registry prerequisites remain open |
| EUCLID 17 notes and package metadata | Research generation 17.0.0 | First-public distribution candidate now 1.0.0, runtime/research identity stays 17.0.0; historical results are not new artifact qualification |

No existing product result above is promoted into release evidence for the new
RC. No current-RC Actions run, package hash, registry install result or platform
certificate was observed during this source repair.

## Gate repairs in this increment

- Both existing package workflows require an explicit full `rc_sha` matching the
  dispatch head, check out that SHA, and retain the existing package gates.
- KELLOGG discovers all `test_kellogg*.py` product tests in addition to the required
  boundary suites; missing files, zero tests, skipped tests, failures and errors
  fail. Old JUnit/latest benchmark outputs are removed before execution; duplicate
  benchmark IDs and stale benchmark commit bindings fail.
- Qualification artifacts must bind to the frozen RC. Registry verification
  validates required qualification flags and refuses missing/false source gates.
- One production dispatch runs TestPyPI OIDC upload -> clean installed Python
  matrix -> sealed execution receipts -> exact archive promotion through PyPI
  OIDC -> clean PyPI Python matrix -> evidence-linked GitHub release. No rebuild
  occurs between the two registry uploads. `publish=none` never uploads.
- `testpypi_verified` is initially false and becomes true only from validated,
  executed TestPyPI receipts. Package JSON existence cannot satisfy it.
- Registry checks run outside the source tree in fresh environments, validate
  wheel download origin/hash and both registry archive digests, execute imports,
  product checks and TURING CLI, and retain install/command/custody/replay records.
- KELLOGG resident custody is explicitly resident, not durable platform custody.
  TURING serializes and independently verifies/replays its computation receipt in
  a fresh process. Scientific/software results are not relabelled physical QPU.
- Receipt validation rejects missing interpreters, duplicates, stale SHA, wrong
  registry/run/product, substituted archives, missing commands, tampered custody
  and malformed/duplicate-key JSON. Cross-interpreter digest qualification belongs
  to the existing workflow matrix, not a lone registry interpreter.
- TURING publication requires a completed same-RC KELLOGG publication run and
  consumes its exact archive rather than rebuilding its prerequisite.

## Execution order — pending, not results

Run from a full authenticated checkout of the frozen RC. A partial file retrieval
cannot substitute for source, installed artifact, platform or registry tests.

1. Freeze the repair commit; verify `git rev-parse HEAD` and clean tracked source.
2. Dispatch KELLOGG with `publish=pypi` to execute both registry stages in one run.
   Its qualification includes the complete product suite, zero skips, full
   benchmarks, installed wheel/sdist and 3.11/3.12/3.13/3.14 fixture matrix.
3. Retain the completed KELLOGG run ID and exact verified archive/evidence bundle.
4. Dispatch TURING with `publish=pypi` on the **same RC**, supplying that KELLOGG run
   ID. Its existing qualified interpreter matrix is 3.11/3.12/3.13; no unexecuted
   interpreter is certified. It also retains source/composition tests, acceptance,
   full benchmark and Lean gates. Registry smoke includes `turing-vqc --help`, a
   two-qubit script, certificate/witness verification and fresh-process replay.
5. Inspect all job executions, receipt statuses and hashes. Zero-step Actions is
   UNAVAILABLE, not PASS or code failure. Crashed/skipped mandatory jobs fail
   qualification. Missing external execution access is a missing action/access,
   not a PR blocker.
6. After successful PyPI installed execution, each workflow creates a separate
   product GitHub release attached to the RC with wheel/sdist, publication JSON
   and full registry execution logs. No release is created on smoke failure.

Example commands (not executed during this source repair):

```bash
RC_SHA="$(git rev-parse HEAD)"
REF=release/standalone-qualification-rc
# Requires authenticated GitHub CLI with Actions execution access.
gh workflow run kellogg-tensor.yml --ref "$REF" -f rc_sha="$RC_SHA" -f publish=pypi
# Obtain actual completed run ID from Actions; never use a placeholder as evidence.
gh run list --workflow kellogg-tensor.yml --branch "$REF" --commit "$RC_SHA"
gh run watch "$KELLOGG_RUN_ID" --exit-status
gh run download "$KELLOGG_RUN_ID" -D release-evidence/kellogg

gh workflow run turing-release.yml --ref "$REF" -f rc_sha="$RC_SHA" \
  -f publish=pypi -f kellogg_release_run_id="$KELLOGG_RUN_ID"
gh run list --workflow turing-release.yml --branch "$REF" --commit "$RC_SHA"
gh run watch "$TURING_RUN_ID" --exit-status
gh run download "$TURING_RUN_ID" -D release-evidence/turing
```

Prefer the single `publish=pypi` run: it publishes to TestPyPI **first**, verifies
it, then promotes the exact archives. `publish=testpypi` is a verification-only
stop before production and is not a production certificate. Version collisions
or interrupted registry uploads need explicit archive-preserving reconciliation;
never rebuild and silently overwrite or treat existence as a passing smoke test.

## Required release custody record

For each product retain: frozen RC SHA; exact CI run URL and executed job/step
statuses; wheel and sdist SHA-256; qualified Python versions; source/full product
suite results; TestPyPI and PyPI install reports and command logs; downloaded wheel
hash and origin; import/CLI/smoke results; serialized custody/replay record and
its digest; execution receipt digest; registry URLs; GitHub release URL.
Missing records mean NOT_QUALIFIED. Artifact/receipt digests detect tampering;
they do not independently establish a physical substrate or platform authority.

## Separate CHRONUS/iGPU track

Choose one explicit deployment target and lock driver/runtime/device identity.
Execute intended-route end-to-end iGPU workloads, independent result verification,
real canonical component composition, restart/readback, fault injection and
provenance checks on that target. Bind all evidence to its source commit and
artifacts; issue closure only after mandatory whole-product gates pass. Until then
retain NOT_CERTIFIED/UNAVAILABLE. SALAMANDER production composition remains
UNAVAILABLE and is not qualified by standalone package publication.

## Access and evidence gaps at handoff

The GitHub MCP used for this audit can read and write source, but exposes no
workflow dispatch or GitHub release creation tool. Earlier check-run access
returned 403, and unauthenticated private-repository git checkout was denied.
A full source/product execution and OIDC publication were therefore not run here.
Required remaining actions: obtain execution access; dispatch on the frozen RC;
resolve any real gate failures; verify OIDC environments and publisher settings;
complete both registry execution matrices; retain archives/logs; create and inspect
the evidence-linked releases. These are not open-PR blockers.

## Local tooling checks executed before freezing the repair

These are hermetic **protocol/fixture tests**, not KELLOGG/TURING product results
or registry/CI qualification. Python 3.13.14 was used in a partial source staging
folder. Executed commands:

```bash
python -m py_compile packaging/verify_registry_release.py \
  packaging/kellogg-tensor/run_release_gate.py \
  packaging/euclid-engine/build_and_verify.py tests/test_registry_release_protocol.py
python -m unittest discover -s tests -p test_registry_release_protocol.py -v
```

Result: **20 protocol tests passed**, zero protocol skips. Both workflow YAML
files parsed; their dependency graphs were acyclic, all checkout refs bound to
RC_SHA, PyPI promotion depended on executed TestPyPI verification, GitHub release
creation depended on executed PyPI verification, every embedded Python block
compiled and every Bash run block passed `bash -n`. None of these checks was a
GitHub Actions run or a product install/smoke/full-suite result. Release artifacts
and registry qualification receipts must still be produced by the frozen-RC
workflows; none was fabricated during this repair.
