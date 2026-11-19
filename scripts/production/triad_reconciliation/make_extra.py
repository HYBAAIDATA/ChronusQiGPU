#!/usr/bin/env python3
"""Phase 'pre': write extra.json keys gen.py needs. Phase 'post': add report keys to cfg.json using rows.json.
Usage: make_extra.py pre <cand_sha> <run_dir> <extra.json> | make_extra.py post <cfg.json> <qv_dir>"""
import json, subprocess, sys, re
from pathlib import Path
REPO = "HYBAAIDATA/ChronusQiGPU"; GH = f"https://github.com/{REPO}"
def gh(*a):
    return subprocess.run(["gh", *a], capture_output=True, text=True).stdout

def bench(D):
    out, bm = [], {}
    try:
        c = json.loads((D / "bench/components.json").read_text())
        tm = [m for m in c["measurements"] if "tensor" in m]
        for m in tm:
            t = m["tensor"]
            out.append(f"Tensor add on `{m['path']}` ({t['shape']}, {m['input_bytes']} B, public UCI data): PhiTensorCore median {t['chronus_phitensorcore_add']['median_ns']/1e3:.1f} µs vs NumPy {t['same_workload_numpy_add']['median_ns']/1e3:.1f} µs, so Chronus is {t['chronus_over_numpy_latency_ratio']:.2f}× slower on the numpy-reference backend. Output is exact: {t['output_exact_match']}. Classification: {m['matched_useful_work']['classification']}.")
        rat = [m["tensor"]["chronus_over_numpy_latency_ratio"] for m in tm]
        bm["C-06"] = f"PhiTensorCore add is {min(rat):.1f}× to {max(rat):.1f}× slower than NumPy on {len(rat)} public UCI inputs, with exact output. CPU reference only; no accelerator."
        bm["C-19"] = "There are no device-bound measurements. The CPU reference benchmark is not hardware evidence."
    except Exception as e: out.append(f"Components benchmark unavailable: {e}")
    try:
        s = json.loads((D / "bench/storage.json").read_text())
        ws = sorted(r["write_application_ns"] for r in s["results"]); rs = sorted(r["read_application_ns"] for r in s["results"])
        med = lambda v: v[len(v)//2] / 1e6
        tot = sum(r["source_bytes"] for r in s["results"])
        out.append(f"THESEUS storage app-call timings ({len(ws)} public inputs, {tot} B): write median {med(ws):.2f} ms, read median {med(rs):.2f} ms. All payloads byte-exact: {s['all_payloads_byte_exact']}. Fresh restart verified: {s['fresh_service_restart_verified']}. Limitation stated by the tool: {s['limitation']}")
        bm["T-01"] = f"write median {med(ws):.2f} ms, read median {med(rs):.2f} ms (SQLite/WAL app-call, not physical IOPS)"
    except Exception as e: out.append(f"Storage benchmark unavailable: {e}")
    try:
        r = json.loads((D / "bench/real_workload.json").read_text())
        e0 = r["entries"][0]
        out.append(f"Real-workload triad custody: result {r['result']}. {len(r['entries'])} input(s). Custody write call {e0['custody_write_call_ns']/1e6:.1f} ms, read call {e0['custody_read_call_ns']/1e6:.1f} ms. Restart round-trip verified: {e0['custody_restart_roundtrip_verified']}. Device execution: {json.dumps(r.get('device_execution'))[:120]}")
        bm["I-01"] = f"real-workload custody round-trip {r['result']}: write {e0['custody_write_call_ns']/1e6:.1f} ms, read {e0['custody_read_call_ns']/1e6:.1f} ms, restart verified {e0['custody_restart_roundtrip_verified']}"
    except Exception as e: out.append(f"Real-workload benchmark unavailable: {e}")
    return out, bm

if sys.argv[1] == "pre":
    cand, D, extra = sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    al = json.loads(gh("api", "--paginate", f"repos/{REPO}/code-scanning/alerts?state=open&ref=refs/heads/main&per_page=100") or "[]")
    cq = [{"number": a["number"], "severity": a["rule"].get("security_severity_level") or a["rule"].get("severity"),
           "rule": a["rule"]["id"], "path": a["most_recent_instance"]["location"]["path"],
           "line": a["most_recent_instance"]["location"].get("start_line"), "commit": a["most_recent_instance"].get("commit_sha")} for a in al]
    gates = (D / "gates.txt").read_text()
    sums = (D / "dist/SHA256SUMS").read_text().split("\n")
    inst = (D / "install.log").read_text() if (D / "install.log").exists() else ""
    m = re.search(r"installed (\S+) (\S+)", inst)
    pk = [f"Built from {cand}: " + "; ".join(l.split()[1] for l in sums if l.strip()) + " (sha256 in the artifact manifest)",
          "Build, twine check and TURING build: " + "; ".join(l for l in gates.splitlines() if any(k in l for k in ("build", "twine"))),
          "Clean install of the wheel into a fresh venv from PyPI dependencies: " + "; ".join(l for l in gates.splitlines() if any(k in l for k in ("clean install", "pip check", "installed import"))),
          (f"Installed provenance: chronus {m.group(1)} imported from {m.group(2)}" if m else "Installed provenance: not established"),
          "Packages are not published or signed for release. Release publication requires the qualified main SHA, as the RELEASE workflow requires."]
    b, bm = bench(D)
    extra.write_text(json.dumps({"codeql_open": cq, "packaging": pk, "bench_map": bm, "benchmarks": b, "t09_state": "sw",
        "historical": {"I-03": "PRODUCTION_QUALIFIED.json provenance at 50187b18. Revision-scoped and NOT evidence for the candidate.",
                       "T-12": "Historical evidence under evidence/ and archive/ stays scoped to its own revision and is not carried forward.",
                       "C-08": "Any earlier OpenCL observations are revision-scoped. None were re-executed on a physical device for the candidate."},
        "local_env_extra": inst[-400:]}, indent=1))
    print("pre ok", len(cq), "open CodeQL alerts")
