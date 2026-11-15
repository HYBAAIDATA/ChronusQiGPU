# Finding: prime codec on measured data

Source: `src/chronus/storage/prime_codec.py`, Git blob `fb514a06f65473526e4ed43a0070e7dafcb1d657`, measured at source commit `16d4e441b4dd7e61abf4f08c2faf430fbef929be`. `encode` maps each source byte to one two-byte prime word; `decode` reverses that and verifies a 45-byte header with SHA-256. This is a reference codec, not a ring-backed storage implementation.

Only one measured data class was located in the PR evidence: deterministic synthetic HTTP access-log text, 256 lines, 20,480 bytes, input SHA-256 `068f4281c091346b59726ab09a35306001d46080488f24ff6505ffa75fad7369`. The measured payload plus header is 41,005 bytes: input/encoded = `0.49945128642848435` (<1), with bit-for-bit round trip. This codec expands that sample. The format is 2n+45 bytes, so the same expansion follows for all nonempty byte strings, but no additional data-class benchmark is asserted.

Raw samples: [prime-codec-synthetic-log.json](../cyclotomic/prime-codec-synthetic-log.json), SHA-256 `66217744c41e3f76ad356d6ba11940a086e4a0703589398586fbff1353ba22c4`; method and limitations: [measurement note](../cyclotomic/prime-codec-synthetic-log.md). Harness SHA-256 `83aba043ed7c9ed0615e5fccab4034f1b38981627ed305c234da69c95bfa02b5`. Reproduce with the harness from the artifact-introduction revision and verify the source blob:

```sh
python tools/measure_prime_codec_reference.py --source-commit 16d4e441b4dd7e61abf4f08c2faf430fbef929be --codec-blob fb514a06f65473526e4ed43a0070e7dafcb1d657 --repetitions 200 --output /tmp/prime-codec-synthetic-log.json
```

Next separately named candidate: representative binary database pages. It does not replace the log result. No fault-recovery or physical-write measurement is established.
