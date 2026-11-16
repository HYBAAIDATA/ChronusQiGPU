# Evidence-first CI gates: wording, test reality, quantum naming

These checks complement `scripts/ci/purity_gate.py` and the existing claim-token audit. They flag claims or language requiring review; **they do not prove or disprove mathematical or physical semantics**. The historical quantum namespace must not silently acquire the status of TURING.

## Commands and machine-readable evidence

```sh
python scripts/ci/no_dressing.py --json > dressing-findings.json
python scripts/ci/test_reality.py --json > test-reality.json
python scripts/ci/quantum_naming.py
python -m pytest -q tests/test_dressing_gates.py
```

All three gates exit 0 when clean, 2 on findings, and 1 on configuration or scanning errors. JSON modes write machine-readable data to stdout; totals go to stderr. CI uploads both JSON outputs even when a gate fails. A failed gate cannot be represented as production qualification.

## Vocabulary and exact-path scope

The versioned policy is `scripts/ci/dressing_policy.json`. It checks scoped source and documentation for approximate language, synthetic/model words, unsupported computational claims and floating-point or tolerance terminology in claimed exact paths. A match is **a review trigger**, not conclusive proof. It may legitimately describe a limitation, a rejected approach, a boundary conversion, or a negative claim.

The allowlist supports path globs plus exact case-insensitive words. Every exception must include a concrete reason and named reviewer; `reviewer: pending` has **no effect**. Do not use directory-wide exceptions merely to silence the first run. Check findings, retain raw path/line/word evidence, and record an explicit reviewer for any narrowly justified exception. The supplied entries are requests for review, not approvals.

## What real and simulated mean

`scripts/ci/test_reality.py` inventories every `tests/**/test_*.py` file. Exactly one **module-level** declaration is required:

```python
pytestmark = pytest.mark.real
# or
pytestmark = pytest.mark.simulated
```

- **real**: exercises production implementation without mocked behaviour in that test; it is **not** an assertion of hardware, live pool, deployment or independent validation.
- **simulated**: depends on mocks, synthetic pool, fake clock or controlled fixture/harness. These tests remain useful but are not promoted into runtime evidence.
- A line-level `# mock-ok: specific reason` is counted as a documented exception, not silently ignored. Prefer simulated if the behaviour under test is mocked.

Reports count source-level test functions and files. Parametrization, collection skips, unittest marker semantics, actual execution and live system observations are **not** established by this static inventory. Generated input vectors that exercise genuine production paths without mocks can be real after review.

The first rollout may have substantial failures. Unclassified files remain unclassified until inspected; do not mass-apply the real label. Keep the PR unmerged until findings are triaged and CI is green.

## Legacy quantum namespace

`scripts/ci/quantum_naming_policy.json` inventories every Python module under `src/chronus/quantum` as a finite-field/algebraic model or historical namespace. An added module must be classified. The legacy `QuantumStateEngine` alias must still resolve to the classical `PredictiveEngine` unless an implementation and migration are explicitly reviewed. The existing taxonomy documentation must retain its boundary between algebraic models and TURING.

No name, token, statevector demonstration or test count establishes device execution, physical measurement, computational advantage, live performance, or production status. Such claims need independent, reproducible runtime or experimental evidence tied to the exact reviewed code.
