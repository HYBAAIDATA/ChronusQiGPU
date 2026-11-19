# Fleet-scale admission hardening

The existing 200,000-entry replay cache retains request nonces for 600 seconds. At one heartbeat per second and one idle lease poll per 150 ms, 125 workers alone require at least 575,000 entries per retention window before results, clients or retries. This is arithmetic, not a load test. Saturation refuses authenticated requests, as it must; eviction is not a valid fix.

The coordinator now calculates a conservative idle-request planning floor from the expected worker count, heartbeat and poll intervals, reserving twice the calculated number of nonces, including a boundary allowance. The operator may set a larger explicit budget. Example: `chronus-fleet coordinator --expected-workers 125 --max-connections 256` produces a 1,150,500-entry planning budget at default intervals. Memory and throughput must be measured; neither the budget nor the worker count establishes GPU capacity. JSON status exposes replay occupancy, capacity rejections and configured connection budget. Initial heartbeat phase is distributed by node identity; idle polls add at most 25% delay to avoid lockstep requests. This bounds idle polling delay, not end-to-end dispatch latency.

The existing AL HARAS local ledger now refuses a stale writer under the OS file lock rather than appending a duplicate sequence to a changed journal. This is a local safety guard, not distributed consensus or a THESEUS lease fence. Distributed custody remains a separate authority and integration obligation (#187).

## Evidence boundary

No physical benchmark, native node daemon, network transport migration or distributed fleet qualification is implied. The new tests exercise actual local files and HTTP and exact planning arithmetic; physical hardware and multi-node measurements remain unavailable until independently executed. No qualification gates or mining algorithms are changed.
