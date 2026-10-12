"""Issue a promotion receipt; repository state changes require a reviewed commit."""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.assert_gate_rollup import evaluate
from al_haras.cedr import evaluate as evaluate_cedr, read_json
from al_haras.promotion_gates import PromotionState
from al_haras.promotion_pipeline import Approval
from al_haras.promotion_pipeline import build_receipt

p = argparse.ArgumentParser()
p.add_argument("--subsystem", required=True)
p.add_argument("--target", required=True)
p.add_argument("--commit", required=True)
p.add_argument("--cedr-profile", required=True)
p.add_argument("--artifact", required=True, type=Path)
a = p.parse_args()
expected_profile = "mining-production" if a.target == "PRODUCTION" else "pilot-operations"
if a.cedr_profile != expected_profile:
    raise SystemExit("promotion blocked: CEDR profile does not cover target tier")
head = subprocess.run(
    ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
).stdout.strip()
if head != a.commit:
    raise SystemExit("promotion blocked: candidate differs from checkout")
cedr = evaluate_cedr(
    read_json(Path("governance/cedr.json")),
    root=Path.cwd(),
    profile_name=a.cedr_profile,
    commit=head,
    artifact=a.artifact,
)
Path("results").mkdir(exist_ok=True)
Path("results/cedr-decision.json").write_text(json.dumps(cedr, indent=2) + "\n")
if not cedr["eligible"]:
    raise SystemExit("promotion blocked: CEDR claims are not qualified")
key = os.environ.get("PROMOTION_SIGNING_KEY", "").encode()
if len(key) < 32:
    raise SystemExit("PROMOTION_SIGNING_KEY (>=32 bytes) required")
states = json.loads(Path("config/al-haras-promotion-evidence.json").read_text())["targets"]
current = PromotionState[states[a.subsystem]]
target = PromotionState[a.target]
approvals = []
for x in json.loads(Path("results/approvals/approvals.json").read_text()):
    approvals.append(
        Approval(
            x["subsystem"],
            PromotionState[x["from_state"]],
            PromotionState[x["to_state"]],
            x["approver_role"],
            x["approver_identity"],
            x["approved_at"],
            x["evidence_commit"],
            x["reason"],
            x["source_url"],
        )
    )
report = evaluate(Path("results"), expected_commit=a.commit)
if not report["passed"]:
    raise SystemExit("promotion blocked: incomplete or invalid gate evidence")
required = []
for pth in Path("results").glob("*.json"):
    x = json.loads(pth.read_text())
    if {"gate", "status"} <= x.keys():
        required.append(x)
receipt = build_receipt(
    a.subsystem, current, target, a.commit, required, approvals, key, cedr_decision=cedr
)
Path("results/promotion_receipt.json").write_text(
    json.dumps(
        receipt.__dict__, indent=2, default=lambda x: x.name if hasattr(x, "name") else x.__dict__
    )
)
print("Receipt issued; persist state through a separately reviewed repository change.")
