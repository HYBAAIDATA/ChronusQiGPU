# Reference codec: synthetic log measurement

This is a measurement of the existing prime codec, not a ring-backed data system or a customer capacity claim. Source was read via GitHub MCP as the exact Git blob `fb514a06f65473526e4ed43a0070e7dafcb1d657` at source commit `16d4e441b4dd7e61abf4f08c2faf430fbef929be`. The benchmark consumes that source in memory from the MCP response; it checks the Git blob before execution. No full checkout was used.

Class: deterministic synthetic HTTP access-log text, 256 generated lines, 20480 bytes, SHA-256 `068f4281c091346b59726ab09a35306001d46080488f24ff6505ffa75fad7369`. No customer data. The encoding does not compress this class: 20480 input bytes / 41005 encoded bytes including header = 0.499451286. Bit-for-bit round-trip passed. Application-level logical write amplification was 2.002197266; this is not physical write amplification. The clean file reopen and decode took 9230869 ns; crash/corruption recovery time and physical write amplification were not measured. Corruption detection is not recovery.

Decode p50/p95/p99: 4682398 / 7906558 / 8746377 ns; 200 individual in-memory decode calls after 10 warmups, nearest-rank percentiles. Environment-specific, not a service latency guarantee. The complete raw samples are in the JSON artifact.

Reproduce from a full checkout of the source commit with:

```sh
python tools/measure_prime_codec_reference.py --source-commit 16d4e441b4dd7e61abf4f08c2faf430fbef929be --codec-blob fb514a06f65473526e4ed43a0070e7dafcb1d657 --repetitions 200 --output /tmp/prime-codec-synthetic-log.json
```

The benchmark is introduced after that source commit; use the introduction commit for the harness and verify the codec blob. Local command included `--mcp-source-json` pointing to the GitHub MCP result, with identical remaining arguments and output under `evidence/cyclotomic/prime-codec-synthetic-log.json`. Timings vary; byte counts and input digest should match. No switch to a different class was made to improve results. Next candidate to evaluate separately: a representative binary database-page dataset, without treating it as a replacement result.

SHA-256 benchmark `83aba043ed7c9ed0615e5fccab4034f1b38981627ed305c234da69c95bfa02b5`; artifact `66217744c41e3f76ad356d6ba11940a086e4a0703589398586fbff1353ba22c4`. The artifact-introduction commit is found via `git log --diff-filter=A -- evidence/cyclotomic/prime-codec-synthetic-log.json`.
