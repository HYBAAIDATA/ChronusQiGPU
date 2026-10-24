# Custody authority repair and whole-system qualification disposition

**Actual custody checks PASS; whole-system validation BLOCKED; production HOLD.**

Continuation of draft PR #153, based on `668ade9f2a8297d5f27ac10e016c128d847c71b9`.
Main reviewed at `cd80d0371e50979cb5d1e704bafd41f70f0044d8`; PR #148 is merged.
The PR #153 runtime/SALAMANDER restart repairs remain untouched. No merge,
deployment, registry upload, permission change or qualification waiver occurred.
The candidate is identified by this PR commit and the companion changed-file
hash manifest, not a fabricated local Git revision.

## Reproduced defects and repairs

- The Triad advertised Ovid-root authority while normal `put/get` used Theseus.
  If a legacy root was bound, `put` wrote two owners with no atomic contract.
  Default composition now names `theseus-custody/v1`: Theseus custody, Ovid
  transformation, optional Chronus execution evidence. It has one custody writer.
- Legacy `ovid-authority/v1` and `theseus-projection/v1` files retain their formats
  and explicit `legacy-ovid-root/v1` profile. They are not silently migrated,
  deleted or labelled enterprise Theseus custody. Ambiguous configurations are
  refused before directories are created; generic legacy `put/get/snapshot`
  refuse rather than operate on the wrong store. Legacy backup is not qualified.
- `open_triad(durable_dir=...)` now passes a real directory to the actual Theseus
  owner. `durable=True` without a directory remains memory-only for compatibility;
  health says so. The EUCLID Triad adapter refuses persistent `put` until a disk
  custody owner is bound. Its verification response identifies actual authority,
  profile, disk binding and integrity separately; it does not claim qualification.
- Theseus publishes its index with file/directory fsync through the existing
  storage primitive. A failed publication latches the live owner uncertain;
  subsequent writes, payload reads, working-form reads and snapshots refuse.
  A fresh attach rejects a missing/stale index, journal/index mismatch, duplicate
  addresses, invalid integer metadata and metadata inconsistent with verified
  bytes. Orphan/non-empty foreign directories are preserved and refused, not
  adopted as a fresh empty store.
- Legacy Ovid reads now compare stored folded blocks and metadata against the
  actual bytes and index. `get_form` retains stored lineage instead of inventing
  a new transform execution. Legacy projection comparison checks full metadata
  and generation against verified source objects, not only object ID membership.

These are integrity checks, not signatures/authentication. No private Triad is
substituted for an already bound enterprise shared fabric. Existing canonical
enterprise `SystemDataPort`/persistent fabric composition is not changed here.

## Compatibility / operations

```python
from aethel.triad import open_triad, LEGACY_OVID_PROFILE
from euclid.organ_adapters.specialists import TriadCustodyOrgan

# Disk custody, actual Theseus implementation; caller chooses the owned directory.
triad = open_triad(durable_dir="/owned/path/theseus", bind_chronus=False)
organ = TriadCustodyOrgan(triad)
# Supply this implementation through the existing runtime composition interface.
# Reuse the existing owner where one is already bound; do not create a second root.

# Explicit legacy access only; never automatic migration or enterprise admission.
legacy = open_triad(storage_profile=LEGACY_OVID_PROFILE,
                    ovid_root="/owned/path/legacy-ovid", bind_chronus=False)
```

Legacy callers supplying `ovid_root` must select that explicit profile. The
historical projection test has been updated accordingly and reads legacy root
health from `owners.legacy_ovid_root`, not transformation health `owners.ovid`.
The complete historical Chronus-containing module was NOT rerun locally.

Theseus index reads now enforce the storage module's existing private-file and
ownership checks. Broad-permission historical index files will refuse admission;
the responsible owner must review/correct file permissions and rerun validation.
No automatic chmod, migration or recovery rewrite is performed. Back up the
entire store before investigating a refused attach. Reconcile index and journal
against independent trusted custody evidence; do not truncate or fabricate index
rows merely to obtain a pass. Automatic orphan recovery, multiprocess concurrent
writers and a power-loss durability guarantee are not established by this patch.

## Fresh execution

Environment: Linux x86_64, CPython 3.13.14. Twenty actual Aethel source modules
were retrieved by GitHub MCP and checked against returned Git blob IDs. Actual
`Triad`, `Theseus`, `AddressSpace`, Ovid transforms, legacy root/projection and
`TriadCustodyOrgan` implementations executed; no storage substitute was used.

This environment still has only a selective source closure, **not** a complete
checkout or installed enterprise distribution. The local test bootstrap bypassed
Aethel/Euclid package initializers explicitly; its exact text is in the manifest.
That limits every result below. The new repository test imports are ordinary
imports; they must also pass without this bootstrap on the full candidate.

| Run | Outcome | Scope |
|---|---|---|
| New custody/profile suite, normal | **35 passed**, no failures/skips | actual listed source components |
| Same suite under `python -O` | **35 passed**, no failures/skips | same 35 cases, not 35 additional cases |
| Inherited PR #148 bridge subset, normal | **39 passed** | existing local PR #148 subset; DiskPort test double, not native custody acceptance |
| Same inherited subset under `python -O` | **39 passed** | same 39 cases, not additional distinct cases |
| Scoped Ruff E9/F63/F7/F82/F401 and AST parse | PASS | seven changed Python files; not full-repository lint |
| Non-custody specialist semantic AST comparison | PASS | TURING/Chronus adapter logic unchanged |
| Existing full closeout runner preflight | **BLOCKED, exit 2** | git rev-parse exit 128: selective source is not a Git checkout |

