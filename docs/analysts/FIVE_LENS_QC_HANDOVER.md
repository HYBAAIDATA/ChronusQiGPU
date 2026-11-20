# Five-lens QC handover — findings first
**HOLD / NOT QUALIFIED.** [Findings register](../../evidence/five_lens/findings.json) is the canonical front door. Executor evidence, not independent acceptance. Reviewed baseline `9d16926c64f7df222e18937e2c30d4767c2799de`, main `93d6068f2c668f3f1106a9e6df204f37033fc163`. No finding states or acceptance criteria changed.

| Finding | State | Mechanical gate consequence | Owner |
|---|---|---|---|
| MV-INPUTS | OPEN | REFUSES closure | customer finance |
| MV-OPTION-D | OPEN | REFUSES closure | customer finance / OVID |
| CLAIM-PURGE | OPEN | REFUSES closure | Chronus |
| TEI-CONSENT | OPEN | REFUSES closure | CEO |
| ANALYST-PACKAGE | OPEN | REFUSES closure | Chronus |
| OPERATING-ROSTER | OPEN | REFUSES closure | CEO |
| PARADIGM-QC | OPEN | REFUSES closure | independent QC |
| FOLDED-RESIDENCY | CLOSED | Evidence validated; QC pending | Chronus |

## 1. Structural refusal and retained provenance
[Hosted CI run 44597165030](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/44597165030), job 135818469797, exact source `9d16926c64f7df222e18937e2c30d4767c2799de`: 16 focused tests passed; campaign executed; closure step returned exit 1. [Retained verdict](../../evidence/five_lens/runs/9d16926c64f7df222e18937e2c30d4767c2799de/closure.json): all_lenses_closed=false, findings_and_qc.pass=false, seven open findings; operating model also refused (named roles missing). Six other validators passed, including artifact integrity. Original verdict content digest `af5e12c3f55aaf981bf340fa97744b879dff23c1bab4441281d78b396fb2d374`. [Artifact 14565069338](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/44597165030/artifacts/14565069338), ZIP SHA-256 `c8b3eaab9bc7c0a72858fcc935048aa62ccbdaecbf2de2357eb66284a335fbe6`.
The workflow calls scripts/ci/check_five_lens_closure.py directly, without continue-on-error. findings() reads findings.json, validates required IDs, checks evidence digests and referencing-commit ancestry, refuses any OPEN entry and requires QC ACCEPTED. A recorded QC field does not authenticate a non-author identity. Do not change it as executor. Independent QC must record identity, reviewed SHA, replay and acceptance. No named independent acceptance available for #202. #201 itself remains OPEN for owner ratification and non-author QC (#205, unassigned when inspected); no ratified wire spec claimed.

## 2. Analytics — explanation, not promotion
Original inputs [traces.json](../../evidence/residency/inputs/traces.json), SHA-256 `ae47d1649bd2b087f4057efcd68b16b5aa3d1e2357c229f7ebde2f8e61cf9060`; [campaign script](../../scripts/benchmarks/fold_residency_campaign.py), SHA-256 `7b96eb8adc70da95ea6dad0b3271058bd1783b471d74c30bb5216f638aeea667`; [original runner output](../../evidence/residency/0f94d2d6ae917eb819943dda6cb7d58baa99a08c/campaign.json), SHA-256 `95da6c4d659c8795765ac14512840423bfa6559824777b5835c6e72ae2d396c9`. Runner output recovered from hosted log and independently hash-checked against runner digest; original bytes retained, not substituted. Source `0f94d2d6ae917eb819943dda6cb7d58baa99a08c`.

| Trace | Folded ops | Boundary ops | Ingress | Egress | Total materializations |
|---|---:|---:|---:|---:|---:|
| Event log | 7 | 1 | 4 | 2 | 6 |
| Object store | 6 | 1 | 4 | 2 | 6 |
| Analytics | 1 | 5 | 12 | 6 | 18 |

Analytics: sort, threshold, top-k, magnitude join, sort are boundary; equality is folded-native. 1/6 counts executed operations by classification, NOT elapsed residency or bytes. Five boundary egresses plus final output each materialize once; 2 initial encodings plus 2 per boundary = 12 ingress, total 18. Identity and candidate counters agree. No counter error identified. The low fraction follows from the prescribed operation mix; ordering holds for those mixes only, not independent evidence about enterprise workloads.

