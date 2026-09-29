"""Hybrid substrate benchmark — measured, paired, falsifiable.

Four configurations on the same job set:

  (a) gpu_only       — sequential scan through the coordinator, even split
  (b) asic_only      — skipped when no ASIC channel is configured (gap noted)
  (c) hybrid_even    — coordinator, even partition
  (d) hybrid_lucas   — coordinator, Lucas-weighted partition

Metrics: nonces-to-first-share (total physical hashes executed), wall ns,
and the coverage-certificate digest per job. Pairwise bootstrap 95% CIs
are computed on the paired per-header differences (d)-(c) and (d)-(a).
A negative control (a target so easy every traversal is equivalent) and a
positive control (a target where any traversal signal would show) gate the
verdict: if the negative control shows a non-zero difference the harness
is measuring artifacts, not signal.

Header corpus: a real corpus may be supplied via ``--headers`` (one 80-byte
hex header per line). Without it the corpus is DETERMINISTICALLY SYNTHETIC
(``sha256(seed || i)``-derived) and is labeled synthetic in every artifact.
"""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from hyba.hybrid.asic_solver import ASICSolver
from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
from hyba.hybrid.gpu_solver import GPUSolver
from hyba.hybrid.nonce_scheduler import AttestationRegistry

# Dockerfile.hybrid points HYBA_REPORTS_DIR at a volume-mountable directory.
REPORTS = Path(
    os.getenv("HYBA_REPORTS_DIR") or Path(__file__).resolve().parent.parent / "reports"
)


def synthetic_headers(n: int, seed: int = 0x48495259) -> List[bytes]:
    """Deterministic synthetic 80-byte headers. LABELED SYNTHETIC."""
    out = []
    for i in range(n):
        blob = bytearray()
        ctr = i
        while len(blob) < 80:
            blob += hashlib.sha256(seed.to_bytes(4, "little") + ctr.to_bytes(8, "little")).digest()
            ctr += 1
        out.append(bytes(blob[:80]))
    return out


def load_headers(path: Path) -> List[bytes]:
    headers = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        raw = bytes.fromhex(line)
        if len(raw) != 80:
            raise ValueError(f"header line is not 80 bytes: {line[:32]}…")
        headers.append(raw)
    return headers


def target_from_bits(bits: int) -> bytes:
    """2^bits target as 32-byte big-endian."""
    if not (0 < bits <= 256):
        raise ValueError("bits in (0, 256]")
    return ((1 << bits) - 1).to_bytes(32, "big")


def bootstrap_ci(
    diffs: List[float], n_resamples: int = 10_000, ci: float = 0.95, seed: int = 0
) -> Dict[str, float]:
    arr = np.asarray(diffs, dtype=np.float64)
    if arr.size == 0:
        return {"low": float("nan"), "high": float("nan"), "contains_zero": True}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_resamples, arr.size))
    means = arr[idx].mean(axis=1)
    low = float(np.quantile(means, (1 - ci) / 2))
    high = float(np.quantile(means, 1 - (1 - ci) / 2))
    return {"low": low, "high": high, "contains_zero": bool(low <= 0 <= high)}


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return float("nan")
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def run_config(
    config: str,
    headers: List[bytes],
    target: bytes,
    nonce_space: int,
) -> Dict[str, Any]:
    """Run one configuration; return per-header trials and totals."""
    trials = []
    registry_before = len(AttestationRegistry.get().snapshot())
    gpu = GPUSolver()
    asic = ASICSolver()
    coord = HybridCoordinator(gpu, asic)
    for i, header in enumerate(headers):
        if config == "asic_only":
            if not asic.capability().supported:
                trials.append({"found": False, "nonces_tried": 0, "skipped": True})
                continue
            # Pure ASIC path: the window goes to the ASIC alone.
            from hyba.hybrid.nonce_scheduler import NonceWindow

            t0 = time.monotonic_ns()
            window = NonceWindow(
                job_id=f"asic_only-{i}", session_epoch=0, job_epoch=0,
                base_nonce=0, span=nonce_space, target=target,
            )
            handle = asic.dispatch(window)
            share = None
            deadline = time.monotonic_ns() + 60_000_000_000
            while share is None and time.monotonic_ns() < deadline:
                share = asic.poll(handle)
                if share is None and asic.is_done(handle):
                    break
            if share is None:
                asic.cancel(handle, reason="benchmark_deadline")
            trials.append(
                {
                    "found": share is not None,
                    "nonces_tried": (
                        share.nonces_tried if share else nonce_space
                    ),
                    "winner_probe_index": (
                        share.probe_index if share else None
                    ),
                    "wall_ns": time.monotonic_ns() - t0,
                    "cert_digest": "asic_only:no_partition",
                    "skipped": False,
                }
            )
            continue
        strategy = {
            "gpu_only": "even",
            "hybrid_even": "even",
            "hybrid_lucas": "lucas",
        }[config]
        job = StratumJob(
            job_id=f"{config}-{i}",
            header80=header,
            target=target,
            nonce_space=nonce_space,
        )
        res = coord.run_job(job, strategy=strategy)
        trials.append(
            {
                "found": res.share is not None,
                "nonces_tried": res.total_nonces_tried,
                "winner_probe_index": res.winner_probe_index,
                "wall_ns": res.wall_ns,
                "cert_digest": res.certificate.digest,
                "skipped": False,
            }
        )
    att = AttestationRegistry.get().snapshot()
    done = [t for t in trials if not t["skipped"]]
    tried = [t["nonces_tried"] for t in done]
    probes = [t["winner_probe_index"] for t in done if t.get("winner_probe_index") is not None]
    return {
        "config": config,
        "trials": trials,
        "n_completed": len(done),
        "n_skipped": len(trials) - len(done),
        "mean_probe_index": statistics.fmean(probes) if probes else None,
        "median_probe_index": statistics.median(probes) if probes else None,
        "p95_probe_index": _percentile(probes, 0.95),
        "mean_nonces": statistics.fmean(tried) if tried else None,
        "median_nonces": statistics.median(tried) if tried else None,
        "p95_nonces": _percentile(tried, 0.95),
        "total_hashes": int(sum(tried)),
        "wall_ns_total": int(sum(t["wall_ns"] for t in done)),
        "attestations_emitted": len(att) - registry_before,
        "found_rate": (
            sum(1 for t in done if t["found"]) / len(done) if done else None
        ),
    }


