#!/usr/bin/env python3
"""Assemble cfg for gen.py/render.py from the candidate run directory and live gh data."""
import json, subprocess, sys, os, re
from pathlib import Path
CAND = sys.argv[1]; D = Path(sys.argv[2]); OUTDIR = Path(sys.argv[3]); EXTRA = json.loads(Path(sys.argv[4]).read_text())
REPO = "HYBAAIDATA/ChronusQiGPU"
def reject(msg): sys.exit(f"build_cfg: rejected evidence for {CAND}: {msg}")
# provenance: every evidence input must be bound to the candidate SHA
env_sha = next((l.split("=", 1)[1].strip() for l in (D / "env.txt").read_text().splitlines() if l.startswith("sha=")), None)
if env_sha != CAND: reject(f"env.txt records sha={env_sha}")
xc_sha = json.loads((D / "xchecks.json").read_text()).get("git_sha")
if xc_sha != CAND: reject(f"xchecks.json records git_sha={xc_sha}")
wt_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=os.environ.get("WT", "/workspace/closeout-cand"), capture_output=True, text=True).stdout.strip()
if wt_head != CAND: reject(f"worktree HEAD is {wt_head}")
# every recorded required step must have exited 0
failed = []
for l in (D / "gates.txt").read_text().splitlines():
    m = re.search(r"exit[= ](\d+)", l)
    if m and m.group(1) != "0": failed.append(l.strip())
pe = [l for l in (D / "pytest.txt").read_text().splitlines() if l.startswith("pytest exit ")]
if not pe or pe[-1].split()[-1] != "0": failed.append(pe[-1] if pe else "pytest exit not recorded")
if failed: reject("failed or unrecorded required steps: " + "; ".join(failed))
def gh(*a):
    return subprocess.run(["gh", *a], capture_output=True, text=True).stdout
runs = json.loads(gh("run", "list", "-R", REPO, "--commit", CAND, "--limit", "100", "--json", "databaseId,workflowName,conclusion,status,event,headSha"))
ci = {}
for r in runs:
    if r["headSha"] != CAND or r["event"] != "push": continue
    name = r["workflowName"]
    if name in ci: continue
    jobs = json.loads(gh("api", f"repos/{REPO}/actions/runs/{r['databaseId']}/jobs?per_page=100")).get("jobs", [])
    jl = {j["name"]: {"conclusion": j["conclusion"], "runner": j.get("runner_name"), "labels": j.get("labels")} for j in jobs}
    labels = sorted({l for j in jobs for l in (j.get("labels") or [])})
    ci[name] = {"run_id": r["databaseId"], "conclusion": r["conclusion"] or r["status"], "event": r["event"],
                "runner_summary": "GitHub-hosted: " + ", ".join(labels) if labels else "", "jobs": jl}
env = (D / "env.txt").read_text().split("\n")
suite = [l for l in (D / "pytest.txt").read_text().splitlines() if " passed" in l][-1].strip()
gates = (D / "gates.txt").read_text().strip().replace("\n", "; ")
cfg = {"candidate_sha": CAND, "worktree": os.environ.get("WT", "/workspace/closeout-cand"), "junit": str(D / "junit.xml"), "xchecks": str(D / "xchecks.json"),
       "ci": ci, "local_env": f"{env[1]}, {env[2]}, SQLite {env[3].split()[-1]}, {env[4]} logical CPUs (cloud VM, no GPU)",
       "local_suite": suite, "gates_summary": gates, "out_json_rows": str(OUTDIR / "rows.json"),
       "out_md": str(OUTDIR / "TRIAD_RECONCILIATION.md"), "out_json": str(OUTDIR / "TRIAD_RECONCILIATION.json")}
cfg.update(EXTRA)
Path(OUTDIR / "cfg.json").write_text(json.dumps(cfg, indent=1))
print(json.dumps({k: (v["conclusion"], v["run_id"]) for k, v in ci.items()}, indent=0))
