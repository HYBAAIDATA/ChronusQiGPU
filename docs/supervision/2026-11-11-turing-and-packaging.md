# TURING and packaging consolidation: supervision record

**Date:** 11 November 2026
**Scope:** the TURING library expansion and how HYBA's packages are built for deployment, as assigned by Andre Taylor-Morris. Other workstreams (CI repairs, AL HARAS, attestation, mining) keep their own branches and are not changed here.
**Standard:** AGENTS.md and docs/directives. Every statement below is backed by a test run recorded in section 7 or by the file it names.

## 1. Outcome

- One TURING package. `src/turing` (the exact cyclotomic library) moved to `packages/turing/src/turing/exact` and is imported as `turing.exact`, so the repository no longer has two top-level `turing` packages that shadowed each other.
- Two private distributions with no overlap: `hyba-chronus` 37.0.0.dev0 ships only `chronus`, and `hyba-turing` 0.2.0.dev0 ships only `turing`. Both carry `Private :: Do Not Upload`, which makes the public package index refuse an accidental upload, and `License :: Other/Proprietary License`.
- The root LICENSE named the MIT License for "Chronus Systems" and was copied into every wheel. It now carries a proprietary notice for HYBA Software Ltd, consistent with black-box delivery.
- Every module that ships compiles. `src/chronus/core/trust_ledger.py` could not compile and nothing imported it, so it is held unchanged in `archive/fragments/` with a README.
- New gates: `scripts/ci/check_wheels.py` (private classifier, disjoint packages, compiling modules, no working files), `scripts/ci/check_no_temporary_workflows.py` (no scratch or diagnostic workflow reaches main) and `.github/workflows/packages.yml`, which also runs the TURING tests against the installed wheel outside the source tree.
- Root clean-up: diagnostic dumps moved to `archive/diagnostics/2026-11-11/`, TURING source snapshots to `archive/turing-sources/`, and the two root API wrappers to `archive/root-entrypoints/`, each with a README. Nothing was deleted.
- Re-export namespaces for the names Andre uses: `chronus.hermes` (the bounded Fourier and state modules), `chronus.ovid`, `chronus.theseus`, `chronus.geodesic` and `chronus.igpu.tensor`. Each re-exports the existing objects; tests prove they are the same objects.

## 2. TURING canonical algorithm suite

The build contract is `packages/turing/docs/SPECIFICATION.md`. The implementation is on `feat/turing-exact-algorithms` and merges separately:

- `turing.algebra`: exact cyclotomic fields Q(ζ_n), and the reduction Z[ζ_256] → F_257 used only as an arithmetic checksum.
- `turing.algorithms`: Deutsch–Jozsa, Bernstein–Vazirani, Simon, Grover (exact two-term rational recurrence), QFT, QPE and Shor's order finding with exact continued fractions; a Clifford tableau path; and the 2,500-qubit structured instances (GHZ, affine Deutsch–Jozsa, linear Bernstein–Vazirani and Simon, dyadic QPE).
- 84 tests, no floating point and no randomness in these modules, and no import of `chronus`.

What 2,500 qubits means: exact evaluation at that size is real for Clifford circuits, affine or linear oracles and dyadic phase estimation. It is not available for Shor on cryptographic moduli (the sum runs over 2^(2n) inputs, about 10^616.5 terms for a 1,024-bit modulus), for Grover at its optimal iteration count (about 2^1249.65 iterations at N = 2^2500) or for general circuits. Nothing in the suite claims cryptanalysis, a quantum advantage or fault-tolerant qubits.

## 3. Tensor and iGPU

`EnhancedTensorRepresentation` stays inside Chronus and is exposed at `chronus.igpu.tensor`; it is not published as its own package. The audit did not confirm a code-level coupling to the OpenCL kernels or the `cpp/` library: the class is a numpy tensor network that records its truncations. The decision stands for two other reasons. It is floating point, so it cannot enter TURING's exact path, and TURING importing Chronus would create a cycle between the two distributions. Hendrix and Chronus code may import it from `chronus.igpu.tensor`; TURING never does.

## 4. Black-box delivery

Participants receive capabilities, never code they can read:

1. **Hosted service (default).** Participants call HYBA's service through a thin client that contains no mathematics. Nothing executable leaves HYBA.
2. **Sealed appliance (only where a site cannot connect).** An encrypted image that runs inside a confidential-computing environment and receives its keys only after remote attestation. An offline, hardware-bound Ed25519 lease enables named capabilities for a fixed period.
3. **Compiled modules are defence in depth only.** Native compilation raises the cost of inspection but does not prevent it, so it is never the primary control.
4. **Contract.** The HYBA Restricted Evaluation Licence (Draft 0.1, DIFC law) prohibits reverse engineering, probing and benchmarking for publication, and sets out a capability statement that matches section 2.

Packaging rules that follow: wheels stay internal; no source distribution or wheel is given to a participant; installs use HYBA's private index or `--no-index` only, so a look-alike package on the public index cannot be pulled in by name.

Hardening found on `main` that must close before any participant connects: the interactive API documentation and OpenAPI schema are enabled, `/health` and `/metrics` answer without authentication, and some responses expose internal fields.

## 5. Corrections recorded

| Statement in circulation | Finding |
|---|---|
| 3^16 ≡ 136 (mod 257) | 3^16 ≡ 249 (= −8), of order 16; 136 = 3^8, of order 32 |
| Amplitudes carried in F_257 | F_257 has no absolute value and the reduction is many-to-one; it is used only as a checksum |
| "11D 600-cell polytope" | The 600-cell is 4-dimensional with 120 vertices, as the code's own invariants assert |
| Ovid logic in `apply_ovid_patch.py` | The file has been empty since commit e04dbd0; Ovid is `chronus.security.ovid` |
| Theseus as path traversal | `chronus.storage.theseus` is storage |
| "O(1) Galois search" | `chronus.math.f257_search` computes closed-form parameters from a given seed; Hendrix lookups are constant time per query after a table build of size p − 1 for small primes only |
| Existing DJ, BV, Simon, QPE and Shor | None existed before this work; Grover existed only in `chronus.quantum.grover` |
| UK NSI Act as an export control | The NSI Act governs acquisitions; exports from the UAE fall under UAE strategic-goods controls, plus the importing country's rules |

## 6. Left with other workstreams or the owner

- `BLOCKER_MILLENIEIEUM_1.patch`, `BLOCKER_MILLENIEIEUM_2.patch` and `BLOCKER_TOE_1.patch` neither apply nor reverse-apply on `main`; their owners should rebase or retire them.
- The root `qigpu_*` acceleration scripts are kept for the Hermes reconciliation; the root AL HARAS and mining scripts, `chronus_source_backup/` (which carries its own MIT licence file) and the duplicate Kubernetes manifests are untouched.
- `scripts/ci/test_the_tests.py` rewrites seven source files with different line endings after each run (content identical), leaving the working tree changed.
- Pull request #26 carries a diagnostics workflow its author will remove before merge; the new hygiene gate fails until then. Pull request #27 is a scratch workbench and is never merged.

## 7. Evidence

| Run | Commit | Python | Result |
|---|---|---|---|
| `main` after PR #28 | 438e409 | 3.13.18 | 987 passed, 25 skipped |
| Consolidation branch | 942dd4a | 3.13.18 | 997 passed, 25 skipped; ruff, compile, claim, purity and mutation gates pass; both wheels build and pass the wheel check |
| TURING wheel alone, outside the tree | 942dd4a | 3.13.18 | 74 passed; `chronus` not imported |

All runs: GitHub-hosted Ubuntu 26.04 runner, 11 November 2026, `python -m pytest -q`.
