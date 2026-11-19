"""Reproducible bounded SHA-256d and nonce-representation benchmark."""

import argparse
import hashlib
import statistics
from pathlib import Path
import json
import os
import platform
import time

from chronus.execution.mining import _max_candidates, search_nonce_range
from chronus.execution.structural import zeckendorf_decode, zeckendorf_encode


def paired_mainnet(corpus: Path, window: int):
    """Measure the current bounded production search method and full-header reference.

    Windows are constructed using historical winners; this measures bounded
    execution, not blind prediction, resident-plan qualification or live mining.
    """
    from chronus.execution.geometric_galois_miner import GeometricGaloisMiner
    from chronus.stratum.gatekeeper import decode_nbits_target
    raw = corpus.read_bytes()
    if hashlib.sha256(raw).hexdigest() != "3db2d4a97543f8ae786691a193eff8cf6b7e5922208beff05340c3f08413cc76":
        raise ValueError("unexpected mainnet corpus digest")
    blocks = json.loads(raw)["blocks"]
    assert len(blocks) == len({b["height"] for b in blocks}) == 500
    engine = GeometricGaloisMiner()
    rows = []
    for b in blocks:
        header = bytes.fromhex(b["header_hex"])
        prefix = header[:76]
        winner = int.from_bytes(header[76:], "little")
        target = decode_nbits_target(header[72:76][::-1].hex())
        assert hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex() == b["block_hash_be"]
        offset = int.from_bytes(hashlib.sha256(prefix).digest()[:4], "big") % window
        base = max(0, min(winner - offset, (1 << 32) - window))
        excluded = winner + 1 if winner + window < 1 << 32 else winner - window
        for mode, start in (("known_winner", base), ("excluded_winner", excluded)):
            assert 0 <= start <= (1 << 32) - window
            t0 = time.perf_counter_ns()
            result = engine.solve_header_range(prefix, target, start, window)
            elapsed = time.perf_counter_ns() - t0
            t0 = time.perf_counter_ns()
            reference = None
            for n in range(start, start + window):
                digest = hashlib.sha256(hashlib.sha256(prefix + n.to_bytes(4, "little")).digest()).digest()
                if int.from_bytes(digest, "little") <= target:
                    reference = n
                    break
            reference_ns = time.perf_counter_ns() - t0
            expected_evaluations = window if reference is None else reference - start + 1
            assert result.found == (reference is not None)
            assert result.nonce == reference
            assert result.iterations_evaluated == expected_evaluations
            assert reference == (winner if mode == "known_winner" else None)
            if result.found:
                assert result.header_hash == hashlib.sha256(hashlib.sha256(prefix + reference.to_bytes(4, "little")).digest()).digest()
            rows.append({"height": b["height"], "mode": mode, "base": start, "window": window,
                         "nonce": reference, "evaluated": result.iterations_evaluated,
                         "reference_evaluations": expected_evaluations, "current_search_ns": elapsed,
                         "reference_ns": reference_ns})
    summary = {}
    for mode in ("known_winner", "excluded_winner"):
        group = [r for r in rows if r["mode"] == mode]
        summary[mode] = {k: statistics.mean(r[k] for r in group) for k in
                         ("evaluated", "reference_evaluations", "current_search_ns", "reference_ns")}
    return {"execution_mode": "SOFTWARE_EXECUTION", "scope": "bounded historical search, known windows, no pool",
            "commit": os.environ.get("GITHUB_SHA"), "platform": platform.platform(), "python": platform.python_version(),
            "logical_cpus": os.cpu_count(), "workers": 1, "corpus_sha256": hashlib.sha256(raw).hexdigest(),
            "window": window, "known_hits": 500, "excluded_hits": 0, "summary": summary, "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=int, default=32768)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--mainnet-corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    max_candidates = _max_candidates()  # runtime bound (CHRONUS_* config), not a constant
    if not 1 <= args.candidates <= max_candidates:
        parser.error(f"candidates must be between 1 and {max_candidates}")

    if args.mainnet_corpus:
        if args.workers != 1 or args.candidates > (1 << 20):
            parser.error("paired mainnet benchmark uses one worker and a bounded window")
        report = paired_mainnet(args.mainnet_corpus, args.candidates)
        if args.out:
            args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
        return

    start = time.perf_counter()
    result = search_nonce_range(bytes(80), 0, args.candidates, 0, args.workers)
    hash_seconds = time.perf_counter() - start

    start = time.perf_counter()
    binary = 0
    for _ in range(args.candidates):
        binary += 1
    binary_seconds = time.perf_counter() - start

    start = time.perf_counter()
    encoded = ()
    for _ in range(args.candidates):
        encoded = zeckendorf_encode(zeckendorf_decode(encoded) + 1)
    structural_seconds = time.perf_counter() - start
    assert binary == zeckendorf_decode(encoded) == args.candidates

    print(json.dumps({
        "execution_mode": "SOFTWARE_EXECUTION",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "requested_workers": args.workers,
        "actual_workers": result["workers"],
        "lanes": len(result["lanes"]),
        "candidates": result["tested"],
        "sha256d_seconds": hash_seconds,
        "sha256d_hashes_per_second": result["tested"] / hash_seconds,
        "binary_increment_seconds": binary_seconds,
        "zeckendorf_decode_increment_reencode_seconds": structural_seconds,
    }, indent=2))


if __name__ == "__main__":
    main()