The original data witness is degenerate: [11,22,33,44] all below threshold 128, giving [0,0,0,0]; top-k gives [0,0]; join against [22,33,7,8] yields []; final equality is trivially true. A post-campaign diagnostic separately uses [11,128,200,250] and [200,250,7,8], expecting [200,200,250,250] and false equality, and checks the original and nonempty cases at stages 0 and 7 against independent plain integer arithmetic and exact counter totals. It is not a replacement for the preregistered trace. Execution of the added tests requires revised-head CI. Synthetic operation traces only: measured, not benchmarked; no acceleration or customer claim.

Replay from clean checkout with project test dependencies installed:
```sh
python -m pytest -q -o addopts= tests/test_fold_residency_campaign.py
python scripts/benchmarks/fold_residency_campaign.py --output-dir /tmp/five-lens-replay
python scripts/ci/check_five_lens_closure.py
```
Check out the original source for byte-identical historical campaign replay; at current head compare classes (source_commit changes). Independent QC must rerun, not merely rehash.

## 3. Claim catalogue — incomplete (1 open reconciliation finding)
Six of six defined held entries archived; 0 remain active; all 6 remain publication-blocked. Each held entry now has a specific why_held reason. Original archive bytes remain in Git at the reviewed baseline. CLAIM-PURGE remains OPEN: this count covers the six-entry register, not every historical assertion throughout the repository. The inspected run passed two archive tests; independent full-catalogue reconciliation remains outstanding. No claim admitted.

## 4. Defect and bounded software checks
[Failed run 44595256611](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/44595256611), job 135811700960, source d458f7ee94a6f7c65b4362463a4213294b135b66: tests and campaign succeeded; the gate crashed on ModuleNotFoundError: No module named 'scripts'. Direct script execution initially put scripts/ci rather than the repo root on sys.path; editable install exposed chronus, not the scripts namespace. Fix 0f94d2d inserts ROOT before importing the campaign. The failed run is deliberately retained as failure/remediation provenance; do not erase or relabel it.
[Acceleration run 44597164936](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/44597164936) at reviewed baseline: coverage floor 90% per module with branch coverage enabled; Fourier 16 tests, 100.00%, explicit power-of-two vector length <=4096; state 18 tests, 96.15%, explicit dimension <=256. Bounded software/API validation only; no physical performance claim.

## 5. Blast radius and inherited recovery
Original PR #202: 57 changed-file entries over 10 commits, not one. [Scope inventory](../../evidence/five_lens/reviewer_scope.json) groups every original diff entry:
| Scope | Files |
|---|---:|
| Claim archive/status consumers | 31 |
| Closure and CI | 5 |
| Analyst/memo/metadata | 3 |
| Operating model | 6 |
| TEI | 5 |
| M&V | 3 |
| Residency | 4 |
No unrelated mining, algorithm or product expansion identified in the diff review; legacy decision link migrations include AL HARAS documentation/status strings, not its recovery engine or governance logic. Not a full independent source audit.
PR #201 implementation a83f5f0b892e1bac9e818bcc4b525b12f502d113 is an actual ancestor via second parent of 70a5c97a7db2c4b01eb4bc84735d42ed55e21e87. All 11 recovery-change paths from f7fa3002c272c80d9055443fed652e3bb2dccc79 to a83f5f0 have identical Git blob IDs at reviewed #202 head; zero overlap with its 57-file delta. Not a re-paste. #201 has advanced to a3f78151581c8434e752c95d211eecf74884216e; latest ratification evidence is not inferred inherited. Reconcile dependency before final independent review. No merger or change of release controls.

## 6. Positioning — behind findings
Attested storage combines exact algebraic recovery, reversible fold-domain execution and governed evidence-first closure under explicit AL HARAS, Chronus, OVID and THESEUS authority boundaries. Individual components have incumbents; the combination is the subject of the differentiation thesis, not a verified exclusivity or superiority claim. Competitive landscape review unavailable; do not publish "no equal". No hardware acceleration or customer advantage asserted.

HOLD stays. Independent QC, named non-author, original brief, exact reviewed revision, trace replay, authority review and unresolved findings precede acceptance. The executor does not grant QC.
