# Security

Use the repository/organization's private security reporting channel for
vulnerabilities. Do not include credentials, provider tokens, customer data or
reproduction secrets in public issues, result manifests or manuscript files.
This document does not invent a security mailbox or override the root policy.

Artifacts and manifests are data: do not evaluate serialized strings as Python.
Local file hashes establish content identity, not authorship or a signed release.
Job identifiers and idempotency keys are local API controls, not authentication.
Review dependency artifacts, licenses and the existing release secret scan before
publication. New runtime integrations need their own authorization and tests.

The actual AL HARAS, Salamander and EUCLID controls, trust assumptions and
unresolved deployment requirements are recorded in
[capability security boundaries](docs/security-boundaries.md). A named dependency
or handoff custody record is not evidence that every security control is active.
