"""Fail closed unless GitHub verified an annotated release tag at this commit."""

from __future__ import annotations

import json
import os
import re
import subprocess


def validate_tag(name: str, reference: dict, tag: dict, commit: str) -> None:
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", name):
        raise ValueError("release tag must be vMAJOR.MINOR.PATCH without leading zeros")
    ref_object = reference.get("object", {})
    if ref_object.get("type") != "tag" or ref_object.get("sha") != tag.get("sha"):
        raise ValueError("release requires an annotated tag with matching identity")
    verification = tag.get("verification", {})
    if verification.get("verified") is not True or verification.get("reason") != "valid":
        raise ValueError("GitHub has not verified the release tag signature")
    target = tag.get("object", {})
    if tag.get("tag") != name or target.get("type") != "commit" or target.get("sha") != commit:
        raise ValueError("signed tag does not identify this release commit")


def github_json(path: str) -> dict:
    result = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    name = os.environ["GITHUB_REF_NAME"]
    commit = os.environ["GITHUB_SHA"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("invalid repository identity")
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", name):
        raise ValueError("invalid release tag")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid release commit identity")
    reference = github_json(f"repos/{repository}/git/ref/tags/{name}")
    tag_sha = reference.get("object", {}).get("sha", "")
    if reference.get("object", {}).get("type") != "tag" or not re.fullmatch(
        r"[0-9a-f]{40}", tag_sha
    ):
        raise ValueError("release tag must be annotated")
    tag = github_json(f"repos/{repository}/git/tags/{tag_sha}")
    validate_tag(name, reference, tag, commit)
    # Release only commits already incorporated into the default production branch.
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"], check=True)
    print(f"PASS — verified signed release tag {name} at {commit}")


if __name__ == "__main__":
    main()
