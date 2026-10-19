# Public API nonces

Source: `https://blockstream.info/api/blocks/{height}`.
Requested heights 800000 through 809999. The API returned 1640 blocks and then HTTP 429.
The nonce in each header is the `nonce` field from that response. No other nonce was generated.

| heights | blocks | bits | difficulty |
|---|---|---|---|
| 805000-805009 | 10 | 386207611 | 55621444139429.57 |
| 808370-808415 | 46 | 386216622 | 54150142369480.0 |
| 808416-809999 | 1584 | 386198911 | 57119871304635.31 |

Not returned: 800000-804999 and 805010-808369.

| check | result |
|---|---|
| sha256d(header) <= target(bits) | 1640 / 1640 |
| previous-hash link inside each stored span | 0 breaks |
| nonce replaced by 0 still meets target | 0 / 1640 |
| nonce at height 805000 | 2431510578 |

808416 = 2016 × 401, so the bits change there is the retarget boundary.
Height 805000 sits in the epoch that starts at 804384 = 2016 × 399. Its difficulty is 55621444139429.57. The work per block at that difficulty is that many times 2^32 hashes. The nonce that met the target is the one stored with the header.

The traversal tables under `reports/traversal_*.md` measure address steps. They were not used to choose any nonce in this check.
