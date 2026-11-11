# TURING source snapshots archived on 2026-11-11

* `exact_primitive_library-v3.py` is the single-file exact cyclotomic library from
  which the TURING exact layer was built. Its file name contains a hyphen, so it
  could not be imported as a module. The maintained implementation is
  `turing.exact` (packages/turing/src/turing/exact), tested by tests/test_turing.py.
* `qudit_qec.py` is a demonstration script for the exact qudit stabilizer tableau.
  It imports a module named `exact_primitive_library_v3`, which does not exist in
  this repository, so it did not run as committed. The tableau it exercises is
  `turing.exact.StabilizerTableauZetaP`.

Both files are unchanged. Use `git log --follow <path>` for their history.
