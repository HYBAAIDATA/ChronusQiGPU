# Contributing to TURING

Use the monorepo's contribution and security policies. Keep this package's
implementation in its canonical inner package, runnable research definitions in
`experiments/`, generated evidence in `results/`, and manuscript content in
`paper/`. Do not duplicate engines or add empty modules for planned features.

Every new public contract needs positive, negative and result/provenance tests.
Register added modules in `product_registry`. Preserve exact values and declared
representation semantics. Treat a missing facade binding separately from the
availability of the underlying TURING implementation.

Run `python scripts/run_turing_tests.py .` from the repository root, the affected
native/enterprise tests and installed-artifact checks. `--all` runs the native
suite. Format new files with Black at line length 100; avoid reformatting unrelated
engines. Never commit credentials, private runtime paths, wheel binaries or
fabricated evidence. Baseline failures must be reported, not silently skipped or
weakened. The existing release workflow owns registry publication.
