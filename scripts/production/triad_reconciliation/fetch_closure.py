#!/usr/bin/env python3
"""Write closure.json: every PR merged into main since the closeout began, with checks on its final head."""
import json, subprocess, sys
from collections import Counter
SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-11-19T01:00:00Z"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/workspace/closeout-data/closure.json"
MINE = {180: "this stream", 182: "this stream", 183: "this stream", 186: "this stream"}
raw = subprocess.run(["gh", "pr", "list", "-R", "HYBAAIDATA/ChronusQiGPU", "--state", "merged", "--base", "main", "-L", "15",
                      "--json", "number,title,mergeCommit,mergedAt,headRefOid,statusCheckRollup"], capture_output=True, text=True, check=True).stdout
out = []
for p in json.loads(raw):
    if p["mergedAt"] < SINCE:
        continue
    c = Counter((x.get("conclusion") or x.get("state") or "").lower() for x in p["statusCheckRollup"])
    out.append({"n": p["number"], "title": p["title"] + ("" if p["number"] in MINE else " (other stream)"),
                "mc": p["mergeCommit"]["oid"], "merged": p["mergedAt"].replace("T", " ").rstrip("Z"),
                "checks": ", ".join(f"{v} {k}" for k, v in sorted(c.items())) + f" (head {p['headRefOid'][:8]})"})
out.sort(key=lambda p: p["merged"])
json.dump(out, open(OUT, "w"), indent=1)
print(len(out), "merged PRs:", [p["n"] for p in out])
