"""Collect approved PR reviews and enforce role mapping/SOD for target SHA."""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from al_haras.promotion_gates import PromotionState
from al_haras.promotion_pipeline import Approval
from al_haras.promotion_pipeline import enforce_sod

p = argparse.ArgumentParser()
p.add_argument("--subsystem", required=True)
p.add_argument("--target", required=True)
p.add_argument("--commit", required=True)
p.add_argument("--authors", required=True)
a = p.parse_args()
token = os.environ.get("GITHUB_TOKEN")
repo = os.environ.get("GITHUB_REPOSITORY")
api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
if not token or not repo:
    raise SystemExit("GitHub API environment required")


def get(url):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    return json.loads(urllib.request.urlopen(req).read())


prs = get(f"{api}/repos/{repo}/commits/{a.commit}/pulls")
if not prs:
    raise SystemExit("target commit is not associated with a pull request")
reviews = get(f"{api}/repos/{repo}/pulls/{prs[0]['number']}/reviews")
roles = json.loads(Path("config/promotion-roles.json").read_text())
states = json.loads(Path("config/al-haras-promotion-evidence.json").read_text())["targets"]
current = PromotionState[states[a.subsystem]]
target = PromotionState[a.target]
approvals = []
for review in reviews:
    if review.get("state") != "APPROVED":
        continue
    login = review["user"]["login"]
    matched = [role for role, members in roles.items() if login in members]
    for role in matched:
        approvals.append(
            Approval(
                a.subsystem,
                current,
                target,
                role,
                login,
                int(
                    __import__("datetime")
                    .datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00"))
                    .timestamp()
                ),
                a.commit,
                review.get("body") or "approved",
                review["html_url"],
            )
        )
valid = enforce_sod(
    a.subsystem,
    current,
    target,
    a.commit,
    json.loads(a.authors),
    approvals,
    {k: set(v) for k, v in roles.items()},
)
out = Path("results/approvals")
out.mkdir(parents=True, exist_ok=True)
(out / "approvals.json").write_text(
    json.dumps(
        [
            x.__dict__ | {"from_state": x.from_state.name, "to_state": x.to_state.name}
            for x in valid
        ],
        indent=2,
    )
)
