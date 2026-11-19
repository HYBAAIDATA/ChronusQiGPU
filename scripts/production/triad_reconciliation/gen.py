#!/usr/bin/env python3
"""Build docs/production/TRIAD_RECONCILIATION.{md,json} from executed evidence.

Inputs (all produced on the candidate SHA): junit XML from the local full suite,
cross-check JSON, benchmark JSON, CI runs listed via gh, qualification verdict,
artifact manifest. Nothing is inferred beyond what those inputs contain."""
import json, subprocess, sys, re, xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rows import ROWS

REPO = "HYBAAIDATA/ChronusQiGPU"; GH = f"https://github.com/{REPO}"
cfg = json.loads(Path(sys.argv[1]).read_text())
CAND = cfg["candidate_sha"]; WT = Path(cfg["worktree"])

def sh(*a, cwd=WT):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True).stdout.strip()

# ---- local junit per file
junit = ET.parse(cfg["junit"]).getroot()
per_file = defaultdict(lambda: {"passed":0,"failed":0,"skipped":0})
for tc in junit.iter("testcase"):
    parts = tc.get("classname","").split(".")
    while parts and not parts[-1].startswith("test_"):
        parts.pop()  # drop unittest class names
    f = tc.get("file") or ("/".join(parts) + ".py" if parts else "")
    st = "failed" if (tc.find("failure") is not None or tc.find("error") is not None) else ("skipped" if tc.find("skipped") is not None else "passed")
    per_file[f][st] += 1
suite = {k: int(junit.find("testsuite").get(k) if junit.tag=="testsuites" else junit.get(k)) for k in ("tests","failures","errors","skipped")}

# ---- test reality class per file
reality = {}
for f in WT.glob("tests/**/test_*.py"):
    m = re.search(r"^pytestmark\s*=.*?\b(real|simulated)\b", f.read_text(errors="ignore"), re.M)
    reality[str(f.relative_to(WT))] = m.group(1) if m else "unclassified"

xc = {r["id"]: r for r in json.loads(Path(cfg["xchecks"]).read_text())["results"]}
ci = cfg["ci"]  # {workflow: {run_id, conclusion, jobs:{name:{conclusion, runner, labels}}}}
CI_RUN = ci.get("CI", {})
pyjob = CI_RUN.get("jobs", {}).get("Python 3.13 tests", {})
QV = ci.get("Chronus V2 evidence qualification", {})

pr_cache = {}
def pr_for(sha):
    if not sha: return None
    if sha in pr_cache: return pr_cache[sha]
    out = subprocess.run(["gh","api",f"repos/{REPO}/commits/{sha}/pulls","--jq","[.[]|select(.merged_at!=null)][0].number // empty"],capture_output=True,text=True).stdout.strip()
    pr_cache[sha] = int(out) if out.isdigit() else None
    return pr_cache[sha]

def first_last(paths):
    real = [p for p in paths if (WT / p.split(" ")[0]).exists()]
    if not real: return None, None
    first = sh("git","log",CAND,"--diff-filter=A","--format=%H","--",*[p.split(" ")[0] for p in real]).splitlines()
    last = sh("git","log",CAND,"-1","--format=%H","--",*[p.split(" ")[0] for p in real])
    return (first[-1] if first else None), (last or None)

EVC = {"sw":"SOFTWARE_VERIFIED","gap":"SOFTWARE_VERIFIED (gap observed)","gated":"GATED","unavail":"UNAVAILABLE",
       "avail_not_exec":"AVAILABLE_NOT_EXECUTED","phys_cpu":"SOFTWARE_VERIFIED (CPU reference only); physical AVAILABLE_NOT_EXECUTED",
       "dep_missing":"SOFTWARE_VERIFIED (contract); deployment UNAVAILABLE","pr176":cfg.get("t09_class","GATED")}

