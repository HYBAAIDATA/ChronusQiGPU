#!/usr/bin/env python3
import json, sys
from pathlib import Path
cfg = json.loads(Path(sys.argv[1]).read_text())
rows = json.loads(Path(cfg["out_json_rows"]).read_text())
xc = json.loads(Path(cfg["xchecks"]).read_text())
GH = "https://github.com/HYBAAIDATA/ChronusQiGPU"
CAND = cfg["candidate_sha"]; S = CAND[:10]
L = []
def w(x=""): L.append(x)
def cell(v):
    if v is None: return "—"
    if isinstance(v, bool): return "yes" if v else "no"
    if isinstance(v, list): return "<br>".join(str(i) for i in v) if v else "—"
    if isinstance(v, dict): return ", ".join(f"{k} {val}" for k, val in v.items())
    return str(v).replace("|", "\\|")

w("# Chronus–OVID–THESEUS production-readiness reconciliation")
w()
w(f"**Candidate release SHA:** [`{CAND}`]({GH}/commit/{CAND}) (`main` after #173, #176, #180, #182 and #183 merged)  ")
w(f"**Reconciled:** {cfg['date']} (Europe/London)  ")
w("**Method:** every row is checked against code on the candidate SHA, the full local test suite run on that SHA, CI runs whose `head_sha` equals that SHA, executable cross-triad checks (`scripts/ci/triad_cross_checks.py`), benchmarks run on SHA-pinned public data, and artifacts built from that SHA. Nothing is carried forward from older revisions. Historical evidence is cited only with its own revision.  ")
w("**This document is not a production certification.** It weakens, suppresses and redefines no gate. `PRODUCTION_QUALIFIED.json` is unchanged and still says `NOT_QUALIFIED`.")
w()
w("## 1. Verdicts")
w()
w("| Scope | Verdict | Basis |")
w("| --- | --- | --- |")
for v in cfg["verdicts"]:
    w(f"| {v['scope']} | **{v['verdict']}** | {v['basis']} |")
w()
w("Authority boundaries:")
w("- **CHRONUS/QiGPU** owns execution, scheduling, acceleration, the tensor engine and the fleet. The tensor engine stays inside CHRONUS.")
w("- **OVID** owns organisation, transformation, folding, materialisation, content addressing, lineage and integrity.")
w("- **THESEUS** owns custody, storage, reconstruction, replication, storage healing, recovery and provenance.")
w("- **Salamander** (system self-healing), **AL HARAS** (governance) and **PYTHIA** (SearchPlan) are external authorities and are not certified here.")
w()
w("## 2. Evidence classes used")
w()
w("| Class | Meaning in this document |")
w("| --- | --- |")
w("| PHYSICAL_DEVICE_OBSERVED | Observed on an identified physical device. **No row has this class:** nothing on this host or on GitHub-hosted runners counts as GPU or hardware evidence. |")
w("| SOFTWARE_VERIFIED | Maintained code executed by tests or checks on the candidate SHA, locally and in CI. |")
w("| AVAILABLE_NOT_EXECUTED | Implemented with a route to evidence, such as a macOS runner or a GPU host, but not executed for this SHA. |")
w("| UNAVAILABLE | No implementation or environment exists to produce the evidence. |")
w("| GATED | Waiting on an open PR, an external authority or an owner decision. |")
w()
w("## 3. CI attestation for the candidate SHA")
w()
w("| Workflow | Run | Event | Conclusion | Runner |")
w("| --- | --- | --- | --- | --- |")
for name, r in sorted(cfg["ci"].items()):
    w(f"| {name} | [{r['run_id']}]({GH}/actions/runs/{r['run_id']}) | {r.get('event','push')} | {r['conclusion']} | {r.get('runner_summary','')} |")
w()
q = cfg.get("qualification_verdict")
if q:
    w(f"Qualification verdict artifact (`ci-verdict.json`, run {q['run_id']}): **status `{q['status']}`**, profile `{q.get('deployment_profile')}`, gates {json.dumps(q.get('gates'))}, blockers {json.dumps(q.get('blockers'))}. This covers only the **software-base** profile. It does not cover enterprise, sovereign or hyperscaler profiles, external key custody, multi-region durability or physical devices.")
    w()
