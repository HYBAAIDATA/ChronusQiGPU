# Cyclotomic input and projection: isolated local evidence

Status: WIP, not qualified for release. Source export from main commit `8fddfd17eb776a95e0eec1d1514dd48290c905b4`; original source Git blob `bb13891ab2b1d355ec40c8f72b40eab4e6f95d3f` verified from export bytes. This was not a full repository checkout. Tests load the changed module in isolation. Integration compatibility and complete repository tests were not run.

Change: reject non-integer Cyclotomic5 coefficients; reject projection outside Z[phi] instead of silently discarding coefficients. This changes behavior for unsupported inputs and requires integration review. The ring identities and braid relation are only tested in the stated cases, not proven in general. Seeded random tests are not Hypothesis tests and are not proof.

Command: `python -m unittest discover -s tests -p 'test_cyclotomic_projection_review.py' -v` in the partial source export. Runtime: Python 3.13.15.

```text
test_braid_relation (test_cyclotomic_projection_review.RingRegressions.test_braid_relation) ... ok
test_invalid_coefficients (test_cyclotomic_projection_review.RingRegressions.test_invalid_coefficients) ... ok
test_nonreal_projection_refused (test_cyclotomic_projection_review.RingRegressions.test_nonreal_projection_refused) ... ok
test_projection_examples (test_cyclotomic_projection_review.RingRegressions.test_projection_examples) ... ok
test_projection_preserves_operations_on_quadratic_subring (test_cyclotomic_projection_review.RingRegressions.test_projection_preserves_operations_on_quadratic_subring) ... ok
test_root_and_phi_identities (test_cyclotomic_projection_review.RingRegressions.test_root_and_phi_identities) ... ok
test_seeded_sample_ring_associativity (test_cyclotomic_projection_review.RingRegressions.test_seeded_sample_ring_associativity) ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.063s

OK
```

SHA-256 of exact file bytes:

- `src/chronus/quantum/geometric_polychoron.py`: `b780b57d4f83627199f3e31852212af7359f0e949f72e9ed52e4030389699e13`
- `tests/test_cyclotomic_projection_review.py`: `ef8f903c15e951e30a92a3c96113987c5173df2bc1acea07997d153f981c1ef9`

These seven test functions are not the seven required test classes. No coverage measurement, CI run, signature, hardware timing, pentagon or F/R matrix qualification, tensor or storage measurement, customer evidence, or release qualification is asserted. Verify the artifact introduction commit with `git log --diff-filter=A -- evidence/cyclotomic/isolation-review.md` (a commit cannot contain its own SHA). Verify checksums with `sha256sum` from a checkout of that commit.
