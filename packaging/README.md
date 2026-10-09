# HYBA package publication

Canonical publication convention: **`hyba-<system>-<capability>`**.
The authority/system name remains part of the product identity; a substrate
implementation name is not a replacement (THESEUS owns unchanged `aethel`).

- [Complete catalog, count and release order](HYBA_PUBLICATION_CATALOG.md)
- Machine-readable identities: `publication_catalog.json`
- Check identity/dependency/count drift: `python packaging/check_publication_catalog.py`
- Existing publication workflows: [PUBLISHING.md](PUBLISHING.md)

**11 existing Python distribution candidates; 2 additional planned CHRONUS
splits; 13-package roadmap.** This is not a count of qualified/published packages.
Two EUCLID build definitions name one distribution. Four private JavaScript
applications are excluded. AL HARAS remains bundled with SALAMANDER.

The existing monorepo runtime and authority boundaries remain canonical.
Directory paths, Python imports, CLIs, service routes and existing gate/evidence
schema IDs are retained. No runtime is forked or retired by this naming change.
Old distribution identities are recorded for migration, not advertised as
installable compatibility facades. Registry ownership/history and supported
consumer migration must be verified before publication.

Prior local wheel/test evidence is historical and source-bound. Rebuild and
qualify the renamed artifacts on a frozen current RC; do not reuse an old wheel,
receipt or registry namespace as evidence for a newly named distribution.

## Chronos / CHRONUS boundaries

- `hyba-chronos-mathematics`: existing `chronus/v33` mathematics-only scaffold;
  excludes ONE iGPU, delivery and mining runtime.
- `hyba-chronos-one-igpu`: existing resident standalone product; not certified
  by scoped installed-package checks or modeled M5 descriptors.
- `hyba-chronus-igpu`, `hyba-chronus-tensor`: planned splits, not yet
  scaffolded. Reconcile module/file ownership and retain one canonical runtime
  before building these; do not duplicate THESEUS-owned `aethel/fold_store.py`.

CHRONUS remains substrate-agnostic. Explicit unavailable routes fail closed;
software execution is never relabeled physical GPU/QPU execution. Its separate
whole-product deployment/composition/closure workstream cannot be borrowed by
TURING standalone qualification.
