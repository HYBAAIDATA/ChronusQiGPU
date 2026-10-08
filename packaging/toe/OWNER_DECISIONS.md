# TOE publication — owner decisions required

Publication of TOE to TestPyPI/PyPI is **blocked** until the decisions below are
recorded here by the owner (HYBA Software Limited). Everything else in the release
pipeline runs without them; `packaging/toe/build_and_verify.py` reports
`publishable: false` while any item is open.

## 1. Public distribution name — APPROVED

Owner naming instruction: use `hyba-<system>-<capability>` consistently.
The approved first-public identity is **hyba-toe-intelligence==1.0.0**.
This supersedes the previous candidate name `hyba-toe`; it is not a claim
that the new registry namespace is available, configured or published.
The import name remains `toe`.

APPROVED_DISTRIBUTION_NAME: hyba-toe-intelligence

## 2. Release version — APPROVED

Owner decision recorded 2026-10-07: **every first public HYBA product release starts at 1.0.0**.
TOE's internal development/history may have used 3.5.0, but unpublished development
versioning does not become the public package version.

APPROVED_VERSION: 1.0.0

## 3. Registry prerequisites — OPEN (external)

- `hyba-kellogg-tensor` 1.0.0 must be live on PyPI first (TOE depends on it).
- Configure PyPI and TestPyPI trusted publishers for the approved name:
  owner `QuantumPhiRedux`, repository `PhiMiner`, workflow `toe-release.yml`,
  environments `testpypi` and `pypi` (see `packaging/PUBLISHING.md`).
- GitHub Actions must be able to start jobs for the repository.
