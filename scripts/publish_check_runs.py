"""Publish file-backed gate results to GitHub Checks and commit status APIs."""

import json
import os
import urllib.request
from pathlib import Path

try:
    from scripts.gate_runner import canonical_digest
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from gate_runner import canonical_digest

try:
    from scripts.assert_gate_rollup import evaluate, read_json
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from assert_gate_rollup import evaluate, read_json


def post(url, token, body):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def main():
    required = ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_API_URL")
    env = {k: os.environ.get(k) for k in required}
    if not all(env.values()):
        raise SystemExit("missing GitHub publication environment")
    report = evaluate(Path("results"), expected_commit=env["GITHUB_SHA"])
    results = []
    for gate in report["observed"]:
        try:
            result = read_json(Path("results") / f"{gate}.json")
            if canonical_digest(result) != report["evidence_digests"][gate]:
                raise ValueError("evidence changed after validation")
            results.append(result)
        except (OSError, ValueError, TypeError):
            report["passed"] = False
    api = env["GITHUB_API_URL"].rstrip("/")
    repo = env["GITHUB_REPOSITORY"]
    sha = env["GITHUB_SHA"]
    token = env["GITHUB_TOKEN"]
    conclusions = {"PASS": "success", "FAIL": "failure", "SKIP": "skipped", "NOT_RUN": "neutral", "ERROR": "failure"}
    for r in results:
        if r["gate"] not in report["observed"]:
            continue
        post(
            f"{api}/repos/{repo}/check-runs",
            token,
            {
                "name": r["gate"],
                "head_sha": sha,
                "status": "completed",
                "conclusion": conclusions[r["status"]],
                "output": {
                    "title": r["gate"],
                    "summary": r["reason"],
                    "text": "\n".join(r.get("artifacts", ()))[:65000],
                },
            },
        )
    state = "success" if report["passed"] else "failure"
    post(
        f"{api}/repos/{repo}/statuses/{sha}",
        token,
        {
            "state": state,
            "description": "Complete commit-bound assurance gates passed" if report["passed"]
            else "Incomplete or invalid mandatory assurance evidence",
            "context": "chronus/mla1517/gates",
        },
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
