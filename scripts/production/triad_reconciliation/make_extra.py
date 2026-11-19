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

if sys.argv[1] == "post":
    cfgp = Path(sys.argv[2]); cfg = json.loads(cfgp.read_text()); qvd = Path(sys.argv[3])
    rows = json.loads(Path(cfg["out_json_rows"]).read_text()); CAND = cfg["candidate_sha"]
    xc = {r["id"]: r for r in json.loads(Path(cfg["xchecks"]).read_text())["results"]}
    D = Path(cfg["junit"]).parent
    ok = lambda r: r["Qualification verdict"] == "SOFTWARE-BASE VERIFIED"
    by = lambda pre: [r for r in rows if r["Requirement ID"].startswith(pre)]
    ids = lambda rs: [r["Requirement ID"] for r in rs]
    def scope_verdict(pre, name):
        rs = by(pre); good = [r for r in rs if ok(r)]; hold = [r for r in rs if not ok(r)]
        v = "HOLD / NOT CERTIFIED" if hold else "SOFTWARE-BASE VERIFIED (not production-certified)"
        return {"scope": name, "verdict": v,
                "basis": f"{len(good)}/{len(rs)} rows software-base verified ({', '.join(ids(good)) or 'none'}); held: " +
                         ("; ".join(f"{r['Requirement ID']} ({r['Qualification verdict'].split(': ',1)[-1]})" for r in hold) or "none")}
    verdicts = [scope_verdict("C-", "CHRONUS / QiGPU"), scope_verdict("O-", "OVID"), scope_verdict("T-", "THESEUS"),
                {"scope": "External authorities (Salamander, AL HARAS, PYTHIA)", "verdict": "GATED, not assessed here",
                 "basis": "No implementation or contract for these authorities exists on main. Their authority is preserved and not claimed."}]
    tri = scope_verdict("I-", "Integrated triad")
    tri["verdict"] = "HOLD / NOT CERTIFIED"
    tri["basis"] += ". Mandatory physical-device, deployment and release evidence is missing (PRODUCTION_QUALIFIED.json says NOT_QUALIFIED)."
    verdicts.append(tri)
    # qualification verdict artifact for the candidate
    q = None
    f = next(qvd.rglob("ci-verdict.json"), None)
    if f:
        d = json.loads(f.read_text())
        q = {"run_id": cfg["ci"].get("Chronus V2 evidence qualification", {}).get("run_id"), "status": d["status"],
             "deployment_profile": d.get("deployment_profile"), "gates": d.get("gates"), "blockers": d.get("blockers"), "claims": d.get("claims")}
    # artifacts
    arts = []
    for l in (D / "dist/SHA256SUMS").read_text().splitlines():
        h, n = l.split()
        arts.append({"name": n, "bytes": (D / "dist" / n).stat().st_size, "sha256": h})
    cs = cfg.get("codeql_open", [])
    from collections import Counter
    sev = Counter(a["severity"] for a in cs); vend = [a for a in cs if a["path"].startswith("vendor/")]
    ci_ok = [n for n, r in cfg["ci"].items() if r["conclusion"] == "success"]; ci_no = [f"{n} ({r['conclusion']})" for n, r in cfg["ci"].items() if r["conclusion"] != "success"]
    pyj = cfg["ci"].get("CI", {}).get("jobs", {}).get("Python 3.13 tests", {})
    registers = [
     ["1. Pull requests and merge status", ["#173 merged c11af3e6", "#176 merged ad7b9bba", "#180 merged b89a5315", "#182 merged 38fc6373", "#183 merged " + CAND[:8]],
      ["#171 open (decision brief)", "#169 open (decision brief)", "#168 open (decision brief)", "#178 open (self-healing hardening, other stream)", "#181 open (wiring closeout, other stream)", "#185 open (tensor Z2 DMRG, other stream, DIRTY)", "#186 open (this reconciliation)"]],
     ["2. CI workflows (push, candidate SHA)", ci_ok + [f"CI / Python 3.13 tests: {pyj.get('conclusion')}"], ci_no],
     ["3. Tests and acceptance coverage", [cfg["local_suite"]] + [r["Requirement ID"] for r in rows if r["Test coverage"]["files"] and "failed 0" in r["Test execution"]],
      [f"{r['Requirement ID']}: no executable test" for r in rows if not r["Test coverage"]["files"]]],
     ["4. Implementation completeness", [r["Requirement ID"] for r in rows if r["Implementation status"] == "complete"],
      [f"{r['Requirement ID']}: {r['Implementation status']}" for r in rows if r["Implementation status"] != "complete"]],
     ["5. Merged-code verification", [f"rows tested on merged main {CAND[:10]}: " + ", ".join(r["Requirement ID"] for r in rows if r["CI evidence"])],
      [f"{r['Requirement ID']}: not verifiable on main" for r in rows if not r["CI evidence"]]],
     ["6. TODOs and technical debt", ["No TODO/FIXME/HACK markers in maintained src/ and tests/ ('XXX' hits are the Heisenberg XXX model)", "Version drift (36.0.0 in health router) fixed by #183"],
      ["75 markers in vendor/, archive/ and backups (unmaintained)", "theory_of_everything.py:443/447/484 load joblib (pickle) from a relative 'models' dir (RCE risk, owner-protected file, not changed)",
       "capabilities/triad_production_manifest.json statuses still say IMPLEMENTED_BRANCH for merged work"]],
     ["7. Defects and blockers", ["X-check failures: none (" + ", ".join(k for k, v in xc.items() if v["status"] == "PASS") + " PASS)"],
      [f"{k} GAP: {v['requirement']}" for k, v in xc.items() if v["status"] != "PASS"] + ["Codex review quota exhausted (one of three review bots not reviewing)"]],
     ["8. CodeQL and security vulnerabilities", ["Fixed and closed: CodeQL #49 (XSS), #59 (stack-trace exposure), #60 (log injection) in #180", "Dependabot #45/#46 (next) fixed in #180", "pip-audit: no known vulnerabilities", "bandit (CI scope): clean"],
      [f"CodeQL open on main: {len(cs)} ({', '.join(f'{k} {v}' for k, v in sev.items())}); {len(vend)} in vendor/cgminer-3.7.2",
       "Secret scanning #4 Google API key ACTIVE in public history (legacy/firebase-applet-config.json, fa37f2c5): rotate",
       "Secret scanning #2 Stripe key (inactive), #3 Stripe webhook secret (validity unknown): revoke and confirm"]],
     ["9. Runtime qualification", ["Software runtime observed on this host and in CI for SOFTWARE_VERIFIED rows; cross-checks executed in fresh processes"],
      ["No observed runtime of a deployed service instance", "Deployed readiness does not reflect custody health (X6)"]],
     ["10. Physical hardware qualification", [], [f"{r['Requirement ID']}: {r['Hardware evidence']}" for r in rows if r["Hardware evidence"].startswith("REQUIRED")]],
     ["11. Deployment qualification", [], [f"{r['Requirement ID']}: deployment not verified" for r in rows if r["Deployment"].startswith("REQUIRED")]],
     ["12. Production admission", ([f"Software-base ci-verdict {q['status']} (run {q['run_id']}, profile {q['deployment_profile']}); claims {json.dumps(q['claims'])}"] if q else []),
      ["PRODUCTION_QUALIFIED.json: NOT_QUALIFIED, 7 required evidence items missing", "53abc10 (2026-11-16) removed 3 required evidence items (reference-vs-device-differential, sustained-soak-and-recovery, pool-acknowledgement): owner decision, not restored",
       "Non-base profiles (enterprise, sovereign, hyperscaler) not evaluated"]],
    ]
    def xs(*k): return "; ".join(f"{i} {xc[i]['status']}" for i in k if i in xc)
    xtriad = [
     ["CHRONUS → OVID execution outputs and transformation contracts", "ProductionTriad.put → OvidTransformService.fold under the versioned contract `ovid.m15-byte-pairs/v1`; real-workload benchmark custody receipt; tests/test_triad_production.py", "SOFTWARE_VERIFIED"],
     ["OVID → THESEUS materialisation, lineage and durable custody", "TRIAD_REPRESENTATION_COMMITTED journal event; envelope lineage; " + xs("X1", "X5b"), "SOFTWARE_VERIFIED"],
     ["THESEUS → CHRONUS verified retrieval, reconstruction and restart continuity", xs("X1", "X2d", "X8"), "SOFTWARE_VERIFIED"],
     ["End-to-end integrity and provenance across the three authorities", xs("X1", "X5a", "X5b", "X8b") + "; digests verified at each hop", "SOFTWARE_VERIFIED"],
     ["Bidirectional THESEUS–SQLite orphan reconciliation", xs("X2a", "X2b", "X2c", "X2d") + ". Rows pointing at missing objects fail closed. Unreferenced objects and stray shard files are neither reported nor reconciled.", "GAP: HOLD"],
     ["Durable custody, not process-local or ephemeral state", "ProductionTriad uses DurableTheseusService (SQLite WAL, FK, full sync) — " + xs("X1") + ". The deployed service and console still use in-memory TheseusService(OVIDStorage()) — " + xs("X7"), "PARTIAL: HOLD"],
     ["Fresh-process replay and deterministic reconstruction", xs("X1"), "SOFTWARE_VERIFIED"],
     ["Transactional consistency, tenant isolation and concurrent access", xs("X3", "X4"), "SOFTWARE_VERIFIED"],
     ["Failure propagation, degraded operation and fail-closed semantics", xs("X2a", "X2d", "X5a", "X5b", "X8b") + ". Degraded operation under partial failure is not defined for the deployed service.", "SOFTWARE_VERIFIED (storage); deployed service: GAP"],
     ["Storage repair versus Salamander system-level self-healing", "THESEUS repairs bounded storage only: RS(48,32) over GF(257), t=8 bytes per 32-byte block, with an audit trail in self_heal_events (" + xs("X8", "X8b") + "). Salamander's system self-healing authority is not implemented on main and is not claimed (E-01). #178 (Salamander-governed remediation) is open in another stream.", "STORAGE REPAIR SOFTWARE_VERIFIED; SALAMANDER GATED"],
     ["Readiness derived from actual required component health", xs("X6") + ". /health/ready checks only the execution adapter.", "GAP: HOLD"],
     ["End-to-end visibility in the Chronus Studio Web Console", xs("X7"), "GAP: HOLD"],
    ]
    outstanding = [
     "G1. Physical device evidence for OpenCL, CUDA and Metal tensor routes and hardware performance (C-08, C-09, C-10, C-12, C-19). Owner: provide an identified device. Class: AVAILABLE_NOT_EXECUTED or UNAVAILABLE.",
     "G2. Wire ProductionTriad durable custody into the deployed service and console, and derive /health/ready from custody health (C-16, C-17, I-02; X6, X7). Owner approval: custody path, volume and readiness contract.",
     "G3. THESEUS orphan reconciliation for unreferenced objects and stray shard files (T-07; X2b, X2c). Owner decision: report-only or garbage collection.",
     "G4. Deployment-profile evidence: target environment, replication, RTO/RPO and external key custody (C-03, C-04, C-18, T-10, T-11).",
     "G5. PRODUCTION_QUALIFIED.json: 7 missing items, and 53abc10 removed 3 required items. Owner decision; not changed here.",
     "G6. External authorities Salamander, AL HARAS and PYTHIA: no contract on main (E-01, E-02, E-03).",
     "G7. OVID folding (O-05) depends on the #171 decision.",
     "G8. Rotate the Google API key exposed in public git history (secret-scanning #4, active), then close the alerts.",
     "G9. Decide on CodeQL for vendored cgminer: exclude via paths-ignore or delete if unused (33 alerts).",
     "G10. theory_of_everything.py pickle loading (RCE risk): owner-protected file, report only.",
    ]
    sw_vs_phys = [
     "Software qualification (SOFTWARE_VERIFIED): the full pytest suite, cross-triad checks, evidence gates, benchmarks on public data and the package build ran on the candidate SHA, on this host (cloud VM, no GPU) and on GitHub-hosted runners. The CI software-base verdict is attested.",
     "Physical qualification (PHYSICAL_DEVICE_OBSERVED): no rows. No GPU, OpenCL, CUDA or Metal device and no physical disk was observed. Storage timings are SQLite app-call timings, not IOPS, and the tensor timings are a CPU NumPy reference showing Chronus 2–6× slower.",
     "Historical evidence (PRODUCTION_QUALIFIED.json at 50187b18, evidence/ and archive/) stays scoped to its revision and is not used as evidence for the candidate.",
    ]
    closure = cfg.get("closure", [])
    open_prs = [
     "#171 Feat/grok triad grover: do not merge as-is. Title framing ('Grover in O(1)') and 'exponentially' fail the claim-token policy (scripts/ci/claim_token_policy.json). test_reality finds a misclassified test and mocks in a real test (tests/test_gl2_review.py:197–198). There are 29 unresolved review threads. Fix by renaming the paper framing to O(1)-state, fixing test_reality, resolving threads and rebasing; optionally split the paper from the code. Your authorisation is needed for the paper's publication and framing, and then the merge.",
     "#169 Feat/quantum team: close and split into focused PRs (hyba_mine, hyba_trust, PRODUCTION evidence docs) rebased on main. It mixes 170 files, has conflicts, 47 unresolved threads and failing CodeQL, HYBA Mine, hygiene and claim-token checks. It also edits the owner-protected PRODUCTION_QUALIFIED.json and BLOCKER_TOE_1.patch, which need your authorisation.",
     "#168 M_32 attractor + exact Grover unified: close as superseded. It targets the stale branch fix/remediation-7143ceab-91fb4d (not an ancestor of main; its PR #68 is closed), touches directories absent from main, fails CI broadly, and #171's triad_grover.py supersedes it. Your authorisation is needed for the close and the branch deletion.",
    ]
    security = registers[7][1] + registers[7][2] + [
     "Non-vendored alerts triaged as low or false positive: test-only (#1–3, #43, #44, #51–58); static pages (#4–6); false positives (#41, #45, #50); low (#42, #46–48).",
     "The bandit whole-tree scan has 5 MEDIUM B310 findings, all in packages/hyba_mine/tests/test_ledger_status.py:132–146 (tests)."]
    admission = ("**PRODUCTION ADMISSION: HOLD / NOT CERTIFIED.** " + f"Candidate `{CAND}` is software-base verified for the rows marked so, with attested CI evidence"
                 + (f" (ci-verdict {q['status']}, run {q['run_id']})" if q else "") +
                 ". Production admission still needs physical device evidence (none observed), deployment verification (none), durable custody wired into the deployed service with custody-derived readiness, orphan reconciliation, and the owner-held release evidence in PRODUCTION_QUALIFIED.json. Green CI and merged PRs do not establish production readiness on their own.")
    cfg.update({"verdicts": verdicts, "registers": registers, "qualification_verdict": q, "artifacts": arts,
                "artifact_note": f"Built on this host from a clean worktree of `{CAND}` with `python -m build`; `twine check` passed. The artifacts are not published or signed. The digests let you reproduce the build or compare it with a CI-built artifact.",
                "outstanding": outstanding, "sw_vs_phys": sw_vs_phys, "open_prs": open_prs, "security": security,
                "xtriad": xtriad, "admission": admission})
    cfgp.write_text(json.dumps(cfg, indent=1))
    print("post ok")
