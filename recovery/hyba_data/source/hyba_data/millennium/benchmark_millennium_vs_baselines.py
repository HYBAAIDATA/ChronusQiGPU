"""
benchmark_millennium_vs_baselines.py

Fair, honest comparison of the phi-folding / Millennium-heuristics
compressor against standard baselines (zlib/gzip always available;
zstandard, brotli, lz4 used if installed) across:

  - synthetic corpora (the same ones already used in
    test_lossless_comprehensive.py, kept for continuity)
  - real-world corpora, if you point --real-data-dir at a folder
    (source code, text, binaries, model weight files, whatever you
    want to actually claim a win on)

For every (corpus, compressor) pair we record:
  - compressed size, ratio, space saved %
  - compress time, decompress time
  - CORRECTNESS: every result is round-tripped and verified byte-exact
    before its ratio is allowed to count. A compressor that corrupts
    data does not get to post a ratio -- it's marked FAIL and excluded
    from the "best" column, exactly like the identity-preserved gate
    should already be doing in millennium_pulvini_integration.py.

Run:
    python benchmark_millennium_vs_baselines.py
    python benchmark_millennium_vs_baselines.py --real-data-dir ./some_folder
    python benchmark_millennium_vs_baselines.py --output results.md
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import pickle
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Optional baselines -- used only if installed, never required.
try:
    import zstandard as _zstd
    HAVE_ZSTD = True
except ImportError:
    HAVE_ZSTD = False

try:
    import brotli as _brotli
    HAVE_BROTLI = True
except ImportError:
    HAVE_BROTLI = False

try:
    import lz4.frame as _lz4
    HAVE_LZ4 = True
except ImportError:
    HAVE_LZ4 = False

# The system under test. Import path assumes this script sits next to
# millennium_pulvini_integration.py (same convention as your other
# debug_*.py scripts). Adjust the path below if you keep it elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from millennium_pulvini_integration import _pure_python_phi_fold, _pure_python_phi_unfold
    HAVE_MILLENNIUM = True
except ImportError as e:
    HAVE_MILLENNIUM = False
    _MILLENNIUM_IMPORT_ERROR = e


# ---------------------------------------------------------------------------
# Compressor adapters -- every adapter has the same shape:
#   compress(data) -> bytes
#   decompress(blob) -> bytes
# so the harness can treat all of them identically.
# ---------------------------------------------------------------------------

@dataclass
class Codec:
    name: str
    compress: Callable[[bytes], bytes]
    decompress: Callable[[bytes], bytes]
    available: bool = True
    unavailable_reason: str = ""


def _millennium_compress(data: bytes) -> bytes:
    """
    Wraps the Millennium compression to return a flat bytes blob.
    Uses the internal _pure_python_phi_fold function directly.
    Uses pickle to preserve numpy array types and structure correctly.
    """
    import numpy as np

    # Convert bytes to numpy array for phi-folding
    data_array = np.frombuffer(data, dtype=np.uint8).astype(np.float64)
    
    # Compress using pure Python implementation
    folded, kernels = _pure_python_phi_fold(data_array, depth=3, kernel_compression=True)
    
    # Use pickle to preserve the exact numpy types and structure
    # This is necessary because the decompression function expects specific numpy dtypes
    payload = {
        "folded": folded,
        "kernels": kernels,
    }
    return pickle.dumps(payload)


def _millennium_decompress(blob: bytes) -> bytes:
    """Decompress Millennium-compressed data."""
    import numpy as np
    
    payload = pickle.loads(blob)
    folded = payload["folded"]
    kernels = payload["kernels"]
    
    reconstructed = _pure_python_phi_unfold(folded, kernels)
    return reconstructed.astype(np.uint8).tobytes()


def build_codecs() -> list[Codec]:
    codecs = [
        Codec("zlib-9", lambda d: zlib.compress(d, 9), zlib.decompress),
        Codec("gzip-9", lambda d: gzip.compress(d, compresslevel=9), gzip.decompress),
    ]

    if HAVE_ZSTD:
        cctx = _zstd.ZstdCompressor(level=19)
        dctx = _zstd.ZstdDecompressor()
        codecs.append(Codec("zstd-19", cctx.compress, dctx.decompress))
    else:
        codecs.append(Codec("zstd-19", None, None, available=False,
                             unavailable_reason="pip install zstandard"))

    if HAVE_BROTLI:
        codecs.append(Codec("brotli-11",
                             lambda d: _brotli.compress(d, quality=11),
                             _brotli.decompress))
    else:
        codecs.append(Codec("brotli-11", None, None, available=False,
                             unavailable_reason="pip install brotli"))

    if HAVE_LZ4:
        codecs.append(Codec("lz4", _lz4.compress, _lz4.decompress))
    else:
        codecs.append(Codec("lz4", None, None, available=False,
                             unavailable_reason="pip install lz4"))

    if HAVE_MILLENNIUM:
        codecs.append(Codec("millennium-phi", _millennium_compress, _millennium_decompress))
    else:
        codecs.append(Codec("millennium-phi", None, None, available=False,
                             unavailable_reason=f"import failed: {_MILLENNIUM_IMPORT_ERROR}"))

    return codecs


# ---------------------------------------------------------------------------
# Corpora
# ---------------------------------------------------------------------------

def synthetic_corpora() -> dict[str, bytes]:
    import random
    rng = random.Random(42)  # fixed seed: reproducible, not "lucky"

    return {
        "periodic_3": (b"ABC" * 1000),
        "periodic_5": (b"ABCDE" * 600),
        "low_entropy": (b"A" * 5000 + b"B" * 3000 + b"C" * 2000),
        "high_entropy": bytes(rng.randrange(256) for _ in range(10000)),
        "mixed": (b"A" * 1000 + bytes(range(256)) * 10),
        "structured": (b"A" * 1000 + b"B" * 500 + b"C" * 250) * 10,
        "english_text_like": (
            b"the quick brown fox jumps over the lazy dog. " * 400
        ),
    }


def real_corpora(directory: Path, max_file_bytes: int = 5_000_000) -> dict[str, bytes]:
    out = {}
    if not directory.exists():
        print(f"warning: --real-data-dir {directory} does not exist, skipping", file=sys.stderr)
        return out
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            size = path.stat().st_size
            if size == 0 or size > max_file_bytes:
                continue
            try:
                out[str(path.relative_to(directory))] = path.read_bytes()
            except OSError:
                continue
    return out


# ---------------------------------------------------------------------------
# Benchmark core
# ---------------------------------------------------------------------------

@dataclass
class BenchResult:
    corpus: str
    codec: str
    original_size: int
    compressed_size: int | None = None
    ratio: float | None = None
    space_saved_pct: float | None = None
    compress_ms: float | None = None
    decompress_ms: float | None = None
    correct: bool | None = None
    error: str | None = None


def run_one(corpus_name: str, data: bytes, codec: Codec) -> BenchResult:
    r = BenchResult(corpus=corpus_name, codec=codec.name, original_size=len(data))

    if not codec.available:
        r.error = f"not installed ({codec.unavailable_reason})"
        return r

    original_hash = hashlib.sha256(data).hexdigest()

    try:
        t0 = time.perf_counter()
        blob = codec.compress(data)
        t1 = time.perf_counter()
        restored = codec.decompress(blob)
        t2 = time.perf_counter()
    except Exception as e:
        r.error = f"{type(e).__name__}: {e}"
        return r

    r.compressed_size = len(blob)
    r.compress_ms = (t1 - t0) * 1000
    r.decompress_ms = (t2 - t1) * 1000
    r.correct = hashlib.sha256(restored).hexdigest() == original_hash

    if r.correct and r.compressed_size > 0:
        r.ratio = r.original_size / r.compressed_size
        r.space_saved_pct = (1 - 1 / r.ratio) * 100
    elif not r.correct:
        r.error = "ROUND-TRIP MISMATCH -- result excluded from ranking"

    return r


def run_benchmark(corpora: dict[str, bytes], codecs: list[Codec]) -> list[BenchResult]:
    results = []
    for corpus_name, data in corpora.items():
        for codec in codecs:
            results.append(run_one(corpus_name, data, codec))
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_report(results: list[BenchResult]) -> str:
    lines = []
    corpora = sorted(set(r.corpus for r in results))

    for corpus in corpora:
        rows = [r for r in results if r.corpus == corpus]
        original_size = rows[0].original_size
        lines.append(f"\n## {corpus}  ({original_size:,} bytes)\n")
        lines.append("| codec | status | compressed | ratio | space saved | compress ms | decompress ms |")
        lines.append("|---|---|---|---|---|---|---|")

        valid = [r for r in rows if r.correct and r.ratio is not None]
        best_name = max(valid, key=lambda r: r.ratio).codec if valid else None

        for r in rows:
            if r.error and r.compressed_size is None:
                lines.append(f"| {r.codec} | SKIP | - | - | - | - | - | {r.error} |")
                continue
            if not r.correct:
                lines.append(
                    f"| {r.codec} | **FAIL (data corrupted)** | {r.compressed_size:,} | "
                    f"n/a | n/a | {r.compress_ms:.2f} | {r.decompress_ms:.2f} |"
                )
                continue
            marker = " **<- best**" if r.codec == best_name else ""
            lines.append(
                f"| {r.codec} | OK{marker} | {r.compressed_size:,} | "
                f"{r.ratio:.2f}x | {r.space_saved_pct:.2f}% | "
                f"{r.compress_ms:.2f} | {r.decompress_ms:.2f} |"
            )

    # Summary: how often does millennium-phi actually win, honestly
    lines.append("\n## Summary\n")
    mill_rows = [r for r in results if r.codec == "millennium-phi"]
    if not mill_rows or all(r.error and r.compressed_size is None for r in mill_rows):
        lines.append("millennium-phi was not available in this run "
                      "(fix the import path / adapter and re-run).")
    else:
        wins, losses, fails, total = 0, 0, 0, 0
        for corpus in corpora:
            rows = [r for r in results if r.corpus == corpus]
            valid = [r for r in rows if r.correct and r.ratio is not None]
            mill = next((r for r in rows if r.codec == "millennium-phi"), None)
            if mill is None:
                continue
            total += 1
            if not mill.correct:
                fails += 1
                continue
            if not valid:
                continue
            best = max(valid, key=lambda r: r.ratio)
            if best.codec == "millennium-phi":
                wins += 1
            else:
                losses += 1
        lines.append(f"millennium-phi: {wins} win(s), {losses} loss(es), "
                      f"{fails} correctness failure(s), out of {total} corpora tested.")
        if fails:
            lines.append(
                "\n**Any correctness failure above means millennium-phi's ratio "
                "on that corpus does not count as a result** -- a compressor "
                "that doesn't round-trip isn't a compressor, it's data loss. "
                "Fix those first; a ratio next to a FAIL is not a claim you "
                "can defend."
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-data-dir", type=Path, default=None,
                         help="Directory of real files to benchmark against, in addition to synthetic corpora.")
    parser.add_argument("--output", type=Path, default=None,
                         help="Write the markdown report here instead of (or in addition to) stdout.")
    parser.add_argument("--synthetic-only", action="store_true",
                         help="Skip real-data-dir even if provided.")
    args = parser.parse_args()

    corpora = synthetic_corpora()
    if args.real_data_dir and not args.synthetic_only:
        corpora.update(real_corpora(args.real_data_dir))

    codecs = build_codecs()

    print(f"Codecs: {[c.name for c in codecs if c.available]} "
          f"(unavailable: {[(c.name, c.unavailable_reason) for c in codecs if not c.available]})")
    print(f"Corpora: {list(corpora.keys())}")

    results = run_benchmark(corpora, codecs)
    report = format_report(results)

    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"\nWritten to {args.output}")


if __name__ == "__main__":
    main()
