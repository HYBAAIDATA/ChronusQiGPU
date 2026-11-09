# Bounded exact ring codec

The `RC01` format encodes each byte by multiplying its scalar ring element by phi, storing the four signed 16-bit coefficients, then verifies the inverse and SHA-256 on decode. It accepts at most 4096 bytes. It is reversible for the bounded format; it expands every nonempty input (`44 + 8n` bytes). An unkeyed digest is not authentication or protection against deliberate tampering. This is a codec experiment, not a durable page store or a compression claim.

[Seven-class test output](ring-codec-tests.txt): eight cases passed in a partial source export; [branch-inclusive coverage](ring-codec-coverage.json) is 100% for this module. End-to-end is a temporary-file round trip, not a deployed service or recovery from failure. The AST purity check covers numeric literals in this module, not transitive dependencies. See [hash manifest](ring-codec-SHA256SUMS).

## Sample and measurement

The selected data system is a database-page-like sample: one deterministic synthetic 4096-byte page containing 64 fixed-width textual records; it is not a database-produced page or customer data. The [data artifact](../../artifacts/acceleration/data_system_e68323c90f115bbc86c8ec676e694fb9075cfea1c9531ae5736e64a8fea548be.json) records the full method, digest, raw latency samples and counts. It measured 4096 original bytes and 32812 encoded bytes, ratio 0.1248323784 (input/encoded), and exact round-trip. The same input compressed with zlib to 431 bytes in this one sample. This is not a comparison to a configured production page store. The next separately named candidate is an approved representative binary database-page dataset; this result remains unchanged.

The artifact gives decode p50/p95/p99 and clean file reopen plus decode time. The reported write amplification is logical encoded bytes written divided by input bytes, not physical write amplification. Crash/corruption recovery is not implemented or measured: clean reopen is not failure recovery. No durability, customer capacity, security or release claim is made.

```sh
PYTHONPATH=src python -m coverage run --branch --include='*/ring_codec.py' -m pytest -v tests/test_ring_codec_seven_classes.py
python -m coverage report -m --fail-under=90
python -m coverage json -o evidence/acceleration/ring-codec-coverage.json
PYTHONPATH=src python benchmarks/acceleration/ring_codec_benchmark.py > /tmp/ring_codec_raw.json
sha256sum -c evidence/acceleration/ring-codec-SHA256SUMS
```

Timing changes make a rerun's JSON digest different; the input digest and deterministic byte counts should match. No full checkout or CI execution is represented.
