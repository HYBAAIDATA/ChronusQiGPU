# TURING documentation system — review increment

The [audience entry point](turing/index.md), [source inventory](turing/internal/inventory.md),
[portal implementation specification](turing/internal/portal-design.md), and
[qualification mapping](turing/internal/qualification.md) describe this increment.

## Build and check from the repository root

```bash
python -m pip install -r docs/turing/requirements.txt
python scripts/turing_docs.py check
python -m unittest discover -s scripts -p test_turing_docs.py -v
python scripts/turing_docs.py build --audience public --out /tmp/turing-public-review
python scripts/turing_docs.py build --audience customer --out /tmp/turing-customer-review
python scripts/turing_docs.py build --audience internal --out /tmp/turing-internal-review
```

Use fresh output directories. Serve previews over a local HTTP server for search;
`file:` previews can display pages but cannot fetch the search index. No deploy
command exists. Public output contains public pages only; customer/internal
outputs require independent server-side access enforcement. Only the public
review preview is uploaded by the workflow. Draft/noindex labels are not access
controls and must not be used to justify publishing confidential content.

`manifest.json` is the single portal navigation/metadata source. Add a page there,
choose its real audience, use one of the six templates, and link authoritative
contracts rather than copy signatures. All dates reflect an actual source review,
not executed mathematical qualification. Review expiry fails checks deliberately;
perform the review instead of refreshing dates mechanically.

The existing API generator, lock, examples and qualification ledger remain the
source of truth. The documentation workflow checks reference drift and runs the
existing package example in the locked environment. These commands were configured,
not locally executed by this docs-only increment; remote CI must be inspected.
The focused validator checks portal Markdown only, not all historical monorepo
Markdown, external network availability, theorem validity or every possible secret.
Manual scientific, security, IP/disclosure and accessibility review remain required.

This branch is stacked on package PR #96. Service PR #97 remains separate; do not
present its open production gates as merged or qualified. No merge, release tag,
registry upload, deployment, publication approval or invoice is part of this work.
