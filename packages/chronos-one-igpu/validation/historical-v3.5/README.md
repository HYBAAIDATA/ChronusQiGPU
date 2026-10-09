# Executed validation — 7 October 2026

- Unchanged attachment: 40 passed, 0 failed. See original-tests.txt and original-junit.xml.
- Final integrated tree: 125 passed, 0 failed, 0 errors. See full-tests.txt/full-junit.xml.
- Added integration suite: 85 passed. It includes real NIST SHA256 vectors and Bitcoin genesis-header proof, plus generated mathematical/adversarial fixtures. The historical Notion 121-test suite is not part of this release.
- Isolated installed-wheel import, API checks, and packaged Notion manifest/plan: passed.
- Network-free genesis demo, host recheck, restart checkpoint restore, evidence replay: passed.
- Python compileall for source, tests, examples: passed.
- Native C/Rust compilation, CI, physical OpenCL/Intel execution, energy measurements, distributed workers, live Stratum and pool acknowledgement: not executed/not claimed.
- This does not establish algorithmic advantage.

Test and wheel provenance is in summary.json; environment and exact tested dependency versions are retained. The baseline and final runs used different BLAS thread settings: their runtimes are not a controlled performance comparison.
