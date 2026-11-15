# Exact coordinate operations

`chronus.quantum.ring_state.scale_element` multiplies two `Cyclotomic5` elements; `scale_vector` applies the same multiplication independently to 1–256 explicit coordinates. This is algebraic coefficient manipulation, not a normalized quantum-state or measurement model. It makes no performance or customer-value claim.

[Tests](ring-state-tests.txt): eight cases in seven classes passed in a partial source export. [Branch-inclusive coverage](ring-state-coverage.json): 100% for this module. Tests include bounded exhaustive scalar/vector agreement, generated linearity and composition, invalid input checks, and integration with the existing projection. The purity check detects floating-point or complex literals in this module, not all possible impurities in the transitive path. End-to-end means this API's mathematical use, not a customer journey; tests are not universal proofs.

```sh
PYTHONPATH=src python -m coverage run --branch --include='*/ring_state.py' -m pytest -v tests/test_ring_state_seven_classes.py
python -m coverage report -m --fail-under=90
python -m coverage json -o evidence/acceleration/ring-state-coverage.json
PYTHONPATH=src python benchmarks/acceleration/ring_state_benchmark.py > benchmarks/acceleration/ring_state_raw.json
sha256sum -c evidence/acceleration/ring-state-SHA256SUMS
```

[Benchmark](../../benchmarks/acceleration/ring_state_raw.json): seeded explicit scaling at lengths 16 and 128, seven timings per implementation and exact outputs, against an independent polynomial formulation. Only the module validates inputs; both operate on the same valid inputs. Input construction and checking are excluded. Results depend on environment and do not establish general speedup. [SHA-256 manifest](ring-state-SHA256SUMS) covers code, tests and raw evidence. No full checkout or CI execution is represented.
