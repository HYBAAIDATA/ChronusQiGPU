# Integer ring: seven-class isolated test evidence

Source snapshot `ddc8eb08766381b9b319952294b34461b14b16d3`, `src/chronus/quantum/geometric_polychoron.py`, verified Git blob `c64f68f59cc6cea5217ac1f060674995910bc3d5`. The test dynamically loads that exact file from a partial export, not a full checkout. No source modification is included in this commit.

Run on Python 3.13.15, pytest 9.2.0, Hypothesis 6.170.15 and coverage.py 7.17.2:

```sh
python -m coverage run --branch --include='*/geometric_polychoron.py' -m pytest -v tests/test_cyclotomic_seven_classes.py
python -m coverage report -m --fail-under=90
python -m coverage json -o evidence/acceleration/ring-coverage.json
sha256sum -c evidence/acceleration/ring-SHA256SUMS
```

[Log](ring-tests.txt): ten tests in seven classes passed; [full source-file branch coverage](ring-coverage.json) is 100% (233 statements, 66 branch opportunities). This does not establish a universal proof, security assurance, customer journey, repository integration, or release qualification. Generated tests are deterministic; no counterexample or shrinking log was generated. The bounded exhaustive test covers coefficients -1 through 1 for pairwise commutativity and identities, not every execution. Property tests generate 300 triples for ring identities and 100 quadratic-subring projections. The integration and end-to-end tests are mathematical operations in a partial export, not customer-level journeys. Integers are unbounded in language semantics but execution resources are finite; powers tested for phi were n=0 through 100 and 2048-bit coefficients were tested separately. Coverage is not a substitute for correctness.

The existing module also contains geometric, field and braid code. The tests exercise their current public paths to measure the entire file, but do not establish the fidelity of every scientific claim in that file. An Artin matrix check is included; a specified F-matrix, R-matrix and pentagon identity are not established by these tests. The user-requested element/vector interface is not implemented here. The ring module is therefore tested but the full step remains incomplete.
