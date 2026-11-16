# Notion and ChatGPT Library source recovery — 16 November 2026

**Scope:** `HYBAAIDATA/ChronusQiGPU` after PR #130 was merged. This is an
evidence-driven source reconciliation and new integration branch, not a
production qualification or a replacement architecture.

## Actual artifact shelves inspected

These Notion pages contain the named **file blocks**, not merely prose:

| Notion authority | Attached artifact and disposition |
| --- | --- |
| [24 July Geodesic/Tensor & PULVINI engineering](https://app.notion.com/p/ffd11e5552144c30ad38a5aaab0b5fcb) | `PULVINI_V3_HERMES_COMPLETION_20260724.zip` — download reference resolved; user-supplied corresponding archive inspected |
| [HYBA 1,000 logical qubits](https://app.notion.com/p/4af52dc709194c5ea68e6d08736a9863) | `HYBA_1000_QUBIT_VQC_20260724.zip` — download reference resolved; user-supplied corresponding archive inspected |
| [HYBA DATA deployment and discoveries](https://app.notion.com/p/0f9aedc5b415479cb34a9b1646f006b4) | `HYBA_DATA_WITH_AUTH.zip`, `HYBA_TESTIMONY_WITH_AUTH.zip` — actual downloadable attachments; content not downloaded in this run |
| [EUCLID posterity artifact shelf](https://app.notion.com/p/2539733ebb7848c9a84ae4e3d7429822) | EUCLID posterity research bundle, learning system and original PULVINI V3 phase/enterprise archives; file blocks located, **not** all binary contents retrieved |
| [Chronos implementation record](https://app.notion.com/p/1e47398b2fed4e29918d10d02480f102) | Source snippets and tests, dated August 2026, including QSDL; archive v3.4 is more complete than the inline earlier examples |
| [QSDL v1.0 source grammar](https://app.notion.com/p/53b6d4ca11304f228e9b487b1f4683c3) | Formal scene-language specification with BNF; does not imply a deployed parser |
| [Kellogg convergence record](https://app.notion.com/p/c1df99715bbd4d569c77a6bac0540507) | Merged historical PR #55 in an **inaccessible old private repository**; describes TT/MPS/MPO, not a downloadable source archive in this page |
| [Kellogg DφT stack](https://app.notion.com/p/1a8545c483b04fb5ae3d21fe8bb3d39a) | Merged historical PR #59; **cannot** infer source-code availability from its PR summary |

The stable file-block references were resolved through the authenticated Notion
attachment resolver for three sample files. Expiring signed URLs are **not**
recorded in the repository. We have **not** proved byte identity between the
Notion-hosted ZIPs and the user-uploaded ZIPs merely because filenames match.

## Recovered actual source and code changes

### 1. PULVINI tensor-train source — recovered and elevated

Source archive: `pulvini_v3_enterprise_production_20260724(1).zip`.

Original file:
`pulvini_v3/src/euclid/pythagoras/quantum/operators/tensor_train.py`,
SHA-256 `1ff3bd42c4fd33c509e2f86c9360cd55801b2b5b7c708a89f1ef1b5e92edade9`.

**Confirmed defect:** archived `TensorTrain._decompose()` calls
`astype(float)` on a numerical tensor. With complex-valued input
`[[1+2j,2-1j],[3+4j,4+1j]]`, the reconstructed tensor has **no imaginary
components**; the maximum absolute error is 4.0. This is a real archive
reproduction, **not** a defect proven in the present active TT/MPS engines.

**Wired replacement:** `src/chronus/tensor/exact_rational_tt.py` implements
the archived tensor-train *contract* as a bounded, independent and
mathematically exact `Q`-valued factorisation, without SVD truncation,
implicit float conversion, or promoted hardware claims:

- Core geometry: `(r_previous, n_site, r_next)`.
- Exact rank factorisation by rational rank-one elimination, including zero
  tensors; bit-exact reconstruction for integer and rational inputs.
- Explicit maximum 8 sites / 1,024 entries; refuses floats, complex values,
  malformed shapes, excessive dimensions and altered state digest.
- Canonical JSON digest of the exact core data, stored with the resulting
  `ExactRationalTensorTrain`, independently rechecked by `verify()`.
- **Wired into** the current, already-canonical `chronus.tensor` package
  exports; **no second tensor runtime**, no dishonest compressed-storage claim.
- `tests/test_exact_rational_tt_recovery.py` records shape/zero/rational/
  rejection/tamper/digest tests. Local isolated source fixture: **6 passed**.
  The new GitHub-head test itself has **not yet executed in repository CI**.

This is a new exact reference capability, **not a verbatim copy** of the
historical numerical/complex TT-SVD, not an automatic migration of arbitrary
historic pickle/checkpoints, and not hardware-proved.

### 2. Chronos ONE iGPU v3.10 tensor-runtime safety — recovered and wired

From the ChatGPT Library archive
`chronos-one-igpu-v3.10-resident-projection-elevation.zip`:
`chronos-one-igpu-v3.10/src/chronos/igpu/tensor_runtime.py` (SHA-256
`768d9cef438af868929163216a18a35518535790afb44d3109387dffcc38a92a`).

The bounds and finite-data checks were more explicit than the retained
`PhiTensorCore` in current Chronus. They are now **applied to the existing**
`src/chronus/tensor/geodesic.py::PhiTensorCore.execute` reference path:
finite numeric dtype/input, one-million-element input and result budgets,
preallocation checks for Kronecker and matrix products, finite scale and
output checks. Preserves complex-number reference matmul. Tests appended to
`tests/test_geodesic_tensor_migration.py`. This is **software capacity
protection**, not measured physical memory or GPU execution.

### 3. Archived 1,000-qubit machine — verified lineage, not duplicated

The supplied `HYBA_1000_QUBIT_VQC_20260724(3).zip` contains
`phi_quantum_machine.py`, `vqc_phi_grover.py` and original tests.
The missing PULVINI `formal.py` import was filled **only in a temporary
isolated test tree** using the user-supplied enterprise archive. The two
original suites then executed **22/22 passing**. These test results are
software-only and do not establish universal 1,000-qubit computation,
cryptographic search advantage or any physical QPU.

Current `packages/turing/src/turing/algorithms/clifford.py` already contains
the independent, exact bit-packed Aaronson–Gottesman stabilizer tableau, and
`packages/turing/tests/test_turing_clifford.py` already tests GHZ at
**1,000 and 2,500 logical qubits**. Replacing it with the older NumPy tableau
would regress the canonical mathematical implementation. No duplicate
stabilizer was introduced.

### 4. Chronos ONE iGPU v3.4 — verified but separate graphics lineage

Actual user ZIP includes `chronos-completed/src/chronos/qsdl_parser.py`
(SHA-256 `86dd6f29da513e23d0ce32ba0b8a122b05adae5cdd45ded0cad20f09e8bba585`)
and a compiler, manifold/graphics engine, Lucas runtime, PRIME-DB and tests.

A scoped local archive run of `test_one_igpu.py`,
`test_lucas_engine.py` and `test_lucas_runtime.py` passed **10/10**.
It is a historical Chronos graphics lineage, not evidence that the
present Chronus execution plane implements the full QSDL compiler.
**QSDL grammar/compiler integration remains NOT PORTED.** Deliberately do not
install a second GPU controller or relabel archived rendering claims as
physical runtime evidence.

### 5. Supplementary October QC

`private-supplementary-qc-evidence.zip` and
`HYBA-recovery-evidence-20261029.zip` include source/integrity checks,
separate historical recovery reports and deliberately unqualified findings.
Their older descriptions sometimes invert custody authority (OVID/THESEUS)
or refer to no-longer-canonical repositories. The governing October 5
[Architecture Authority Register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19)
and current Chronus source determine ownership.

## Executed evidence, limited to isolated archive source

| Executed scope | Outcome | What it proves |
| --- | --- | --- |
| v3.4 original Chronos iGPU/Lucas test modules | **10 passed** | Older local software source works on this Python runtime |
| Original VQC test modules + PULVINI formal import closure | **22 passed** | Bounded old Clifford/VQC reference checks |
| Bounded exact rational TT recovery module | **6 passed** | Isolated new exact tensor math and corruption negatives |
| New repo tests and full Chronus package graph | **NOT EXECUTED** | Needs exact-commit CI runner execution |
| Live mining, real accelerator, live deployment, HPC/8K, cost claims | **UNAVAILABLE** | No measurements or accepted-share records in this exercise |

Recorded local logs:
- historical Chronos test stdout SHA-256:
  `d96a858f3def7cc4d98f2039cbff441c94155cb2b2f70e25f34e8ef797477799`.
- historical VQC test stdout SHA-256:
  `dc73640ef02afbd8d65d8db048f6b373b2cf15a7b92f5d501ac92bb60870faba`.

All seven newly supplied ZIPs were checked for ZIP integrity, unexpected
traversal paths and source hashes. The full manifest is
`evidence/migration/2026-11-16-notion-library-artifact-register.json`.
No source ZIP was silently treated as deployed code. Unavailable files remain
unavailable until their exact bytes are recovered and checked.

## Release and remaining integration boundary

**NOT QUALIFIED.** Code source is committed in a review branch. New
current-head tests and complete CI/build/static-security review are still
required, along with owner approval and real runtime evidence.

**Open source gap:** the full QSDL parser/compiler+rendering dependency graph
from the Chronos archives is not currently wired into Chronus; this recovery
branch does not falsely declare it integrated. The historical Kellogg
implementation, Notion-only EUCLID posterity binaries and commercial DATA
archive attachments have not all been materialized or independently checked.
They require exact-source comparison and bounded ports rather than duplicate
engines.