w(f"Local full suite on `{S}` ({cfg['local_env']}): **{cfg['local_suite']}**. Evidence gates `no_dressing --baseline`, `test_reality`, `quantum_naming` and `check_forbidden_claims`: {cfg['gates_summary']}.")
w()
w("## 4. Cross-triad checks (executed, not read from docs)")
w()
w(f"`python scripts/ci/triad_cross_checks.py` on `{S}`: **{xc['summary']}**. These are `SOFTWARE_VERIFIED` and say nothing about physical devices.")
w()
w("| ID | Check | Result | Observation |")
w("| --- | --- | --- | --- |")
for r in xc["results"]:
    w(f"| {r['id']} | {cell(r['requirement'])} | **{r['status']}** | {cell(r['detail'])} |")
w()
w("## 5. Status registers (kept separate; no aggregate percentage)")
w()
regs = cfg["registers"]
w("| # | Register | Yes | No / not established |")
w("| --- | --- | --- | --- |")
for i, (name, yes, no) in enumerate(regs, 1):
    w(f"| {i} | {name} | {', '.join(yes) or '—'} | {', '.join(no) or '—'} |")
w()
w("## 6. Traceability matrix")
w()
w("Every row carries all 35 mandatory fields from the owner's specification (Requirement ID through Qualification verdict), plus `Evidence class`. The full matrix is in [`TRIAD_RECONCILIATION.json`](TRIAD_RECONCILIATION.json). This table repeats the fields that drive decisions.")
w()
w("| ID | Authority | Capability | Impl. status | Integration | Evidence class | Test execution | Verdict |")
w("| --- | --- | --- | --- | --- | --- | --- | --- |")
for r in rows:
    w(f"| {r['Requirement ID']} | {cell(r['Authority'])} | {cell(r['Capability'])} | {r['Implementation status']} | {cell(r['Integration status'])} | {r['Evidence class']} | {cell(r['Test execution'])} | {cell(r['Qualification verdict'])} |")
w()
w("## 6a. Cross-triad integration reconciliation (owner spec, section 3)")
w()
w("| Item | Evidence on the candidate SHA | Status |")
w("| --- | --- | --- |")
for it, ev, st in cfg["xtriad"]:
    w(f"| {it} | {cell(ev)} | **{st}** |")
w()
w("## 7. Benchmarks measured on the candidate SHA (local software, not hardware)")
w()
for b in cfg["benchmarks"]:
    w(f"- {b}")
w()
w("## 8. Artifact manifest (built from the candidate SHA on this host)")
w()
w("| Artifact | Bytes | sha256 |")
w("| --- | --- | --- |")
for a in cfg["artifacts"]:
    w(f"| `{a['name']}` | {a['bytes']} | `{a['sha256']}` |")
w()
w(cfg["artifact_note"])
w()
w("## 9. Outstanding release gates and owner actions")
w()
for g in cfg["outstanding"]:
    w(f"- {g}")
w()
w("## 10. Software evidence versus physical evidence")
w()
for g in cfg["sw_vs_phys"]:
    w(f"- {g}")
w()
w("## 11. Closure evidence for this workstream")
w()
w("| PR | Purpose | Merge commit | Merged (UTC) | Checks on final head |")
w("| --- | --- | --- | --- | --- |")
for p in cfg["closure"]:
    w(f"| [#{p['n']}]({GH}/pull/{p['n']}) | {p['title']} | [`{p['mc'][:10]}`]({GH}/commit/{p['mc']}) | {p['merged']} | {p['checks']} |")
w()
w("## 12. Open PR recommendations (#171, #169, #168)")
w()
for p in cfg["open_prs"]:
    w(f"- {p}")
w()
w("## 13. Security posture on the candidate SHA")
w()
for p in cfg["security"]:
    w(f"- {p}")
w()
w("## 14. Final production admission verdict")
w()
w(cfg["admission"])
w()
Path(cfg["out_md"]).write_text("\n".join(L) + "\n")
doc = {"schema": "chronus-triad-reconciliation-v1", "candidate_sha": CAND, "reconciled": cfg["date"],
       "verdicts": cfg["verdicts"], "ci": cfg["ci"], "qualification_verdict": cfg.get("qualification_verdict"),
       "local_suite": cfg["local_suite"], "cross_triad_checks": xc, "registers": [{"register": n, "yes": y, "no": no} for n, y, no in regs],
       "matrix_fields": list(rows[0].keys()), "cross_triad_reconciliation": [{"item": a, "evidence": b, "status": c} for a, b, c in cfg["xtriad"]], "admission": cfg["admission"], "matrix": rows, "artifacts": cfg["artifacts"], "outstanding_gates": cfg["outstanding"],
       "closure": cfg["closure"]}
Path(cfg["out_json"]).write_text(json.dumps(doc, indent=1) + "\n")
print("rendered", len(L), "lines")
