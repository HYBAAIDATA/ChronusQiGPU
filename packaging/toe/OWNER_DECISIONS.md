# TOE publication — owner decisions required

Publication of TOE to TestPyPI/PyPI is **blocked** until the decisions below are
recorded here by the owner (HYBA Software Limited). Everything else in the release
pipeline runs without them; `packaging/toe/build_and_verify.py` reports
`publishable: false` while any item is open.

## 1. Public distribution name — OPEN

No canonical record in the repository names a public distribution for TOE.

| Candidate | PyPI status (checked 2026-10-07) | Note |
|---|---|---|
| `toe` | **taken** | not available |
| `hyba-toe` | free | used **provisionally** by the build so artefacts can be verified |
| `toe-intelligence` | free | |
| `toe-engine` | free | |
| `hyba-toe-engine` | free | |

The import name is `toe` regardless of the distribution chosen.

To approve, replace this line with: `APPROVED_DISTRIBUTION_NAME: <name>`
and update `name` in `packaging/toe/pyproject.toml` if it differs from the provisional one.

## 2. Release version — OPEN (two owner instructions conflict)

- The TOE elevation brief: the canonical source version is **3.5.0**; do not reset
  TOE's history to 1.0.0 arbitrarily; change it only deliberately per release policy.
- `packaging/RELEASE_STATUS.md`: "First public releases use **1.0.0**."

The artefacts are built at **3.5.0**: runtime version, wheel metadata and capability
manifest stay aligned with the canonical source, and nothing renumbers the package
behind the owner's back. If the owner chooses 1.0.0, change `toe/__init__.py:__version__`
(the single literal), `toe/CAPABILITY_MANIFEST.json` and the workflow's `VERSION`, then rebuild.

To approve, replace this line with: `APPROVED_VERSION: <version>`

## 3. Registry prerequisites — OPEN (external)

- `kellogg-tensor` 1.0.0 must be live on PyPI first (TOE depends on it).
- Configure PyPI and TestPyPI trusted publishers for the approved name:
  owner `QuantumPhiRedux`, repository `PhiMiner`, workflow `toe-release.yml`,
  environments `testpypi` and `pypi` (see `packaging/PUBLISHING.md`).
- GitHub Actions must be able to start jobs for the repository.