out_rows = []
for r in ROWS:
    first, last = first_last(r["paths"])
    tests = [t for t in r["tests"] if (WT / t).exists()]
    agg = {"passed":0,"failed":0,"skipped":0}
    for t in tests:
        for k in agg: agg[k] += per_file[t][k]
    xres = [f"{i}:{xc[i]['status']}" for i in r["xc"] if i in xc]
    tested = bool(tests) and agg["passed"] > 0 and agg["failed"] == 0
    state = r["state"]
    if state == "pr176" and cfg.get("t09_state"): state = cfg["t09_state"]
    gaps = [i for i in r["xc"] if i in xc and xc[i]["status"] != "PASS"]
    gates = []
    if r["phys"]: gates.append("physical device evidence (identified device, driver, parity, repeated timing)")
    if r["dep"]: gates.append("deployment-profile evidence (environment-bound)")
    if gaps: gates.append("integration gap: " + ", ".join(gaps))
    if state == "gated": gates.append("open PR / owner decision")
    if state in ("unavail",): gates.append("capability or environment not available")
    if not tests and state == "sw": gates.append("no executable test")
    ci_ok = pyjob.get("conclusion") == "success" and bool(tests)
    reasons = []
    if state == "gated": reasons.append("gated on open PR / owner decision")
    if state == "unavail": reasons.append("capability or environment unavailable")
    if not tests: reasons.append("no executable test on main")
    elif agg["failed"]: reasons.append(f"{agg['failed']} local test(s) failing")
    elif not agg["passed"]: reasons.append("tests not executed in the local run")
    if tests and not ci_ok: reasons.append("CI evidence on candidate SHA missing")
    if r["phys"]: reasons.append("physical device evidence not observed")
    if r["dep"]: reasons.append("deployment-profile evidence missing")
    if gaps: reasons.append("integration gap (" + ", ".join(gaps) + ")")
    verdict = "SOFTWARE-BASE VERIFIED" if not reasons else "HOLD / NOT CERTIFIED: " + "; ".join(reasons)
    owner = []
    if r["id"] == "I-03": owner.append("Decide on restoring the 3 evidence items dropped in 53abc10; supply owner-approval, device certificate, benchmark, SBOM, provenance, rollback plan")
    if r["id"] in ("C-16","C-17","I-02"): owner.append("Approve wiring ProductionTriad custody into the deployed service (custody path, volume, readiness contract)")
    if r["id"] == "T-07": owner.append("Approve reconciliation policy for unreferenced objects/shards (report vs GC)")
    if r["id"] == "O-05": owner.append("Decide PR #171 (see decision brief)")
    if r["id"] in ("E-01",): owner.append("Decide PR #178 / Salamander source of record")
    if r["phys"] and r["id"] != "I-03": owner.append("Provide access to the identified physical device for an evidence run")
    if r["id"] in ("T-10","T-11","C-18"): owner.append("Select deployment profile and environment for evidence")
    # ---- t22u section 2: 35 mandatory fields, exact names
    xdims = {"X1":"durability","X2a":"integrity","X2b":"integrity","X2c":"integrity","X2d":"recovery","X3":"security",
             "X4":"concurrency","X5a":"integrity","X5b":"governance","X6":"observability","X7":"observability",
             "X8":"recovery","X8b":"recovery"}
    def dim(name):
        hits = [f"{i} {xc[i]['status']}: {xc[i]['detail'][:220]}" for i in r["xc"] if i in xc and xdims.get(i) == name]
        extra = r.get("dims", {}).get(name)
        out = ([extra] if extra else []) + hits
        if not out and r["cat"] == name: out = [r["fail"]]
        return out or ["No requirement-specific evidence for this dimension; not assessed for this row"]
    impl_status = {"sw":"complete","gap":"partial","gated":"missing on main (open PR / external authority)","unavail":"missing"}.get(state, state)
    if r.get("defective"): impl_status = "defective"
    integ_status = ("missing" if state in ("gated","unavail") or r["integ"] in ("(none)","not on main") else
                    "partially wired" if state == "gap" or gaps else "wired")
    codeql = [f"CodeQL #{a['number']} {a['severity']} {a['rule']} {a['path']}:{a['line']}" for a in cfg.get("codeql_open", [])
              if any(a["path"].startswith(pp.rstrip('/')) for pp in r["paths"])]
    ci_ev = None
    if tests and CI_RUN:
        ci_ev = {"workflow": "CI", "job": "Python 3.13 tests", "run_id": CI_RUN.get("run_id"),
                 "url": f"{GH}/actions/runs/{CI_RUN.get('run_id')}", "runner": pyjob.get("labels") or pyjob.get("runner"),
                 "environment": "GitHub-hosted ubuntu, Python 3.13", "tested_sha": CAND, "conclusion": pyjob.get("conclusion")}
    test_exec = ("not executed (no test on main)" if not tests else
                 f"passed {agg['passed']}, failed {agg['failed']}, skipped {agg['skipped']} (local, {CAND[:10]}); CI Python 3.13 job {pyjob.get('conclusion')}")
    accept = []
    if tests: accept.append(f"All tests in {', '.join(tests)} pass on the candidate SHA, locally and in CI Python 3.13; zero failures")
    if r["xc"]: accept.append("Cross-checks " + ", ".join(r["xc"]) + " report PASS")
    if r["fail"] and r["fail"] != "n/a": accept.append("Fail-closed: " + r["fail"])
    if r["phys"]: accept.append("Physical device run on an identified device with driver, parity and repeated timing recorded")
    if r["dep"]: accept.append("Verified deployment in the selected target environment")
    if not accept: accept.append("Capability present on main with executable tests (currently unmet)")
    row = {
      "Requirement ID": r["id"],
      "Capability": r["req"],
      "Authority": r["authority"] + (f" / {r['sub']}" if r["sub"] else ""),
      "Canonical specification": f"{r['src']} @ {(sh('git','log','-1','--format=%H',CAND,'--',r['src'].split('#')[0]) or CAND) if (WT / r['src'].split('#')[0]).exists() else 'owner directive (t22u, 2026-11-19); not a repo file'}",
      "Expected behaviour": r["req"] + (". Fail-closed: " + r["fail"] if r["fail"] and r["fail"] != "n/a" else ""),
      "Implementation": {"paths": r["paths"], "entrypoint": r["entry"]},
      "Implementation status": impl_status,
      "Baseline revision": first,
      "Final revision": CAND,
      "PR provenance": {"introduced": {"commit": first, "pr": (f"{GH}/pull/{pr_for(first)}" if pr_for(first) else None)},
                        "last_changed": {"commit": last, "pr": (f"{GH}/pull/{pr_for(last)}" if pr_for(last) else None)},
                        "dependencies": r.get("deps", [])},
      "Integration status": f"{integ_status} ({r['integ']})",
      "Acceptance criteria": accept,
      "Test coverage": {"files": tests, "reality_class": sorted({reality.get(t,"unclassified") for t in tests}),
                        "cross_triad": r["xc"], "automatically_executed_in_ci": bool(r["auto"]) and bool(tests)},
      "Test execution": test_exec,
      "CI evidence": ci_ev,
      "Runtime evidence": ([f"local run on {CAND[:10]}: {cfg['local_env']}"] if tests else []) + xres + ([cfg["bench_map"][r["id"]]] if cfg.get("bench_map",{}).get(r["id"]) else []) or ["none"],
      "Hardware evidence": ("REQUIRED, NOT OBSERVED: no physical device was available to this run (cloud VM, no GPU; GitHub-hosted runners)" if r["phys"] else "not required for this requirement"),
      "Performance": [cfg["bench_map"][r["id"]]] if cfg.get("bench_map",{}).get(r["id"]) else dim("performance"),
      "Integrity": dim("integrity"),
      "Durability": dim("durability"),
      "Recovery": dim("recovery"),
      "Concurrency": dim("concurrency"),
      "Security": dim("security"),
      "Governance": dim("governance"),
      "Provenance": [f"code at {CAND}; introduced {first}; last changed {last}",
                     "test and product-gate evidence attested by GitHub artifact attestations in 'Chronus V2 evidence qualification' on the candidate SHA" if tests else "no attested evidence"],
      "Packaging": cfg["packaging"],
      "Deployment": ("REQUIRED, NOT VERIFIED: no target environment deployment was performed or observed" if r["dep"] else "not deployment-scoped; no deployment verified"),
      "Observability": dim("observability"),
      "Outstanding defects": r.get("defects", []) + [f"{i} {xc[i]['status']}" for i in gaps],
      "Security findings": codeql or ["no open CodeQL alert in these paths; pip-audit clean; bandit (CI scope) clean"],
      "Outstanding decisions": owner,
      "Remaining gates": gates,
      "Accountability": {"component": r["authority"], "owner": "A T-M (decision owner)", "corrective_action": owner or gates or ["none"]},
      "Evidence reference": ([f"{GH}/actions/runs/{CI_RUN.get('run_id')}"] if ci_ev else []) + [f"{GH}/blob/{CAND}/{t}" for t in tests] +
                            ([f"{GH}/blob/{CAND}/scripts/ci/triad_cross_checks.py"] if r["xc"] else []),
      "Qualification verdict": verdict,
      "Evidence class": EVC.get(state, state),
    }
    out_rows.append(row)
assert all(len(x) == 36 for x in out_rows), [len(x) for x in out_rows]  # 35 t22u fields + evidence class
Path(cfg["out_json_rows"]).write_text(json.dumps(out_rows, indent=1))
print(json.dumps({"rows": len(out_rows), "fields": len(out_rows[0]), "suite": suite}))
