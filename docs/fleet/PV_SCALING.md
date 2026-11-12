<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:2bcba1c3ddc16d8e96985d8c0c716f238df71c9eb47d7fd4257e52cf1000bd7f -->

# Structural Lucas/PV scaling on the fleet

`PVScale` is the shared structural index. It retains exact nonnegative Python
integers, including 10^12, 10^15, 10^18 and 10^20. `advance(k)` composes by index
addition. `field_factor()` supplies phi^index in F_257[phi], and `field_trace()`
supplies its Lucas trace modulo 257. The golden anchor is m=1.

## Exact domains

The field factor reduces the index modulo the exact period 516 before reading
the readonly table. Its anti-period is 258. Two coefficients per element use
unsigned 16-bit storage because residue 256 needs nine bits. The table payload
is 2064 bytes. The modulo operation still depends on the input integer's size.

The integer lattice `phi_power` uses Fibonacci fast doubling and returns full
integer coefficients. It does not reduce modulo 516. Existing storage,
reference and OpenCL lattice consumers receive this shared arithmetic
improvement. Service limits remain enforced at request boundaries.

## Use the built-in fleet kernel

`pv_field_scale` is registered by default on the coordinator and every worker.
No additional environment configuration is required. Existing domain plugins,
including `hyba_mine.fleet_kernel`, remain independently configurable.
The fleet's existing backend selection, leases, reference verification and
signed receipts apply to the new kernel.

A work unit uses `kernel="pv_field_scale"`, a nonnegative canonical decimal
string `params["scale_index"]`, and little-endian uint16 coefficient pairs.
The wire index is bounded to 4096 decimal digits. The complete index remains
in the work identity and receipt; reduction happens only at the field-factor
boundary. Inputs outside [0,256] or malformed pairs fail before dispatch.

```python
import struct
from chronus.fleet import FleetExecutor, WorkUnit

# Use the existing coordinator URL and local token file for your fleet.
with FleetExecutor(coordinator_url, token_file=token_file, tls_ca=ca_file) as fleet:
    result = fleet.submit(WorkUnit(
        kernel="pv_field_scale",
        params={"scale_index": "100000000000000000000"},
        payload=struct.pack("<4H", 1, 0, 256, 256),
        route="auto", prefer="host",
    ))
    assert result.verified
    pairs = list(struct.iter_unpack("<HH", result.output))
```

The kernel provides reference, Chronus iGPU/NumPy SIMD, OpenCL and Metal
implementations. OpenCL uses the selected fleet GPU for the PV backend as well
as its other work; the program is reused for tiles. MLX and PyObjC Metal use
unsigned integer kernels. CUDA remains unavailable for this kernel until an
actual implementation passes the known answers. A named unavailable route
fails closed; existing auto selection records any fallback.

## Verification and rollout

```bash
python -m pytest -q tests/test_pv_scale_fleet.py tests/test_fleet_adapters.py tests/test_opencl_kernel.py tests/test_scaling_paths.py
python tools/verify_galois_invariant.py --output /tmp/mining-galois-invariant.json
```

Six pinned answers are independently derived by recurrence. Tests cover tiling,
residue 256, SIMD parity and a real embedded coordinator/worker run with a
verified ML-DSA receipt at scale 10^20. OpenCL kernels were compiled and executed
on PoCL CPU. MLX arithmetic was checked using the existing host test stand-in.
Physical GPU and native Metal execution were unavailable in the task sandbox;
run the same known answers and workload measurements on each fleet device
before selecting it for production work.

This implementation accelerates exact scale arithmetic and exposes it to
workload consumers. Mining throughput must be measured end to end, including
search, hashing, transfers, verification and pool replies. Arithmetic timing
alone does not establish a mining speedup or a competitor ranking.


<!-- /coderabbit-ai-generated:v1 -->