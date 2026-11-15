# Exact MPS contraction: isolated prototype evidence

Experimental bounded unnormalised MPS expansion using the existing Cyclotomic5 class; it is not a physical quantum simulator, production system, or evidence of a performance benefit. Reference background: Pérez-García et al., "Matrix product states and projected entangled pair states: Concepts, symmetries, theorems", Reviews of Modern Physics 93, 045003 (2021), https://doi.org/10.1103/RevModPhys.93.045003. A concrete input and comparison with the existing baseline are separate tasks. No approximate arithmetic is used in this contraction. Output length can grow exponentially; code limits site count and output dimension, but does not yet bound bond sizes, coefficient magnitude or total work.

The local test ran against a partial source export, with the ring module Git blob `c64f68f59cc6cea5217ac1f060674995910bc3d5` checked and loaded in memory. Seven functions passed; full statement coverage of the new module was 38/39 (97%, coverage.py 7.17.2). Tests exercise invariant, Hypothesis-generated property, oversized-output rejection, edge, unit, braid interaction and a small mathematical end-to-end workflow. These labels are not certification of the seven required release classes: no complete customer sign-in-to-settlement journey, threat-class security qualification, full-tree integration or independent oracle is established. Tests do not prove properties for all inputs.

Local execution: `PYTHONPATH=/data/chronus-deps python -m coverage run --include='/data/chronus-resume/src/chronus/tensor/exact_mps.py' tools/local_injected_test_runner.py` followed by `PYTHONPATH=/data/chronus-deps python -m coverage report -m --fail-under=90`. The bootstrap injected the verified prior source export; it is not committed. For a full checkout, use `python -m coverage run --include='*/chronus/tensor/exact_mps.py' -m unittest discover -s tests -p 'test_exact_mps_reference.py' -v` and `python -m coverage report -m --fail-under=90`, with Hypothesis installed. This checkout reproduction has not been run here.

SHA-256 of files:

- `src/chronus/tensor/exact_mps.py`: `7a676fd0f38eea0413febfe38f756fd1d54c68110259b58dd0a8cd2eebe840a0`
- `tests/test_exact_mps_reference.py`: `8c3f5478105d40945c334520f8c5dc774f3976ed0788e799a677a9b91eb83834`
- `evidence/cyclotomic/exact-mps-tests.txt`: `7470ceb546f69e61f37f6a577d7dbc21a591a3fe1e6f1d6882a503915147d7f8`

To determine the artifact-introduction commit: `git log --diff-filter=A -- evidence/cyclotomic/exact-mps-tests.txt`. Timing, drift, ring-vs-baseline comparison, coverage of dependent modules, signature and CI remain unverified.
