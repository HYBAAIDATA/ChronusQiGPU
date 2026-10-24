# Canonical Euclid / Salamander production-factory restart qualification

## Outcome and scope

**Local restart repairs PASS; full enterprise qualification PARTIAL; production HOLD.**

Continuation on `feat/euclid-salamander-agent-capabilities-20261023`, draft PR #145.
Baseline commit: `337c979c878e1077f7f97dfbb9eb769e5b29ef5d`.
The companion manifest binds the repaired candidate by file hashes.
This does not merge, publish, deploy, run live actuation, or certify AGI.

Unlike the earlier constructor-only lifecycle tests, these tests call the actual
`EuclidRuntime.production()` factory with real PYTHIA memory/learning/store,
SQLite memory database, repository intelligence, TOE cognition adapters,
primitive-search engines, and the canonical Salamander control plane. No package
initializer bypasses or substitute modules are used. This is an MCP-retrieved
source dependency closure on Linux/Python 3.13, **not** a complete installed
enterprise product. Optional TURING, CHRONUS and Triad owners are unavailable in
this closure and remain reported unavailable, not mocked into success.
An absent `Intelligence/skills` directory produces a warning during the local
synthetic cognitive episode; no unavailable skill is counted as qualified.

## Reproduced baseline defects

`runtime-restart-before.txt` retains the actual pre-fix reproduction:

- One real diagnostic record existed before save; the restored Salamander ledger
  contained zero records. Saved Euclid mirror records were not reconstructed.
- `restored.cognition.evidence is restored.evidence` was false. Subsequent
  cognitive transitions could enter a detached chain that checkpoints omit.
- Both primitive-search engines used the working-directory-relative default
  `var/euclid/registry/primitive_repository.json`, rather than runtime-local state.

Code inspection and failure injection also demonstrated unclosed SQLite startup
resources and owned PYTHIA exit writers after composition failure. Expanding the
source closure exposed the older recomposition test's dependency on owners being
unavailable: repeated composition hit duplicate organ registration. More
importantly, allowing successful recomposition would discard replay history and
permit tenant rebinding. The public operation now refuses a second composition.

## Repairs

1. Validate checkpoint seal, Euclid evidence, worlds/replay, rights scope and
   Salamander mirror links before starting a new runtime.
2. Rebind the actual cognitive engine and learning service to the restored
   evidence chain, alongside Kairos, rights and the delegator.
3. Add `EvidenceLedger.from_records`: defensive-copy and independently verify
   the exact durable host mirror, without re-emitting old records to its sink.
   Rebuild the control plane through its canonical constructor. This restores
   its existing recovery-budget, idempotency/in-doubt and circuit replay logic.
   Rebind the discovery bridge to that same plane. No credentials, stale health,
   transient capacity or unimplemented policy replay are invented.
4. Add optional tenant routing context to `production`, checkpoints, `restore`
   and `restore_from_custody`. A supplied expected tenant must match before
   startup. Legacy checkpoints without tenant context still restore unbound;
   they cannot satisfy a newly asserted expected tenant without an explicit,
   owner-reviewed migration. The optional field is included in the existing
   schema-v1 seal; **older readers will reject tenant-bearing new checkpoints**.
5. Create one runtime-local primitive repository shared by MCTS and evolutionary
   search. Do not import/migrate a working-directory registry silently.
6. Refuse live `compose_organism` repetition before mutating tenant or registry.
   Callers that previously used recomposition must create a separate runtime.
7. Close SQLite and unregister newly owned store exit callbacks on failed
   startup/restore, without saving partially restored state. Normal close also
   unregisters its owned exit writer and remains idempotent. Caller-owned stores
   are not unregistered as though owned by this runtime.

Tenant strings and hash seals are **not authentication**. Production service
identity and authentic checkpoint provenance remain operator/custody boundaries.
The new mirror API checks integrity, not origin. Real AL HARAS and token-provider
configuration must be reattached out of band. Restore without them remains
closed to actuation; a fresh action is explicitly refused in the tests.

## Qualification results

| Command / check | Result |
|---|---|
| `python scripts/qualify_agent_capabilities.py` | **135 tests passed**, zero failures/skips |
| Of those, new production/mirror tests | **15 passed**, included above, not additive |
| Existing autonomic/authority/evidence pytest modules | **67 passed + 26 subtests**, zero failures/skips |
| Scoped sdist → wheel → clean-venv installed feature check | **PASS**, including installed `from_records` continuation |
| Actual cognitive episode after runtime restore, then save/restore again | PASS, cognitive transition evidence retained |
| Fresh Python-process restore of real diagnostic history | PASS, chain continues, authority remains closed |
| Corrupt mirror / wrong tenant rejected before factory starts | PASS |
| Injected startup and semantic-replay failure cleanup | PASS, actual SQLite connections verified closed |

The new replay test seeds explicitly labelled synthetic recovery-budget,
uncertain-action and circuit records, then verifies canonical replay/refusal.
That is **fault-injection/replay evidence, not actual recovery or actuator proof**.
The positive diagnostic and cognitive episode records are actual component output.
The independent SymPy matrix cases remain part of the earlier contract suite;
this work does not count them again as new discoveries or independent tests.

Earlier local failures are not hidden: initial package/regression commands found
missing `build` / `pytest` tooling; installing those test dependencies resolved
that environment issue. The first expanded run had 95 tests (the local snapshot
was missing the 40 already committed revision-2 tests), and its old recomposition
test failed with `duplicate organ`. Exact revision-2 sources/tests were retrieved
from the pinned commit; the recomposition contract was changed deliberately to
refuse resets. Final logs and hashes describe the successful **135-test** candidate.

## Evidence and remaining production gates

- `runtime-restart-tests.txt`: final complete focused run.
- `runtime-restart-regressions.txt`: existing security/replay regression run.
- `runtime-restart-before.txt`: pre-fix reproduction.
- `runtime-restart-package.json`: scoped clean-install verdict and artifact hashes.
- `runtime-restart-manifest.json`: candidate and retrieved dependency source hashes.

The installed check is for the standalone Salamander diagnostic surface only;
it does not install or qualify the complete Euclid production factory. The
source-level fresh-process restore is not canonical THESEUS enterprise custody
qualification. The custody forwarding signature is changed but no new custody
end-to-end result is claimed here.

Still required: full authoritative hosted CI across supported platforms,
complete product installation/startup with actual owner implementations,
authenticated service/tenant deployment, canonical custody and crash/restart
qualification, actual authorized recovery with independent owner verification,
operational acceptance, and independent security review. Whole-runtime concurrent
world/rights/checkpoint consistency and crash-durable exactly-once behavior are
not established by these tests. The primitive repository's existing default HMAC
key is not made into a production secret by moving its path. Package license
metadata still requires the owner's BSD/MIT resolution; no relicensing occurred.

**Release recommendation: review this candidate; do not promote to production.**
