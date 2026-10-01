# Hardware evidence artifacts

Do not commit fabricated or nameplate values. Generate an artifact only from a
real `HybridCoordinator` job result containing per-device measured samples:

```bash
python bench/hardware_evidence.py job-result.json bench/results/hardware-measured.json
```

The validator refuses reports without executed protocol hashes, a measured wall
window, and per-device samples. The committed JSON must name the target host,
device identities, commit SHA, command, and attached CI run in its surrounding
release record. Tensor operations remain separate from H/s.
