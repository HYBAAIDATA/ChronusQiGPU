# Provenance — golden_quantum_framework/

Imported into this repository on 2026-08-16 from the workspace upload
`golden-quantum-framework (1).zip` (zip-imported to the workspace on 2026-08-15).

## Recovery notes (doctrine §11 — attributable provenance)

- All 35 `.py` sources were recovered verbatim from the import's attachment
  store; the directory structure and the egg-info metadata were cross-checked
  against `SOURCES.txt`.
- `pyproject.toml` could not be recovered as an attachment at import time
  (file-type limitation of the import), and was reconstructed. **Superseded
  2026-08-18 — see "pyproject.toml recovered" below.**
- The import's registry includes two extension families beyond the README's
  original eight: Family 9 (Runtime Infrastructure) and Family 10
  (Mathematical Identities: d'Ocagne, Honsberger, Fibonacci/Lucas polynomials).

## Verification before import (Veritas Rule 0 — run, don't trust)

Executed in an isolated sandbox on 2026-08-16 before this commit:

- `tests/test_framework.py` (standalone runner): **20/20 passed**
- `tests/test_runtime.py` (standalone runner): **26/26 passed**
- `python -m golden_quantum.runner --max-n 2000`: **107/107 checks passed**
  (74 theorems, 15 invariants, 18 demonstrations), exit 0
- Sandbox: Python 3.13, standard library only. `tests/test_hyba_math_family.py`
  imports `pytest` and is exercised in CI (mining-evidence-gate), where pytest
  is installed.

## CI gating

The framework's tests and the theorem-gated runner execute on every push via
`.github/workflows/ci.yml` (mining-evidence-gate). The runner exits non-zero
if any theorem or invariant fails; demonstrations are advisory per the
framework's own classification — aligned with doctrine §5 and §9.

## pyproject.toml recovered (2026-08-18)

The authentic `pyproject.toml` was recovered from the source archive
`golden-quantum-framework.zip` (SHA-256
`f089b4bfbcc74f75cceaf6387cf6e886175381a46937a948d0ebe3029526ce3a`; the
`golden-quantum-framework (1).zip` in the same location is byte-identical).
The reconstruction it replaces had drifted from the original in five ways:

| Field | Reconstruction | Authentic |
|---|---|---|
| `description` | paraphrased | upstream wording restored |
| `requires-python` | `>=3.11` | `>=3.10` |
| `authors` | absent | `[{name = "HYBA"}]` |
| `keywords` | absent | 7 keywords restored |
| `[tool.setuptools.package-dir]` | **absent** | `"" = "src"` restored |

`dependencies = ["numpy>=1.24"]` is retained and is **not** upstream metadata.
numpy is required by the in-repo extensions (`golden_fourier`, `golden_czt`,
`golden_wavelet`, `metallic_fourier`), which are additions to the imported
framework and not part of the v1.0 import. The file now carries a comment
saying so, per doctrine §12 (no document may drift from implementation truth).

### Source-file drift corrected in the same pass

Comparing the tracked tree against the authentic archive (line endings
normalised) found 37 files identical, 8 files present only in this repository
(the `golden_fourier`/CZT/wavelet/metallic-mean extensions plus `PROVENANCE.md`
and `VERIFICATION.md` — additions, correctly retained), and three files where
the tracked copy had drifted from the import:

- `families/hyba_math.py` — an f-string brace escape had been lost, so the
  check label rendered `F_n-1(x)` instead of `F_{n-1}(x)`. The Lucas-polynomial
  identity is L_n(x) = F_{n-1}(x) + F_{n+1}(x); the drifted label misstated it
  in test output. Restored from the archive.
- `math_identities/honsberger.py`, `math_identities/polynomials.py` — two
  explanatory comments each, dropped by the same brace-stripping pass.
  Restored.

`README.md` also differs, but in the other direction: the tracked copy is
ahead (+259 lines, 26 references to the in-repo extensions) and is retained.
