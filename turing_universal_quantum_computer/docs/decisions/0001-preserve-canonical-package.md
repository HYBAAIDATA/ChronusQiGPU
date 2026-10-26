# ADR 0001 — Organize TURING without duplicating or renaming its engine

Status: accepted for this change.

Context: the monorepo already publishes `hyba-turing-vqc`; its inner package,
explicit setuptools package list, console, module registry and sibling systems
have established imports. A generic standalone-project blueprint is useful for
separation of concerns, not authority to create a second engine/product.

Decision: retain the canonical distribution/import namespace and engine paths.
Add a typed convenience surface and discrete package-root directories for
experiments, results, docs, examples and the publication draft. Preserve existing
aliases and the canonical `VQCPipeline`. Do not add empty control/QEC modules.

Consequences: existing consumers remain compatible. The implementation is not
moved to `src/` in this PR. Any future source-layout migration must be mechanical,
separately reviewed, include installed wheel/sdist tests and migrate all package
build/release callers together. It must not duplicate the canonical engine or
change the mathematical meaning of execution.
