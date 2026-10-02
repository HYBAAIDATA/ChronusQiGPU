# Hardware evidence artifacts

Do not commit fabricated or nameplate values. Generate a mining artifact only
from a real `HybridCoordinator` job result containing per-device measured
samples:

```bash
python bench/hardware_evidence.py job-result.json bench/results/hardware-measured.json
```

The validator refuses reports without executed protocol hashes, a measured wall
window, and per-device samples. The committed JSON must name the target host,
device identities, commit SHA, command, and attached CI run in its surrounding
release record. Tensor operations remain separate from H/s.

For a Chronus Intel iGPU, generate the tensor/stress/sensor/topology artifact on
the physical target host:

```bash
python3 -m bench.chronus_igpu_evidence \
  --size 512 --iterations 20 --stress-seconds 300 \
  --sha256d-count 1048576
```

The resulting `igpu_<device>_<UTC timestamp>.json` is accepted only when every
tensor sample records physical Chronus execution, passes the CPU reference, has
a non-zero observation window, and matches its content hash. Missing power,
temperature, peer-access, roofline peaks, or pool acknowledgement remain
`Unavailable`. Do not hand-author evidence JSON.