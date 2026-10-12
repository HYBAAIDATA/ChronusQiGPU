# Hash usage audit: review before refactoring

Run the standard-library-only inventory from a Git checkout:

```bash
python -m unittest discover -s tests -p test_hash_usage_audit.py -v
python scripts/hash_usage_audit.py --output artifacts/hash-usage-audit.json
```

The manual-only `Advisory hash usage audit` workflow runs the same commands.
It does not install project dependencies, import application code, start mining,
connect to pools/databases, reference environment secrets, or deploy anything.
Existing offline mining gates remain in `pythia-ci.yml`.

The JSON contains only tracked source paths, line numbers and categories, not
source snippets or credential values. Paths themselves may be sensitive: keep
artifacts inside the private repository. Symlinks and binary files are excluded;
untracked files are not scanned. Regex findings include comments and tests and
are not an exhaustive security audit. HMAC presence does not prove safe usage.
Read/decode/Git errors fail the command rather than silently reporting success.

## Bucketing decisions

Fibonacci hashing is not an assignment-preserving replacement for modulo.
Do not change persisted addresses, shards, consensus arithmetic, nonce traversal,
prime-bucket Zeckendorf addressing, or externally visible mappings without a
reviewed migration. No application hashing is changed by this PR.

For an eligible in-memory table of size `2**k`, unsigned 64-bit multiply-and-shift
uses multiplier `0x9E3779B97F4A7C15`. For `1 <= k <= 63`, the index is the high
`k` bits of the product modulo `2**64`. Python needs an explicit 64-bit mask.
For `k == 0`, return zero explicitly: shifting a C/C++ 64-bit operand by 64 is
undefined. Reject unsupported sizes/ranges instead of relying on unchecked shifts.

Test range, determinism, distribution on representative inputs, and table
insert/lookup correctness; do not test equality with old modulo assignments.
Benchmark before claiming speedups: modulo by a constant power of two can already
compile to a bitmask, and Python multiply/mask/shift may be slower.

Non-power-of-two multiply-high range reduction is not perfectly unbiased in
general. Exact uniform sampling needs rejection (and a suitable randomness source).
Neither random sampling nor automatic table resizing is a safe deterministic
storage-address replacement.

## SHA-256 decisions

Preserve Bitcoin double-SHA256, public checksums, content identities and protocol
hashes. A SHA reference alone is not a vulnerability. Replace a confirmed
secret-prefix MAC such as `SHA256(key || message)` with HMAC-SHA256 only after
reviewing format compatibility and key management. Verify with constant-time
comparison and standard test vectors plus tamper/wrong-key cases. Existing signed
formats need migration/versioning; do not silently invalidate stored signatures.

Never put credentials in a commit, report, command-line argument or CI log.
Use the approved secret manager or interactive secret input; this workflow needs
no credentials. Pool worker passwords have service-specific semantics; consult the
provider before treating them as account authentication passwords.

## Review and rollback

Classify each finding by purpose, prioritize confirmed security bugs, and benchmark
only eligible bucketing candidates. No automatic codemod or production-readiness
claim follows from this inventory. Revert the audit commit to remove these tools;
there are no runtime, data-format, secret or deployment changes to roll back.