The optimized pytest run emitted its standard assertion warning. Production
refusal guards added here are explicit runtime checks, not `assert` statements.
The initial local test command failed because pytest was absent; installing test
tooling resolved that environment problem. Early scoped lint found unused imports;
those were corrected before final runs. Neither attempt is hidden as a pass.

The suite includes actual child-process restart and `os._exit(73)` immediately
between durable journal publication and index publication. Restart refuses the
stale index and retains both journal entries. It does not claim automatic repair
or exactly-once completion. Other cases exercise memory-only refusal, profile
conflicts before I/O, real adapter put/get, foreign authority refusal, legacy
lineage retention, stored fold/projection tampering, corrupt blocks, real replica
heal and failed heal, and independent Binet/fast-doubling/Cassini/byte-fold checks.

### Reproduction on a complete, dependency-provisioned checkout

```sh
python -m pytest -q tests/test_triad_authority_profiles.py
python -O -m pytest -q tests/test_triad_authority_profiles.py
python -m pytest -q tests/test_ovid_theseus_chronus_gap_closure.py
python -O -m pytest -q tests/test_ovid_theseus_chronus_gap_closure.py
python scripts/qualify_agent_capabilities.py
```

The last three commands were NOT run on this candidate here. Then run the existing
`run_clean_install.py` entry point with its documented arguments and complete
owner/dependency wheel set; preserve normal/optimized installed outputs and exact
wheel/source provenance. Run the existing closeout runner with a clean checkout,
external evidence/basetemp directories and the actual reviewed claims-gate argv.
Do not invent a claims command, use synthetic wheels as product evidence, or mark
an absent owner as a passing fallback.

## Whole-system evidence matrix — not a blanket pass

| Product / gate | This increment | Required closeout |
|---|---|---|
| Theseus custody | actual local disk put/get/heal/attach/crash refusal PASS | full package imports, installed shared fabric, concurrency/power-loss/reconciliation qualification |
| Ovid transforms | exact byte fold and legacy integrity PASS | other declared numeric/splice/refold/checkpoint transforms and complete installed surface |
| EUCLID | actual Triad adapter PASS; #153 restart evidence retained in its original scope | complete installed production startup, real empirical binding/native dispatch and concurrent checkpoint consistency |
| SALAMANDER enterprise | prior #153 replay/diagnostic evidence retained, not rerun | actual authorized recovery with independent postcondition owner |
| SALAMANDER mining / Chronus | prior scoped mode evidence retained, not rerun | inherited #100–#107 gates; physical execution only for device-specific supported claims; authorized pool only if separately approved |
| TURING VQC | logic preserved; no new full-engine result | canonical installed VQCPipeline and mathematical/consumer suites; a physical QPU is not required for software-only claims |
| Kellogg | NOT_RERUN_THIS_CANDIDATE | exact planes, artifacts and full installed suites |
| TOE | NOT_RERUN_THIS_CANDIDATE | actual reasoning and gates A–H with canonical owners |
| PULVINI | NOT_RERUN_THIS_CANDIDATE | real fold audit envelopes/reconstruction bounds |
| AL HARAS / identity / entitlements | no new external identity proof | real authority provider, tenant/policy binding and approved service integration |
| Hermitten | NOT_RUN | actual receiver/economics contract only where the release schedule requires it |
| Full installed/offline distribution | NOT_RUN | complete source, dependency closure, real wheels, out-of-tree normal/optimized acceptance |
| Compatibility/security/operations/legal | OPEN | supported OS/Python matrix, independent security, actual release/deployment/license owner approvals |

Existing product locks remain pinned to main `cd80d037`; this unmerged draft does
not change their accepted source revision. Earlier local passes remain evidence
for their own candidate and scope, not new whole-system passes.

## CI / access / decision

At parent head `668ade9...`, check-runs access again returned **403 Resource not
accessible by personal access token**. Combined status was `pending`, zero statuses.
This is a token visibility limitation, not a demonstrated CI failure or pass.
Required-check configuration and workflow outcomes remain unverified. Paid CI
remains owner-deferred; no paid run, permission change or protection bypass was
requested. Read access to existing check results or authorized self-hosted
execution can close evidence gaps without relabelling local tests as hosted CI.

The full runner freshly refused the incomplete local tree before tests. To unblock
full software qualification, supply a complete authenticated checkout in an
execution environment or the full pinned source archive with independently
verifiable provenance. An archive does not manufacture Git ancestry for runners
that require a checkout. No repository content MCP tool here provides execution
or a complete checkout export. No token should be pasted into chat.

**Decision: repository repairs are reviewable; whole-system validation is not
complete and production remains HOLD.** No existing waiver text is treated as a
passing acceptance result. Full candidate execution, required service/sandbox
bindings and accountable approvals are still necessary for the user's current
whole-system validation mandate.
