import time
import os
import random
import numpy as np

# We want to benchmark: sha256d(header) + int.from_bytes + compare
from chronus.stratum.endian_engine import sha256d

# 1. Build 1000 random valid 80-byte headers
headers = [os.urandom(80) for _ in range(1000)]
target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000

# 2. Warm up
for i in range(1000):
    raw = sha256d(headers[i % 1000])
    h_int = int.from_bytes(raw, "little")
    _ = (h_int <= target)

# 3. Time sha256d(header) + int.from_bytes + compare, 10,000 iterations
times_us = []
for i in range(10000):
    hdr = headers[i % 1000]
    t0 = time.perf_counter_ns()
    raw = sha256d(hdr)
    h_int = int.from_bytes(raw, "little")
    valid = (h_int <= target)
    t1 = time.perf_counter_ns()
    times_us.append((t1 - t0) / 1000.0)

times_arr = np.array(times_us)
p50 = float(np.percentile(times_arr, 50))
p90 = float(np.percentile(times_arr, 90))
p99 = float(np.percentile(times_arr, 99))
max_val = float(np.max(times_arr))

print(f"p50:  {p50:.4f} us")
print(f"p90:  {p90:.4f} us")
print(f"p99:  {p99:.4f} us")
print(f"max:  {max_val:.4f} us")
