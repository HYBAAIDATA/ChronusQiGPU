# Zeckendorf reference accumulation: bounded software measurement

The same sequence starts at 2^53 and adds integer 1 ten thousand times. Existing `src/chronus/hw/zeckendorf.py` `add` yields `9007199254750992`, equal to the integer oracle; binary64 repeated addition yields `9007199254740992`, an error of `-10000`. This deliberately selects a binary64 precision boundary; it is not a general error characterization. `1208925819614629174706176` was rejected with `ValueError`, as recorded in the JSON.

Single local run: software reference 97521.2 additions/s (102541808 ns); Python float baseline 32828108.7 additions/s (304617 ns). Timings include interpreter and representation overhead; this run does **not** show a throughput benefit, physical hardware timing, or removal of a real hardware bottleneck. The reference uses integer Fibonacci representations, not the cyclotomic ring. The requested ring-backed ALU integration and seven-class qualification remain blocked/unimplemented.

Source commit `7d31a98bde6670061a5a3d7161f0affed6c238c7`, source blob `1687afd68d841bb9ededc675d4fb6e5afd63e6fe` checked from GitHub MCP text before execution. No full checkout was used. Checkout command (benchmark is committed after that source commit; checkout must contain both versions):

```sh
python tools/measure_zeckendorf_accumulation.py --source-commit 7d31a98bde6670061a5a3d7161f0affed6c238c7 --source-blob 1687afd68d841bb9ededc675d4fb6e5afd63e6fe --output /tmp/zeckendorf-accumulation.json
```

Local execution used the same arguments plus `--mcp-source-json` with the source tool-result file. It checked the Git blob before executing the original source in memory. Timing varies by run.

SHA-256:

- `tools/measure_zeckendorf_accumulation.py`: `8ee2ea650e97ac8e35944e3869aed82ea2fd11fe924756593083043cb71edf19`
- `evidence/cyclotomic/zeckendorf-accumulation.json`: `4f078e73ae868318a2f6a5f5ce30510c02641aa88dc715ee4430bde1e12752f8`
- `evidence/cyclotomic/zeckendorf-accumulation-output.txt`: `dcfd723a9505a7fcf3cffad372d799accd2f1395e3733e2ecef90c2c3a55fda1`

Find artifact-introduction SHA with `git log --diff-filter=A -- evidence/cyclotomic/zeckendorf-accumulation.json`.
