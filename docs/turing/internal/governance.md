# Ownership, versioning and corrections

## Ownership and review

The manifest is the single metadata/navigation source. Each page records audience, version, owner role, actual source-review date, review due date and verification scope. Role placeholders are not named accountability or signoff. Assign actual people before release. Last-verified changes only after a real review; CI never refreshes it automatically.

Review every implementation change that affects public interfaces, domains, failure semantics, security or customer tasks. Review customer service content with service/commercial owners; mathematics with its reviewer; security/operations with their owners. Public approval needs an auditable review reference and a release-bound claim review.

## Version and deprecation

The current docs describe an unapproved candidate after existing 1.0.0 metadata, not a newly published version. Use one candidate label until maintainers choose a version across package metadata, citation, gates and docs. Never promise an unapproved support window. Add a version selector only when multiple approved supported snapshots actually exist.

For a deprecation, retain the old signature/semantics, affected versions, rationale, replacement example, migration tests, notice and approved removal schedule. No silent symbol changes or redirected incompatible examples.

## Report and correct a defect

Use the repository's existing issue/PR process. Report page, candidate/source commit, inaccurate sentence or broken example, expected behaviour and minimal sanitised evidence. Never place secrets or customer data in a public issue. Security reports follow the existing package security policy.

Triage by impact. Wrong mathematical/security/service claims block publication. Correct the authoritative source first, regenerate reference material, update impacted guides and claim records, run docs and relevant product checks, and obtain owner review. Retain an erratum for material published claims; do not silently erase history.

## Access and publication

Build three isolated outputs: public-only, public+customer (behind real customer access) and internal (all pages, restricted). Search indexes, navigation and rendered content are filtered at build time. Public pages may not link customer/internal pages. No output is published automatically; candidate previews carry a draft banner.

Separate origins/buckets and server-enforced access are deployment requirements, not implemented authentication in the static builder. Never upload internal build artifacts to a public host. PR artifacts remain within repository permissions, not the intended eventual customer authorization model.
