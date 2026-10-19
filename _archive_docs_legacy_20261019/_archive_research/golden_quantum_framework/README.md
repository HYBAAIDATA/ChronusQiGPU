# The Golden Quantum Framework

A Python library of φ (golden-ratio) mathematics: exact-integer Fibonacci/Lucas
sequences, Zeckendorf coding, the Fibonacci Q-matrix, continued fractions, and
a golden-ratio generalization of the Fourier transform. "Quantum" in the name
is inherited from the package's original title and is a mathematical-formalism
label — φ's eigenstructure, spectral decomposition, tight-frame constructions
— **not** a claim of running on quantum hardware or providing a quantum
computational advantage. Nothing in this package touches a QPU, a quantum
simulator, or asymptotic quantum speedup; every check here is classical
arithmetic (Python `int`/`Decimal`) or classical NumPy/FFT computation,
verified against classical alternatives (direct summation, plain DFT).

This document was rewritten from a fresh read of every source and test file
in this directory and a real run of both the test suite and the CLI runner
(details and exact numbers in [Verified status](#verified-status) below).

## Installation

```bash
cd golden_quantum_framework
pip install -e .
```

This is a real installable package (`pyproject.toml`, `setuptools` build
backend, `src/` layout). It declares `numpy` as a runtime dependency (added
in this pass — the four Fourier-bridge modules described below `import numpy`
but the package's `pyproject.toml` did not list it, so a bare `pip install -e .`
in a clean environment would previously fail on `import golden_quantum.golden_fourier`
with `ModuleNotFoundError`; the CI workflow masked this because it separately
runs `pip install pytest numpy`).

## Quick start

### As a library

```python
from golden_quantum.runner import run_all
registry = run_all(max_n=2000)
print(f"Passed:{registry.passed_count}/{registry.total}")
```

Actual output from running this exact snippet in this pass:

```
Passed:107/107
```

### As a CLI tool

```bash
python -m golden_quantum.runner --max-n 2000 --json
# or, once installed: gqf --max-n 2000 --json
```

Actual `summary` block from running this exact command in this pass:

```json
{
  "total": 107,
  "passed": 107,
  "failed": 0,
  "theorems": 74,
  "invariants": 15,
  "demonstrations": 18,
  "all_theorems_invariants_passed": true
}
```

## What "theorem / invariant / demonstration" means

Every check the runner performs is classified as one of:

- **theorem** — a proven mathematical identity, verified computationally
  (e.g. Cassini's identity, checked exactly with Python's arbitrary-precision
  integers — no floating point).
- **invariant** — a structural property that must always hold (e.g. a
  Fibonacci codeword is always prefix-free).
- **demonstration** — an empirical/statistical observation, not a proof
  (e.g. "the golden-angle point sequence has lower discrepancy than a random
  sequence on this sample" — true on the sampled data, not a universal proof).

`run_all()`/`gqf` reports `all_theorems_invariants_passed = True` iff every
**theorem** and **invariant** passed; failing demonstrations are reported but
never gate. This classification is real and is what `.github/workflows/gqf-ontology.yml`
gates CI on (see [CI](#ci) below) — it is not decorative.

## Module reference

### Core (`src/golden_quantum/`)

| Module | What it does |
|---|---|
| `constants.py` | φ, ψ (golden ratio and conjugate) as arbitrary-precision `Decimal`, at a **global 10000-digit precision context** — see the [performance note](#known-limitations--gaps) below. Also the golden angle constants. |
| `sequences.py` | `fibonacci`/`lucas` via O(log n) fast-doubling on Python's arbitrary-precision `int`; `binet_f`/`binet_l` via Binet's closed-form formula on `Decimal`, independently verified to match the exact integer sequences. |
| `coding.py` | Zeckendorf representation and Fibonacci coding (prefix-free, self-delimiting integer codec). |
| `matrices.py` | The Fibonacci Q-matrix `[[1,1],[1,0]]`, its powers, determinant, trace, multiplication. |
| `continued_fraction.py` | φ's continued fraction `[1;1,1,1,...]`, computed **independently** via subtract-and-invert on high-precision `Decimal` (not just asserted as `[1]*n`), plus convergents and the badly-approximable (Hurwitz) bound. |
| `results.py` | `CheckResult`/`CheckRegistry` — the theorem/invariant/demonstration bookkeeping described above. |
| `registry.py` | `FAMILY_REGISTRY` — the list of families `run_all()` executes. |
| `runner.py` | The CLI/library entry point (`run_all`, `format_report`, `format_json`, `main`). |

### The 10 φ-families (`src/golden_quantum/families/`)

Each family pairs a piece of φ-mathematics with the computational purpose it
actually demonstrates, and is registered in `registry.FAMILY_REGISTRY` /
executed by `runner.run_all()`:

| # | Family | Purpose | Key mathematics |
|---|---|---|---|
| 1 | φ + Lucas | SCALING | `L(n) = φⁿ + ψⁿ`; nonresonance of `log_φ(b)` for integer bases |
| 2 | φ + Binet/Pisot | FOLDING | `F(n) = (φⁿ - ψⁿ)/√5`; Pisot property `\|ψ\| < 1` |
| 3 | φ + Fibonacci | STORING | Zeckendorf representation, Fibonacci coding |
| 4 | φ + Cassini | SIGNAL | `F(n-1)F(n+1) - F(n)² = (-1)ⁿ`; Catalan's identity generalization |
| 5 | φ + Eigenstructure | TRANSFORM | Q-matrix eigenvalues `φ`, `ψ`; Cayley-Hamilton `Q² = Q + I` |
| 6 | φ + Continued Fraction | SAMPLING | `φ = [1;1,1,…]`, the "most irrational" number |
| 7 | φ + Golden Angle | LAYOUT | `360°/φ² ≈ 137.508°`; low-discrepancy point layout |
| 8 | φ + KAM | STABILITY | Diophantine condition, small-divisor / resonance avoidance |
| 9 | Runtime Infrastructure | RUNTIME | Cassini-based matrix integrity, exact-integer folding, golden-angle lifting, generalized Pisot convergence, delta+FOR compression |
| 10 | Mathematical Identities | IDENTITIES | d'Ocagne's identity, Honsberger's identity, Fibonacci/Lucas polynomials |

Every check in families 1–10 was read in full for this pass; the arithmetic
is exact-integer (`fibonacci`/`lucas`/matrix entries are Python `int`) or
bounded-tolerance `Decimal`, with explicit tolerances stated in the code
(typically `1e-100` for algebraic identity checks on `PHI_D`/`PSI_D`, since
those are `Decimal` approximations of irrational numbers, not the numbers
themselves).

Families 9 and 10 live under `src/golden_quantum/runtime/` and
`src/golden_quantum/math_identities/` respectively (submodules, not flat
files) — e.g. `runtime/memory.py` reproduces and then fixes a real
capacity-check bug pattern (`gap² >= size` accepting an allocation that
underflows) as a worked example, with both the buggy and corrected versions
kept and tested.

### The Golden-Fourier bridge (`src/golden_quantum/golden_fourier.py` + 3 extensions)

Four modules generalizing the Fourier transform along the φ axis. **These are
not part of `FAMILY_REGISTRY` and are not executed by `run_all()`/`gqf`** —
see [Known limitations](#known-limitations--gaps).

- **`golden_fourier.py`** — `GF(ω, n) = Σ f(k)·φ^(-nk)·e^(-iωk)`. The forward
  transform is a direct O(N·L·M) summation, stable because `φ^(-nk)` decays.
  The inverse (`golden_fourier_inverse`) requires damping regularization
  because `φ^(nk)` grows without bound; this makes it **lossy**, not exact —
  measured on the package's own test data (`tests/test_gf.py`,
  `np.random.seed(42)`, N=30, damping=1/φ): relative reconstruction error
  **≈0.164** (the test only asserts `< 0.5`, a loose bound, not high
  precision). `golden_fourier_reduction` recovers the plain Fourier limit
  (`φ→1`) by recomputing a DFT from the original signal — not by slicing
  `GF`, since φ's decay is already baked into every entry and can't be
  subtracted back out. `detect_phi_structure` classifies a signal as
  φ-structured vs. Fourier-structured by comparing energy on the two edges of
  the `(ω, n)` grid.

  Real example run in this pass (`np.random.seed(0)`, a mixed
  sine+noise signal, matching `tests/test_gf.py::test_phi_structure_detection`):
  correctly reports `is_phi_structured = False` with `fourier_energy_ratio ≈
  0.998` — i.e. it correctly identifies a sinusoid as Fourier-structured, not
  φ-structured.

- **`metallic_fourier.py`** — generalizes to the full metallic-mean family
  `σ_p = (p + √(p²+4))/2` (`p=1`→golden ≈1.618, `p=2`→silver ≈2.414,
  `p=3`→bronze ≈3.303). `p=1` is verified in this pass to match
  `golden_fourier_forward` **exactly** (`np.max(np.abs(GF - MF1)) == 0.0`,
  bit-for-bit, not just within tolerance).

- **`golden_czt.py`** — the same `GF_n(k)` transform computed via Bluestein's
  Chirp Z-Transform in O(N log N) instead of O(N²), computing the φ-decay
  term `φ^(-nm)` directly in log-space (`exp(-n·m·log(φ))`) so it never forms
  `φ^n` as an intermediate value. This matters because `φ^n` as a bare
  `float` overflows around **n≈1475** (`φ^1450` survives, `φ^1475` raises
  `OverflowError` — confirmed in this pass). Verified in this pass: matches
  `golden_fourier_forward` to **max abs diff ≈3.9e-13** on random test data,
  and evaluates cleanly (no NaN/Inf) at `n=1500`, past the point where the
  naive approach would overflow.

- **`golden_wavelet.py`** — replaces `golden_fourier_inverse`'s damping hack
  with a genuine Meyer/Littlewood-Paley-style wavelet frame, dilated by `φⁿ`
  instead of the usual `2ⁿ`. The tiling identity `Σₙ |ψ̂(φⁿω)|² = 1` (a tight
  frame, A=B=1) is provable from the construction (`sin²+cos²=1`), not just
  observed. Verified numerically in this pass:
  - Tight-frame bounds: `A ≈ 0.99999999999999870`, `B ≈ 1.00000000000000133`,
    max deviation from 1 **≈1.33e-15**.
  - Lossless reconstruction on a 256-sample test signal: max error
    **≈1.33e-15** (float precision, not an approximation).
  - Survives scales up to `n=1500` (past the same `φ^n` overflow point as
    `golden_czt.py`) without NaN/Inf, because `psi_hat_sq` also computes in
    log-space rather than forming `φ^n`.

  This is a materially more precise inverse than `golden_fourier_inverse`'s
  damping approach (≈1e-15 vs. ≈0.16 relative error) for the same underlying
  φ-Fourier bridge, at the cost of restructuring the inverse as a filter-bank
  synthesis rather than a direct summation.

## Verified status

Run in this pass, in this environment (Python 3.12.10, numpy 2.4.6, pytest 9.1.1):

- **`python -m pytest tests -q`** from `golden_quantum_framework/`: **92
  passed, 0 failed** (exit code 0) — `test_framework.py` (20),
  `test_gf.py` (4), `test_golden_fourier_extensions.py` (9),
  `test_hyba_math_family.py` (33), `test_runtime.py` (26).
- **`python -m golden_quantum.runner --max-n 2000 --json`**: **107/107**
  checks passed — 74 theorems, 15 invariants, 18 demonstrations, exit 0.
  (This only covers families 1–10; the Golden-Fourier bridge modules are not
  part of this count — see below.)

### CI

`.github/workflows/gqf-ontology.yml` runs on every push/PR touching this
directory: it runs `pytest tests -q` (all 5 test files, since `pytest`
auto-discovers `test_gf.py` and `test_golden_fourier_extensions.py`
alongside the family/runtime/identity tests), then
`python -m golden_quantum.runner --max-n 2000 --json` and asserts
`all_theorems_invariants_passed`. A failing theorem or invariant fails the
build; a failing demonstration does not.

## Known limitations / gaps

- **The Golden-Fourier bridge (`golden_fourier.py`, `metallic_fourier.py`,
  `golden_czt.py`, `golden_wavelet.py`) is not registered in
  `registry.FAMILY_REGISTRY` and is not run by `runner.run_all()`/`gqf`.**
  It has its own real, passing pytest coverage (`test_gf.py`,
  `test_golden_fourier_extensions.py` — 13 tests total, included in the 92
  above and gated by the same CI job), but it does not get the
  theorem/invariant/demonstration classification, the CLI/JSON evidence
  output, or the `all_theorems_invariants_passed` gate that families 1–10
  get. If you need that classification and evidence trail for this code,
  registering it as an 11th family (or a `hyba_math`-style submodule under
  an existing one) is still open work, not done.
- **`golden_fourier_inverse`'s damping-based inverse is lossy**, not exact —
  measured relative error ≈0.164 on the package's own random test data (see
  above), with the test itself only requiring `< 0.5`. Treat it as a coarse
  approximation, not a precise inverse; `golden_wavelet.py`'s frame-based
  synthesis is verified to ≈1e-15 for the same underlying transform and is
  the better choice where reconstruction accuracy matters.
- **`pyproject.toml` did not declare `numpy` as a dependency** even though
  four modules `import numpy` directly — fixed in this pass
  (`dependencies = ["numpy>=1.24"]` added). Before this fix, a clean
  `pip install -e .` outside an environment that already happened to have
  numpy installed would leave those four modules unimportable.
- **The test suite is slow**: a full `pytest tests -q` run took
  approximately 6 minutes wall-clock in this environment, dominated by
  `constants.py` setting a **global** `decimal.getcontext().prec = 10000`
  (10000 significant digits) that every `Decimal` operation in the process
  inherits by default, even in checks that don't need anywhere near that
  precision. Family/runtime code that needs less precision does open a
  `localcontext()` in several places (e.g. `sequences.binet_f`), but not
  everywhere — e.g. many family-module identity checks compute directly
  against module-level `PHI_D`/`PSI_D`, which were built at the global
  10000-digit precision. This is a real, measured characteristic, not a
  hypothetical one — plan CI/local timeouts accordingly (the CI job above
  budgets 15 minutes).
- Provenance: this directory's `.py` sources were imported from an external
  zip upload rather than written fresh in this repository; see
  `PROVENANCE.md` and `VERIFICATION.md` for the byte-level hash verification
  of that import. Those two files predate `golden_fourier.py` and its three
  extension modules (added in a later session pass) and their tests, so
  their manifests do not cover those four files or `test_gf.py`/
  `test_golden_fourier_extensions.py` — this README's "Verified status"
  section above is the current, complete picture across all five test files
  and all modules.

## Architecture

```
golden_quantum_framework/
├── pyproject.toml
├── README.md               (this file)
├── PROVENANCE.md            (import provenance for the original 35-file archive)
├── VERIFICATION.md          (byte-hash verification of that import)
├── src/golden_quantum/
│   ├── __init__.py
│   ├── constants.py          # φ, ψ, precision, bases, golden angle
│   ├── sequences.py          # fibonacci, lucas, binet (arbitrary precision)
│   ├── coding.py              # zeckendorf, fibonacci coding
│   ├── matrices.py            # Q-matrix powers, det, trace
│   ├── continued_fraction.py  # CF of φ, convergents, approximability
│   ├── results.py             # CheckResult, CheckRegistry
│   ├── registry.py            # Family registry (families 1-10 only)
│   ├── runner.py              # CLI runner with --json output
│   ├── golden_fourier.py      # Golden-Fourier bridge (NOT in registry — see gaps)
│   ├── metallic_fourier.py    # Metallic-mean generalization (NOT in registry)
│   ├── golden_czt.py          # Bluestein CZT-stable variant (NOT in registry)
│   ├── golden_wavelet.py      # Golden-dilated wavelet frame (NOT in registry)
│   ├── families/               # Families 1-8
│   │   ├── scaling.py, folding.py, storing.py, signal.py,
│   │   ├── transform.py, sampling.py, layout.py, stability.py,
│   │   ├── runtime.py          # Family 9 (thin wrapper over runtime/)
│   │   ├── hyba_math.py        # Family 10 (thin wrapper over math_identities/)
│   │   └── comparison.py       # shared helper (approximability comparison)
│   ├── runtime/                 # Family 9 implementation
│   │   ├── integrity.py, folds.py, lifting.py, pisot.py,
│   │   ├── delta_for.py, memory.py
│   └── math_identities/         # Family 10 implementation
│       ├── docagne.py, honsberger.py, polynomials.py
└── tests/
    ├── test_framework.py                  # core (sequences/coding/matrices)
    ├── test_runtime.py                    # runtime/ submodule
    ├── test_hyba_math_family.py           # math_identities/ submodule (pytest)
    ├── test_gf.py                         # golden_fourier.py
    └── test_golden_fourier_extensions.py  # metallic_fourier/golden_czt/golden_wavelet
```

## License

MIT
