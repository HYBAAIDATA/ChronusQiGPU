# Version Consolidation Report (GAP-6)

Policy chosen: **each package has exactly ONE canonical `__version__`
literal, located in its top-level `__init__.py`.** A distribution's
`pyproject.toml [project].version` is a packaging *mirror* — it must equal
the runtime literal, never differ. No other module may redeclare a
literal; it must import it (precedent: `kellogg/attest.py` derives via
`getattr(kellogg, "__version__")`).

Enforced by `tests/test_version_single_source.py` — 23 tests, all passing.

## Audit table

| Package | Canonical site | Runtime `__version__` | pyproject mirror | Installed metadata | Status |
| --- | --- | --- | --- | --- | --- |
| `aethel` | `aethel/__init__.py` | `1.0.0` | — (no pyproject) | none | ✓ single source |
| `kellogg` | `kellogg/__init__.py` | `3.5.0` | — | none | ✓ single source |
| `toe` | `toe/__init__.py` | `3.5.0` | — | none | ✓ **fixed**: literal moved out of `toe/engine.py` into `__init__.py`; engine now does `from toe import __version__` |
| `hyba` | `hyba/__init__.py` | `0.1.0` | — | none | ✓ **fixed**: no version existed; canonical literal added (tracks repo distribution) |
| `turing_universal_quantum_computer` | `turing_universal_quantum_computer/turing_universal_quantum_computer/__init__.py` | `1.0.0` | `turing_universal_quantum_computer/pyproject.toml` = `1.0.0` | none (egg-info dir present but not installed) | ✓ mirror equal |
| repo dist `pythia-mla1517` | `pyproject.toml` (root) | — (no `pythia_mla1517` package) | canonical = `0.1.0` | none | ✓ SemVer, self-canonical |

## Notes

- **No package has installed metadata**: `importlib.metadata.version()`
  raises `PackageNotFoundError` for every distribution — nothing is
  pip-installed. The test asserts agreement *when* metadata appears.
- `import turing_universal_quantum_computer` requires the outer project
  dir on `sys.path` (PEP-420 outer dir is a namespace container, not the
  package) — same convention `system_fabric.py` uses via `_TUQC_DIR`.
  The test performs this insertion.
- Excluded as generated artifacts (untracked, not version sites):
  `turing_universal_quantum_computer/build/lib/.../__init__.py`
  (stale build copy — literal `1.0.0`, currently equal; not enforced),
  `.kilo/worktrees/**` (foreign worktree), `__pycache__`, `legacy/**`.
- `legacy/**` retains historical version strings by design (frozen
  archive); the policy applies to canonical packages only.