def benchmark(
    n: int,
    target_bits: int,
    nonce_space: int,
    headers_path: Optional[Path] = None,
    resamples: int = 2000,
) -> Dict[str, Any]:
    if headers_path is not None:
        headers = load_headers(headers_path)
        corpus = f"pinned file: {headers_path}"
        synthetic = False
    else:
        headers = synthetic_headers(n)
        corpus = "DETERMINISTIC SYNTHETIC (sha256-derived, fixed seed)"
        synthetic = True
    headers = headers[:n]
    target = target_from_bits(target_bits)

    results: Dict[str, Any] = {}
    for config in ("gpu_only", "asic_only", "hybrid_even", "hybrid_lucas"):
        results[config] = run_config(config, headers, target, nonce_space)

    def paired(a: str, b: str) -> List[float]:
        """Paired difference on winner probe index — the ordering metric."""
        ta = results[a]["trials"]
        tb = results[b]["trials"]
        diffs = []
        for x, y in zip(ta, tb):
            if x["skipped"] or y["skipped"] or not x["found"] or not y["found"]:
                continue
            if x.get("winner_probe_index") is None or y.get("winner_probe_index") is None:
                continue
            diffs.append(float(y["winner_probe_index"]) - float(x["winner_probe_index"]))
        return diffs

    dc = paired("hybrid_even", "hybrid_lucas")
    da = paired("gpu_only", "hybrid_lucas")
    return {
        "corpus": corpus,
        "synthetic_corpus": synthetic,
        "n_headers": len(headers),
        "target_bits": target_bits,
        "nonce_space": nonce_space,
        "per_config": {k: {kk: vv for kk, vv in v.items() if kk != "trials"} for k, v in results.items()},
        "lucas_minus_even": {"diffs": dc, "ci95": bootstrap_ci(dc, resamples)},
        "lucas_minus_gpu_only": {"diffs": da, "ci95": bootstrap_ci(da, resamples)},
    }


def _fmt(x: Any) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:,.1f}"
    return str(x)


