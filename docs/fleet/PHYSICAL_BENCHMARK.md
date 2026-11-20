# Physical fleet candidate collection

`benchmarks/physical_fleet.py` submits an operator-supplied binary workload, uses
an explicit physical route (no auto/CPU fallback), authenticates the remote
coordinator over HTTPS, pins the independently supplied ML-DSA-65 public key,
checks the exact repeated output and retains raw signed receipts and their hashes.
Run in a clean candidate checkout; use a result directory outside that checkout.

```sh
python benchmarks/physical_fleet.py --coordinator https://coordinator.example:8740 \
  --token-file /secure/fleet-token --tls-ca /secure/ca.pem \
  --public-key-file /secure/pinned-public-key.hex --input /workloads/input.bin \
  --kernel m15_fold --route opencl --expected-workers 8 --iterations 1000 \
  --out /secure/evidence/candidate-eight-workers
```

The process exits nonzero on incomplete collection, verification failure or
insufficient worker participation. Percentiles are nearest-rank over measured
client end-to-end and local receipt-verification times; p99.9 is unavailable below
1,000 samples. These do not measure per-kernel utilization, network dispatch
alone, distributed custody or physical GPU identity. The client commit is read
from Git; a remote commit is not inferred. Worker IDs are worker reports, not
physical inventory. A successful collector run is not qualification.

Physical qualification additionally requires operator-attested unique hardware
IDs and remote source commit on every host, driver/kernel telemetry, a verified
coordinator ledger and THESEUS distributed anchors, independently witnessed
fault injection (10% of workers at each scale point), accounting for every
accepted work/receipt and recovery latency. Repeat at 8, 64 and 1,000 physical
GPUs. No such deployment or measurement is supplied by this change.
