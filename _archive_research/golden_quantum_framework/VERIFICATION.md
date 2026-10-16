# Golden Quantum Framework — Import Verification

**Date:** 2026-08-16
**Verified by:** git blob SHA-1 comparison, archive vs committed tree
**Result:** 35 / 35 imported source and test files byte-identical

## Method

Each file was hashed exactly as git hashes a blob:

```
sha1(b"blob " + str(len(content)).encode() + b"\0" + content)
```

The hashes below were computed from the verified extraction archive, then
compared against the `sha` field GitHub returns for every blob in
`golden_quantum_framework/`. Anyone can repeat the check:

```bash
git hash-object golden_quantum_framework/src/golden_quantum/runner.py
# -> 83c9bc0688d18ba9a3c7d63c904efe1f3716bb17
```

This matters because the import was transcribed rather than copied over a
network link. Transcription can silently alter content, so the claim "this
is the framework" is only worth what its hashes prove.

## Manifest

Paths are relative to `golden_quantum_framework/`.

| Path | Bytes | Blob SHA-1 |
| --- | --- | --- |
| `src/golden_quantum/__init__.py` | 1125 | `aa2232d67b23d8413445b09f97ee105eb7604c25` |
| `src/golden_quantum/coding.py` | 3868 | `d6cf8eda2e0b59c07240ec19c5ebe2bd4a9b8cff` |
| `src/golden_quantum/constants.py` | 1645 | `9027e16f41a7e0aa34673b58a0bf4d47d0d89b7e` |
| `src/golden_quantum/continued_fraction.py` | 4443 | `b6a69bfa664c9579d6dc3fa8c18d26729955ae2d` |
| `src/golden_quantum/matrices.py` | 1402 | `13f432ef043f3ebf8624f462c3c11313779e01be` |
| `src/golden_quantum/registry.py` | 1165 | `2e1e37a1239abcc41f6670ac9aa3bccd6e8ce152` |
| `src/golden_quantum/results.py` | 2371 | `f97a86a45d20218578465e4ff8c7ee40eafea7a1` |
| `src/golden_quantum/runner.py` | 5630 | `83c9bc0688d18ba9a3c7d63c904efe1f3716bb17` |
| `src/golden_quantum/sequences.py` | 3420 | `d55874b3dd71ea7513b8c30794be6f5ea49430ee` |
| `src/golden_quantum/families/__init__.py` | 306 | `1fd1bb373261b7ae5876a0445190036ea498a6d6` |
| `src/golden_quantum/families/comparison.py` | 1449 | `d5a8ccd8f3262aaca20773626d1e45bb90051ffb` |
| `src/golden_quantum/families/scaling.py` | 7247 | `ea081bdcfe27bdc54810d6f0265426ab42c4814d` |
| `src/golden_quantum/families/folding.py` | 5910 | `ab6288e4c9f485a3ec465325d6d38417fefd4b08` |
| `src/golden_quantum/families/storing.py` | 6930 | `55c6ffdf0b4e6c2eaa6a52efa578be36a9ee87a8` |
| `src/golden_quantum/families/signal.py` | 6465 | `82aec8bba7fd255501e305f325468f342206af23` |
| `src/golden_quantum/families/transform.py` | 6437 | `e0f252c5df86609bf7b981c1f28439e7199173fc` |
| `src/golden_quantum/families/sampling.py` | 6788 | `0875da59cfdf3dd35790ca22c03a2dc9217ab128` |
| `src/golden_quantum/families/layout.py` | 7152 | `b413b381a8b851cc275b01ddff9723dc7ca82ef3` |
| `src/golden_quantum/families/stability.py` | 8941 | `7d4a5636b454b8de4cfcc22aacc8b7837c5e5f13` |
| `src/golden_quantum/families/runtime.py` | 20481 | `f3cc3a627e69f0d9cbfd7a658bd6c313a75d350b` |
| `src/golden_quantum/families/hyba_math.py` | 14329 | `b8ef9f976f26d6becaaf87c2713dd1511822e71b` |
| `src/golden_quantum/math_identities/__init__.py` | 791 | `3f3c9e0c06cd8799528bc5f35215b52d964fa907` |
| `src/golden_quantum/math_identities/docagne.py` | 1837 | `c052f40093b3a3b8e6e9fd12dbb0213e410cba91` |
| `src/golden_quantum/math_identities/honsberger.py` | 1518 | `5aace8829c2d6bc67fdbf14a17b0fe5faf56f696` |
| `src/golden_quantum/math_identities/polynomials.py` | 3281 | `eaa5836b81e86c8037c3ffe37304e5840fac0de9` |
| `src/golden_quantum/runtime/__init__.py` | 229 | `64f65936a739b15767219a61570b5bb91a3a1cce` |
| `src/golden_quantum/runtime/integrity.py` | 2711 | `147813fd470db2f12dc393d3f3ee36dcc97965c4` |
| `src/golden_quantum/runtime/folds.py` | 2090 | `4cd267af6e6d0233e8a099e5b0813b0487edc173` |
| `src/golden_quantum/runtime/lifting.py` | 2902 | `430739e3fd2a2e05384016beff1497913c4ff30f` |
| `src/golden_quantum/runtime/delta_for.py` | 6534 | `566f5d16dd7bbfe35eb15e1299c1b7c2b07a9892` |
| `src/golden_quantum/runtime/memory.py` | 3219 | `4e6ee78179937521f2328adc412de9b2e59c780a` |
| `src/golden_quantum/runtime/pisot.py` | 3324 | `3c744f57b17390c28af757bfd25bf545a100ad47` |
| `tests/test_framework.py` | 4344 | `341c2b84f6a9445c9ba13cc920ac7f5df0c6c493` |
| `tests/test_runtime.py` | 7039 | `efdaf260df1b18698f7e4b162043c0fb656f8ece` |
| `tests/test_hyba_math_family.py` | 9108 | `50bf5d9af7f2974ff2deda416b25c814a362dd91` |

## Not covered by this manifest

These files are authored or reconstructed, not archive originals, so they
have no upstream hash to match:

- `pyproject.toml` — reconstructed, not recovered. See `PROVENANCE.md`.
- `README.md`, `PROVENANCE.md`, `VERIFICATION.md` — written for this repo.

## Deviation found and corrected (§9)

The first import of `tests/test_hyba_math_family.py` landed at **9072**
bytes against **9108** in the archive. Each of the 12 decorative section
rules carried 66 `U+2550` characters instead of 67 (12 x 3 bytes = 36).
Executable code and assertions were unaffected, but the file was not
byte-identical, so the provenance claim did not hold for it.

Detected by size comparison, corrected in commit `793a67fd`, and
re-verified: the blob now hashes to `50bf5d9a...`.

This is recorded rather than quietly fixed. A verification process that
only ever reports success is not a verification process.

## Execution evidence

Run locally against the archive (Python 3.13, no network):

- `python -m golden_quantum.runner --max-n 2000` — **107 / 107** checks
  passed: 74 theorems, 15 invariants, 18 demonstrations.
- `tests/test_framework.py` — **20 / 20**.
- `tests/test_runtime.py` — **26 / 26**.
- `tests/test_hyba_math_family.py` requires `pytest`, which was unavailable
  in that environment. It executes in CI only, via
  `.github/workflows/gqf-ontology.yml`. Until that workflow reports green,
  this suite is **unexecuted**, not passing.

CI enforcement: `.github/workflows/gqf-ontology.yml` fails the build if any
check classified `theorem` or `invariant` fails. Checks classified
`demonstration` are reported and never gate.
