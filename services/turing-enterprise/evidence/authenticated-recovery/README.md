# Authenticated service-result recovery evidence

This candidate continues live main `fedf91ac7b327929a67bc0e5bc167de22080f1b7`
on `hyba-data-evolution`. It adds authenticated recovery for an already durable
service report when database completion did not commit. See `decision.json` for
source identity, retained failures, hashes, actual test scope and remaining risks.

## Results

| Run | Result | Scope |
| --- | --- | --- |
| Source service + integrations | 144 passed + 10 subtests | Real installed VQC/Kellogg and supplied platform sources |
| Installed service wheel + integrations | 144 passed + 10 subtests | Fresh venv, real runtime; repository platform sources explicitly supplied |
| Installed service sdist + integrations | 144 passed + 10 subtests | Same fresh dependency environment; service reinstalled from sdist |
| Standalone wheel without AL HARAS/platform | 137 passed, 2 failed + 10 subtests | Real missing-dependency failure retained, not skipped or relabelled |
| Actual CI Black policy | 24 files unchanged | Existing sessions.py formatting corrected, no behavioral changes |
| Targeted GitHub secret scan | 9 blobs / 128317 bytes, no secrets | Not a full security approval |

All passing pytest runs retain one upstream Starlette/httpx deprecation warning.
The source and artifact runs include the real process-exit recovery case; fixture
runtime doubles remain explicitly labelled for transport-only unit tests.

## Reproduction commands

Use the complete reviewed repository/platform topology and actual dependencies.
The computational distribution in this run came from the supplied archive, not
a fabricated current-main checkout. Build with `python -m build services/turing-enterprise`.
Install server/test extras, actual TURING and its Kellogg dependency. For the source
run, invoke `python -m pytest services/turing-enterprise/tests services/turing-enterprise/integration -q`
from repository root with the service src path. For the installed service artifact
runs, install the exact wheel or sdist into a fresh environment, then run the same
absolute test paths from outside the checkout with only the repository platform
root on PYTHONPATH, not the service src directory. Retain module locations as in
`artifact-environment.json`. No production secret or network IdP is required by
these isolated TEST fixtures; live identity qualification is separate.

`artifact-payloads.json` records exact built artifact hashes and matching package
payloads. `build.log`, JUnit XML and console logs retain execution evidence.
Standalone install is explicitly not a full deployment configuration. No mock
AL HARAS, duplicate verifier or fabricated fallback was added to hide that fact.

## Decision

Implemented and locally qualified for the stated recovery window. Not complete
canonical service/custody integration, all-engine qualification, live identity or
production deployment. Historical operator waivers stay waivers. Unexecuted or
inaccessible remote checks stay unverified. No new physical-device requirement.
