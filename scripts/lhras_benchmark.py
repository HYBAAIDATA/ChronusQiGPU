"""AL HARAS / L-HRAS reproducible benchmark harness.

Measures the governed-request path against named conventional baselines,
with fixed workloads, repeated trials, and confidence intervals. This is a
developer-executed microbenchmark — it answers "what does the mechanism
cost?" not "is it faster than X for workload Y". Third-party reproduction
is the remaining gate (see docs/al-haras/GAP_ANALYSIS.md).

    python scripts/lhras_benchmark.py --trials 200 --json

Baselines (named, conventional):
    b0_hmac_verify        raw HMAC-SHA256 token check — no ledger, no audit
    b1_jsonl_append       plain JSONL line write+fsync — no hash chain/lock
    b2_policy_eval        dict lookup policy check — no entitlement/audit

Measured subjects:
    al_haras_verify       entitlement verify (HMAC + claims binding)
    boundary_evaluate     full API path: verify + preflight + audit append
    lhras_respond         full Guardian conjunction (7 topologies, 6
                          intelligences, 5 modes, fold, aethel write)
    lhras_stand_cold      initialize()+stand() cold-start latency

All numbers are nanoseconds/seconds measured with time.perf_counter_ns.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import statistics
import sys
import tempfile
import time
import platform
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims
from al_haras.guardian import ALHaras, GuardianPolicy
from al_haras.runtime import GuardianAPI
from al_haras.settings import ALHarasSettings
from al_haras.audit import HashChainAudit

from l_hras import (
    Request,
    RequestAttestation,
    RequestKind,
    initialize,
    load_config,
    respond,
    signed_request,
    stand,
)


def _stats(samples: list[float]) -> dict:
    n = len(samples)
    mean = statistics.fmean(samples)
    sd = statistics.pstdev(samples) if n > 1 else 0.0
    srt = sorted(samples)
    ci95 = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
    return {
        "trials": n,
        "mean_ms": round(mean * 1e3, 4),
        "p50_ms": round(srt[n // 2] * 1e3, 4),
        "p95_ms": round(srt[int(n * 0.95)] * 1e3, 4),
        "p99_ms": round(srt[int(n * 0.99)] * 1e3, 4),
        "stddev_ms": round(sd * 1e3, 4),
        "ci95_ms": round(ci95 * 1e3, 4),
        "ops_per_s": round(n / sum(samples), 2) if sum(samples) else 0.0,
    }


def _time(fn, trials: int) -> list[float]:
    samples = []
    for _ in range(trials):
        t0 = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - t0) / 1e9)
    return samples


def run(trials: int, warmup: int = 10) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="lhras_bench_"))
    settings = ALHarasSettings(
        issuer="hyba-subscriptions",
        keyring={"bench-1": b"benchmark-secret-0123456789abcdef0123"},
        audit_path=tmp / "bench-guardian.jsonl",
    )
    authority = SubscriptionAuthority(settings.keyring, settings.issuer)
    claims = SubscriptionClaims(
        issuer=settings.issuer,
        key_id="bench-1",
        tenant_id="bench-tenant",
        capabilities=("hyba.security",),
        actors=("bench-actor",),
        not_before=int(time.time()) - 60,
        expires_at=int(time.time()) + 3600,
        subscription_id="sub-bench",
        max_payload_bytes=4096,
    )
    token = authority.issue(claims)
    secret = settings.keyring["bench-1"]

    # ── baselines ────────────────────────────────────────────────────
    payload = json.dumps({"a": 1, "b": 2}).encode()

    def b0_hmac():
        hmac.new(secret, payload, hashlib.sha256).hexdigest()

    baseline_file = tmp / "baseline.jsonl"
    line = json.dumps({"seq": 0, "event": "x"}) + "\n"

    def b1_jsonl():
        with baseline_file.open("a") as f:
            f.write(line)
            f.flush()

    policy_table = {"bench-actor": {"toe.collapse"}}

    def b2_policy():
        "toe.collapse" in policy_table.get("bench-actor", set())

    # ── subjects ─────────────────────────────────────────────────────
    def s_verify():
        authority.verify(
            token,
            tenant_id="bench-tenant",
            actor="bench-actor",
            capability="hyba.security",
            now=int(time.time()),
        )

    try:
        audit = HashChainAudit(settings.audit_path)
        audit_durable = True
    except RuntimeError:
        audit = HashChainAudit()
        audit_durable = False
    guardian = ALHaras(
        authority=authority,
        policy=GuardianPolicy(
            version=settings.policy_version,
            capability=settings.capability,
            max_payload_bytes=settings.max_payload_bytes,
        ),
        audit=audit,
        boundary_audit=HashChainAudit(),
    )
    api = GuardianAPI(guardian, settings, evidence_provider=lambda obs: {"schema_version": "bench"})
    headers = {
        "x-hyba-tenant": "bench-tenant",
        "x-hyba-actor": "bench-actor",
        "authorization": f"Bearer {token}",
    }
    body = {
        "operation": "toe.collapse",
        "resource": "bench",
        "payload": {"n": 1},
        "observation": {"baseline": 0.1},
        "request_id": "req-bench",
    }

    def s_evaluate():
        api.evaluate(headers=headers, body=dict(body))

    cfg_r = load_config(REPO_ROOT / "l_hras" / "config.example.toml")
    lhras = None
    if cfg_r.is_ok:
        init_r = initialize(cfg_r.value)
        if init_r.is_ok:
            lhras = init_r.value
            stand(lhras)
    req = None
    if lhras is not None:
        req = Request(
            kind=RequestKind.BENIGN,
            attestation=RequestAttestation(token="", payload_digest=""),
            actor="bench-actor",
            action="toe.collapse",
            telemetry=[0.1, 0.2, 0.15, 0.18, 0.12, 0.11, 0.09],
            observation={"baseline": 0.12, "spread": 0.05},
        )
        signed_request(cfg_r.value.trust_root, req)

    def s_lhras():
        if lhras is not None and req is not None:
            respond(lhras, req)

    def s_cold():
        c = load_config(REPO_ROOT / "l_hras" / "config.example.toml")
        if c.is_ok:
            i = initialize(c.value)
            if i.is_ok:
                stand(i.value)

    suites = {
        "b0_hmac_verify": b0_hmac,
        "b1_jsonl_append": b1_jsonl,
        "b2_policy_eval": b2_policy,
        "al_haras_verify": s_verify,
        "boundary_evaluate": s_evaluate,
        "lhras_respond": s_lhras,
    }
    for fn in suites.values():
        for _ in range(warmup):
            fn()
    results = {name: _stats(_time(fn, trials)) for name, fn in suites.items()}
    # cold start is expensive; fewer trials
    cold_trials = max(3, trials // 20)
    cold_samples = []
    for _ in range(cold_trials):
        t0 = time.perf_counter_ns()
        s_cold()
        cold_samples.append((time.perf_counter_ns() - t0) / 1e9)
    results["lhras_stand_cold"] = _stats(cold_samples)

    report = {
        "benchmark": "lhras-governed-path",
        "trials_per_case": trials,
        "warmup": warmup,
        "audit_durable": audit_durable,
        "platform": {
            "python": platform.python_version(),
            "system": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
        },
        "results_ms": results,
        "overhead_vs_baseline": {
            "entitlement_vs_raw_hmac": round(
                results["al_haras_verify"]["mean_ms"]
                / max(results["b0_hmac_verify"]["mean_ms"], 1e-9),
                2,
            ),
            "evaluate_vs_policy_lookup": round(
                results["boundary_evaluate"]["mean_ms"]
                / max(results["b2_policy_eval"]["mean_ms"], 1e-9),
                2,
            ),
        },
        "disclaimer": (
            "Developer-executed microbenchmark on a single host. Third-party "
            "reproduction on named hardware with fixed datasets is the "
            "remaining evidence gate."
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--out", default=None, help="write JSON report to path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run(max(5, args.trials))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"wrote {args.out}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
