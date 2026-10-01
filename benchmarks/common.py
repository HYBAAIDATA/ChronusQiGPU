"""Shared harness for the PYTHIA measurement suite.

Every benchmark declares a seed, a dataset, and an environment fingerprint.
The winner model used by the large-N arms is the uniform random-oracle
model: sha256d is memoryless, so the set of nonces whose digest is below a
fixed target is a uniformly random subset of the nonce window. The model is
exact under that assumption — and each benchmark that uses it also runs a
real-hash arm where winners are derived by physically hashing the window,
so the assumption is measured, not merely asserted.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import struct
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
DATA = REPORTS / "data"

for _extra in (
    str(ROOT),
    str(ROOT / "turing_universal_quantum_computer"),
    str(ROOT / "chronus/mla1517_platform" / "python"),
):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

SEED = 0x50595448  # "PYTH" — every trial derives from this declared seed


def sha256d(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def env_fingerprint() -> dict:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        head = "unknown"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "git_head": head,
    }


def rng_for(tag: str, trial: int) -> random.Random:
    """Deterministic per-trial RNG: seed = sha256(SEED|tag|trial)."""
    key = f"{SEED}:{tag}:{trial}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))


def quantile(data: Sequence[float], q: float) -> float:
    if not data:
        return float("nan")
    xs = sorted(data)
    idx = min(len(xs) - 1, max(0, int(math.ceil(q * len(xs)) - 1)))
    return float(xs[idx])


def bootstrap_ci(
    data: Sequence[float], tag: str, resamples: int = 2000
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for the mean, seeded by tag."""
    if not data:
        return (float("nan"), float("nan"))
    rng = rng_for("bootstrap", int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16))
    n = len(data)
    means = sorted(
        statistics.fmean(rng.choice(data) for _ in range(n)) for _ in range(resamples)
    )
    return (float(means[int(0.025 * resamples)]), float(means[int(0.975 * resamples)]))


def summarize(values: Sequence[float], tag: str) -> dict:
    if not values:
        return {"n": 0}
    lo, hi = bootstrap_ci(list(values), tag)
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": quantile(list(values), 0.5),
        "p95": quantile(list(values), 0.95),
        "ci95": [lo, hi],
        "min": min(values),
        "max": max(values),
    }


def loglog_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Least-squares slope on log2 axes — the empirical scaling exponent."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
    if len(pairs) < 2:
        return float("nan")
    lx = [math.log2(x) for x, _ in pairs]
    ly = [math.log2(y) for _, y in pairs]
    mx, my = statistics.fmean(lx), statistics.fmean(ly)
    num = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    den = sum((a - mx) ** 2 for a in lx)
    return num / den if den else float("nan")


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth Poisson sampler for small lam."""
    bound = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= bound:
            return k
        k += 1


def uniform_winners(rng: random.Random, lam: float, space: int) -> List[int]:
    """Random-oracle winner set: Poisson(lam) uniform positions in space."""
    k = poisson(rng, lam)
    return [rng.randrange(space) for _ in range(k)]


def synthetic_header(height: int) -> bytes:
    """One deterministic 80-byte stand-in header for the pinned corpus.

    The repo vendors no real Bitcoin header set; the corpus is a declared
    synthetic stand-in for heights 800,000+i whose digest is published in
    each report. Field layout matches the consensus header layout.
    """
    version = 0x20000000
    prev = sha256d(f"pythia-corpus-prev-{height}".encode())
    merkle = sha256d(f"pythia-corpus-merkle-{height}".encode())
    timestamp = 1_700_000_000 + (height - 800_000) * 600
    bits = 0x1D00FFFF
    return (
        struct.pack("<I", version)
        + prev
        + merkle
        + struct.pack("<III", timestamp, bits, 0)
    )


def corpus_heights() -> range:
    return range(800_000, 810_000)


def corpus_digest(heights: Iterable[int]) -> str:
    h = hashlib.sha256()
    for height in heights:
        h.update(synthetic_header(height))
    return h.hexdigest()


def real_winners(header: bytes, target_int: int, base: int, count: int) -> List[int]:
    """Physically hash the window; return every nonce with digest <= target.

    Midstate acceleration: the first SHA-256 pass over the constant 64-byte
    header prefix is cloned, not recomputed — identical digests, fewer
    compressions per nonce. Comparison is little-endian (consensus digest
    byte order).
    """
    prefix = hashlib.sha256(header[:64])
    tail = header[64:76]
    out = []
    pack = struct.Struct("<I").pack
    for i in range(count):
        nonce = (base + i) & 0xFFFFFFFF
        first = prefix.copy()
        first.update(tail + pack(nonce))
        if int.from_bytes(hashlib.sha256(first.digest()).digest(), "little") <= target_int:
            out.append(nonce)
    return out


def write_report(name: str, results: dict, body: str) -> Path:
    REPORTS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    (DATA / f"{name}.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    path = REPORTS / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


def fmt(x: float, digits: int = 3) -> str:
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    return f"{x:,.{digits}f}"