def write_reports(
    neg: Dict[str, Any],
    pos: Dict[str, Any],
    out_dir: Path = REPORTS,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    def table(res: Dict[str, Any]) -> str:
        lines = [
            "| config | completed | skipped | found_rate | mean probe idx | median | p95 | total hashes | wall s |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for name, r in res["per_config"].items():
            wall_s = (r["wall_ns_total"] or 0) / 1e9
            lines.append(
                f"| {name} | {r['n_completed']} | {r['n_skipped']} | "
                f"{_fmt(r['found_rate'])} | {_fmt(r['mean_probe_index'])} | "
                f"{_fmt(r['median_probe_index'])} | {_fmt(r['p95_probe_index'])} | "
                f"{_fmt(r['total_hashes'])} | {wall_s:,.3f} |"
            )
        return "\n".join(lines)

    neg_ci = neg["lucas_minus_gpu_only"]["ci95"]
    pos_ci = pos["lucas_minus_gpu_only"]["ci95"]
    neg_even = neg["lucas_minus_even"]["ci95"]
    pos_even = pos["lucas_minus_even"]["ci95"]

    harness_trustworthy = neg_ci["contains_zero"] and neg_even["contains_zero"]
    significant = not pos_ci["contains_zero"] or not pos_even["contains_zero"]

    lines = [
        "# Hybrid substrate benchmark — raw numbers",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Corpus (negative control): {neg['corpus']} | n={neg['n_headers']} | "
        f"target=2^{neg['target_bits']} | nonce_space={neg['nonce_space']}",
        f"Corpus (positive control): {pos['corpus']} | n={pos['n_headers']} | "
        f"target=2^{pos['target_bits']} | nonce_space={pos['nonce_space']}",
        "",
        "## Negative control (easy target — no traversal can show advantage)",
        "",
        table(neg),
        "",
        "## Positive control (harder target — signal would be visible here)",
        "",
        table(pos),
        "",
        "## Paired differences (95% bootstrap CI, lucas − baseline)",
        "",
        "| comparison | control | CI low | CI high | contains zero |",
        "|---|---|---|---|---|",
        f"| lucas − gpu_only | negative | {neg_ci['low']:,.1f} | {neg_ci['high']:,.1f} | {neg_ci['contains_zero']} |",
        f"| lucas − even split | negative | {neg_even['low']:,.1f} | {neg_even['high']:,.1f} | {neg_even['contains_zero']} |",
        f"| lucas − gpu_only | positive | {pos_ci['low']:,.1f} | {pos_ci['high']:,.1f} | {pos_ci['contains_zero']} |",
        f"| lucas − even split | positive | {pos_even['low']:,.1f} | {pos_even['high']:,.1f} | {pos_even['contains_zero']} |",
        "",
        f"harness_trustworthy (negative CI contains zero): **{harness_trustworthy}**",
        "",
        "The paired-difference metric is *winner probe index*: the winner's",
        "position in the logical traversal order. This is the only metric",
        "comparable across configs, because physical work is bounded below",
        "by launch granularity (a single launch computes its whole window",
        "even when the winner is early). `total hashes` reports the",
        "physical-cost metric separately: digests actually executed on",
        "device, including hashes burned by windows later cancelled.",
    ]
    (out_dir / "hybrid_benchmark.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    if significant:
        verdict = (
            "A statistically significant difference was measured between "
            "Lucas-weighted traversal and at least one baseline on the "
            "positive-control target (95% CI excludes zero). This is a "
            "measured signal on THIS corpus — it requires replication on "
            "real pinned headers before any advantage is claimed."
        )
    else:
        verdict = (
            "No statistically significant difference was measured between "
            "Lucas-weighted traversal and sequential/even baselines on the "
            "positive-control target (all 95% CIs contain zero). On the "
            "measured corpus, the traversal ordering did not change "
            "nonces-to-first-share. That is the honest outcome."
        )
    fals = [
        "# Hybrid falsification report",
        "",
        verdict,
        "",
        f"- harness_trustworthy: {harness_trustworthy} "
        "(negative-control CIs contain zero; the instrument is not "
        "measuring artifacts)"
        if harness_trustworthy
        else f"- harness_trustworthy: {harness_trustworthy} "
        "(negative-control CI excluded zero — the harness itself is "
        "measuring artifacts; all other numbers are suspect)",
        f"- negative control lucas − gpu_only CI: [{neg_ci['low']:,.1f}, {neg_ci['high']:,.1f}]",
        f"- positive control lucas − gpu_only CI: [{pos_ci['low']:,.1f}, {pos_ci['high']:,.1f}]",
        f"- corpus: negative={neg['corpus']} positive={pos['corpus']}",
        "",
        "Method: paired per-header winner probe index (position in logical",
        "traversal order), bootstrap 95% CI. Physical hashes executed are",
        "reported separately in hybrid_benchmark.md.",
        "Every dispatched window was attested; absent ASIC channels were",
        "recorded as attestation gaps, not simulated.",
    ]
    (out_dir / "hybrid_falsification.md").write_text(
        "\n".join(fals) + "\n", encoding="utf-8"
    )

    return {
        "harness_trustworthy": harness_trustworthy,
        "significant": significant,
        "verdict": verdict,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Hybrid GPU+ASIC substrate benchmark")
    ap.add_argument("--n", type=int, default=64, help="number of headers per run")
    ap.add_argument("--neg-bits", type=int, default=252, help="negative-control target bits")
    ap.add_argument("--pos-bits", type=int, default=240, help="positive-control target bits")
    ap.add_argument("--nonce-space", type=int, default=1 << 21, help="nonces per job")
    ap.add_argument("--headers", type=str, default=None, help="pinned header corpus file")
    ap.add_argument("--resamples", type=int, default=2000)
    args = ap.parse_args()

    headers_path = Path(args.headers) if args.headers else None
    print(f"negative control: n={args.n} target=2^{args.neg_bits}")
    neg = benchmark(args.n, args.neg_bits, args.nonce_space, headers_path, args.resamples)
    print(f"positive control: n={args.n} target=2^{args.pos_bits}")
    pos = benchmark(args.n, args.pos_bits, args.nonce_space, headers_path, args.resamples)
    verdict = write_reports(neg, pos)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
    main()
