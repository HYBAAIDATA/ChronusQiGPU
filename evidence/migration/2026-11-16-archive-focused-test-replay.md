# Focused offline archive-test replay — 16 November 2026

**Environment:** Linux, Python 3.13.5, pytest 9.0.2, NumPy 2.3.5. No
internet, no live Stratum and no physical accelerator. Historical provenance
is not a current release certificate.

## Chronos ONE iGPU v3.4

Archive SHA-256:
`406a6b499ecee14a93e172ce274ae92c69381953cabadbd69903d326cc55642d`.

Command in extracted archive:

```bash
cd chronos-completed
PYTHONPATH=src python -m pytest -q \
  tests/test_one_igpu.py tests/test_lucas_engine.py tests/test_lucas_runtime.py
```

Captured stdout:

```
..........                                                               [100%]
10 passed in 3.79s
```

Stdout SHA-256:
`d96a858f3def7cc4d98f2039cbff441c94155cb2b2f70e25f34e8ef797477799`.

## July VQC with July PULVINI import closure

VQC ZIP SHA-256:
`7b4ef03683de8bf03a189293bb72e4493c9a408c5722b38f4a1e2ca8f05e9038`.

The original `phi_quantum_machine.py`, `vqc_phi_grover.py` and two original
test files were placed **only into a temporary test package** at
`euclid.pythagoras.quantum.pulvini_enterprise`. Their missing formal import
was supplied by the original `formal.py` in the separately recovered July
PULVINI enterprise ZIP. This is deliberately a *mixed-archive replay*, not
proof of a shipped standalone package.

```bash
PYTHONPATH=. python -m pytest -q \
  test_phi_quantum_machine.py test_vqc_phi_grover.py
```

Captured stdout:

```
......................                                                   [100%]
22 passed in 0.19s
```

Stdout SHA-256:
`dc73640ef02afbd8d65d8db048f6b373b2cf15a7b92f5d501ac92bb60870faba`.

## Recovered bounded exact rational tensor train

The isolated source fixture used the same module as
`src/chronus/tensor/exact_rational_tt.py` after the retained-state digest
check was added; it exercised exact rational reconstruction, zero/high-rank
shape handling, invalid dtype/dimension rejections and mutating a retained
core after the digest had been established.

```bash
python -m pytest -q test_exact_rational_tt.py
```

Captured stdout:

```
......                                                                   [100%]
6 passed in 0.04s
```

**Limit:** the test imports the standalone source fixture, not the current
private repository's `chronus.tensor` package initializer. The new
`tests/test_exact_rational_tt_recovery.py` and the modified
`tests/test_geodesic_tensor_migration.py` must run on the exact commit in
the repository CI before a test-pass claim is made for the integrated code.


## Focused safety review replay (after PR #135 review feedback)

The new exact rational TT source was patched with **bounded iterator
consumption** and with the **same shape/site/entry policy at replay** as at
factorisation. Reviewers Qodo and Codex identified those two real gaps on
the original PR head.

A local isolated source fixture was updated with the same algorithm and
three negative tests (infinite source, 65,536-element digest-valid forged
replay, zero-dimension replay). Re-executed in Python 3.13.5:

```
$ python -m pytest -q test_exact_rational_tt.py
.........                                                                [100%]
9 passed in 0.05s
```

Output SHA-256:
`3f2a7d474201c0ea38d8bf1671a9f35e691f355933bdef622342047561fb3da4`.

The **GitHub repository module and its ten-case focused test file** still
require independent exact-commit CI. Standalone source replay never
substitutes for package import, CI result, CodeRabbit/Qodo closure or a
production release verdict.


An additional deterministic digest-reproduction test was then included in
the isolated fixture, corresponding to the tenth focused test in the PR.
The same bounded source fixture was re-executed:

```
..........                                                               [100%]
10 passed in 0.06s
```

Stdout SHA-256:
`a837324a2f5c0d804ee26513e45c3e17425242b25aba8e53fe57a7379e8a79a5`.

This is still a **standalone local source run**, not the installed
`chronus.tensor` test suite, and is not a green repository CI result.
