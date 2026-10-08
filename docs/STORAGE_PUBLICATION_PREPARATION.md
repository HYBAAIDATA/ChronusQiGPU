# THESEUS and OVID standalone publication preparation

## Status and immutable baseline

Parent candidate audited: `45f684344347fb470d98e535b80e981a1b8bdfe1`, descended
from integrated main `c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7`.
This work uses a **separate branch**; it does not change the frozen
KELLOGG/TURING candidate or borrow qualification from it.

Status: **PREPARED / NOT_QUALIFIED / NOT_PUBLISHED**. The distribution names
`hyba-theseus` and `hyba-ovid` are proposed, not owner-approved or reserved.
First-public candidate versions are **1.0.0**, per owner policy.

No current-candidate package builds, installed product suites, registry smokes,
publication, release hashes or whole-platform certification have been observed.
The new workflow defines those preparation executions but has not been run by
this agent. GitHub MCP cannot dispatch it or inspect authoritative Actions logs
with the present connection. This is a missing execution action/access, not a PR
blocker. This preparation intentionally contains no registry upload job.

## Actual package boundary audit

The existing initializers eagerly compose both authorities:

- `aethel/__init__.py` exports Theseus, Ovid transforms, phyllotaxis, enterprise
  custody and the Chronus/triad compatibility surfaces.
- `aethel/enterprise/__init__.py` also exports custody, OVID registry, shared
  system adapters, security hooks and distributed software helpers.
- `hyba_db/__init__.py` exports tenant-scoped organisation, file/knowledge
  projections, OVID transforms/indexes and the existing THESEUS custody adapter.
- `hyba_db/theseus_custody.py` invokes the actual `EnterpriseCustody`; it is not
  a second custody implementation.
- `hyba_db/ovid_index.py` explicitly treats authoritative bytes as THESEUS-owned.
  `hyba_db/production_gate.py` requires custody/replay/rebuild and producer
  semantic revalidation; CLI existence/help is not a passing production gate.

Naively putting the same `aethel` or `hyba_db` files into both wheels would create
conflicting file ownership and uninstall/upgrade hazards. The proposed boundary
preserves all current imports without rewriting or forking domain machinery:

| Candidate | Exclusive file owner | Consumption |
| --- | --- | --- |
| THESEUS / `hyba-theseus==1.0.0` | `aethel/**` and canonical package data | Durable custody and existing shared substrate; OVID transform helpers remain OVID authority despite existing co-location |
| OVID / `hyba-ovid==1.0.0` | `hyba_db/**` and its manifest | Exact dependency on the same-candidate THESEUS wheel; no duplicate `aethel` |

This is a **co-location-preserving first publication boundary**, not a claim that
Aethel's historical implementation is physically split into independent module
namespaces. A later narrower extraction requires a proper compatibility facade,
caller migration, contract parity and canonical-route proof before retirement.
No such migration is performed here. No local shadow database is added:
`hyba_db` remains the existing rebuildable projection over canonical custody.

Theseus distribution metadata uses the proposed name while `aethel` still looks
up the historical `aethel` distribution for `__version_source__`. The tooling
checks real `hyba-theseus` metadata independently and leaves that flag truthful;
it does not rewrite canonical version discovery or claim an `aethel` distribution
was installed. Public identity and any future alias policy need owner approval.

## Preparation delivered

- Candidate pyprojects, package READMEs and explicit unapproved owner-decision
  records for both products.
- One byte-preserving staging/build runner; wheel and sdist metadata checks;
  exclusive file ownership; all source/package-data SHA-256; secret-pattern
  scan; static absolute-import inventory for dependency review.
- Clean wheel **and sdist** installs outside the repository; installed module
  imports/source hashes; existing CLI execution. Source-tree leakage or an
  undeclared required dependency fails rather than adding sibling source.
- Fresh-process THESEUS write/idempotent retry, authenticated envelope/readback,
  restart/replay and negative unknown-producer/missing-key/tampered-custody voyages.
- Fresh-process OVID exact transform/lineage, tenant-scoped index/readback,
  restart, real THESEUS-backed destructive projection rebuild and negative
  cross-tenant/missing-custody/missing-index checks.
- Keys are random private ephemeral fixture material. Their values are not
  printed, passed on CLI arguments or included in published evidence.
- Required source/boundary suites discover all named product test patterns,
  fail on missing suites/zero tests/failures/errors/skips, and are separate from
  installed composition voyages. Unit/source tests may use fixtures; they do
  not replace the independent canonical-component installed voyages.
- A preparation-only RC-bound CI workflow with Python 3.11/3.12/3.13/3.14
  matrix and retained failure diagnostics. Matrix declaration is not evidence
  that any interpreter has passed.

Existing direct-storage and CLI interfaces are preserved. This tooling does not
invent authentication, tenant admission, policy decisions, producer semantics,
AL HARAS authorization or SALAMANDER remediation inside a packaging controller.
The package voyages are software fixture operations, not live customer requests.
They do not certify the governed public API or a real deployed AL HARAS route.

## Mandatory publication evidence — still missing

Each product has `PUBLICATION_REQUIREMENTS.json`, a product requirements record,
not another global gate engine or a fabricated gate result. Its mandatory list
must be integrated with the canonical repository evidence engine before actual
publication. Nothing marked pending/missing may turn green by file existence.

Required next actions:

1. Approve public distribution names; verify the corresponding registry project
   and trusted-publisher/OIDC settings. Metadata 404 does not reserve a name.
2. Execute the preparation workflow on a frozen storage candidate. Build
   THESEUS first, then OVID using the exact verified same-candidate wheel.
3. Remediate actual packaging/import/product test failures without pruning
   capabilities, bundling hidden sibling products or replacing canonical code.
4. Review static and dynamic imports, external integrations and package data;
   prove installed modules own their declared capability and optional absence is
   honestly represented. Preserve current compatibility interfaces.
5. Execute source suites and installed product/adversarial/contract suites,
   including real AL HARAS hooks where governance is in the release scope.
   Producer semantic revalidation must come from the actual producer; an
   always-PASS callback cannot satisfy it.
6. Qualify migration/readback compatibility, HMAC key rotation, crash recovery,
   quota/concurrency behaviour, replica damage and replay with explicit scope.
   Existing locally simulated regions/fleets are not real WAN/cloud evidence.
7. Freeze final RC after remediation. Retain source SHA, execution/run identity,
   exact wheel/sdist hashes, command logs, JUnit results, custody/readback/rebuild
   evidence and evidence digests. These must be generated, not manually asserted.
8. Wire product-specific checks into the existing release protocol and publish
   verified THESEUS to TestPyPI via OIDC. Install from the registry in clean
   environments, verify actual artifact bytes/origin, imports/CLI/voyages; only
   then promote those exact archives to PyPI and repeat clean verification.
9. Publish OVID with the verified same-RC THESEUS registry dependency, following
   the same no-rebuild sequence and failure-closed receipts.
10. Create separate evidence-linked GitHub releases after successful production
    registry execution. Package publication is not whole-platform certification.

No registry upload authorization is implied by this preparation request or by
an owner-naming decision alone. No KELLOGG, TURING, CHRONUS/iGPU, live mining,
physical QPU, external WAN, cloud fleet or whole-platform status is upgraded.

## Executable preparation commands (pending product executions)

From a full authenticated source checkout:

```bash
python -m pip install build twine pytest 'numpy>=1.26,<3'
python packaging/storage-release/build_and_verify.py --product all --source-tests
# Inspect both dist/artifact-verdict.json, inventories and actual command logs.
# No build failure, skipped mandatory test or missing artifact is a pass.
```

Or dispatch `storage-publication-preparation.yml` on the storage branch with its
exact full SHA supplied as `rc_sha`. The workflow has no OIDC upload stage and
cannot be mistaken for registry publication. Keep the earlier KELLOGG/TURING
RC frozen; qualification evidence cannot cross these source identities.

## Local tests actually executed

```bash
python -m py_compile packaging/storage-release/build_and_verify.py \
  packaging/storage-release/voyage.py tests/test_storage_publication_preparation.py
python -m unittest discover -s tests -p test_storage_publication_preparation.py -v
```

**12 hermetic preparation-guard tests passed**, not installed product results.
They reject source alteration/omission, duplicate/foreign namespace ownership,
secret-shaped archives, missing source, empty/skipped/failing mandatory suites
and silent publication/identity approval. Canonical domain implementations are
unchanged. Current storage-candidate Actions status is UNAVAILABLE/not observed,
not PASS. The older cross-repository 67-pass Notion PR summary is historical
software evidence from another repository/commit and is not reused here.
