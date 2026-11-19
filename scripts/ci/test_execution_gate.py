"""Fail CI unless the test suite actually executed.

A green pytest exit code is not evidence on its own: a run where tests were
skipped, deselected or never collected also exits 0. This gate reads the JUnit
XML that pytest wrote and fails when

* any test failed or errored,
* fewer tests passed than the suite's recorded floor (tests silently vanished),
* a test was skipped for a reason the policy does not allow (only hardware,
  platform and pinned optional-dependency skips are allowed; each of those is
  executed by a dedicated job or is platform-specific), or
* a test is an expected failure (xfail) that is not recorded in
  tests/known-failures.txt.

Usage: python scripts/ci/test_execution_gate.py --suite main --junit junit.xml
Exit codes: 0 executed as required, 1 gate failed, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

POLICY = Path(__file__).with_name("test_execution_policy.json")


def _cases(junit: Path):
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    for suite in suites:
        yield from suite.iter("testcase")


def classify(junit: Path) -> dict:
    counts: Counter[str] = Counter()
    skips: list[tuple[str, str]] = []
    xfails: list[tuple[str, str]] = []
    for case in _cases(junit):
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        if case.find("failure") is not None:
            counts["failed"] += 1
        elif case.find("error") is not None:
            counts["errors"] += 1
        elif (skip := case.find("skipped")) is not None:
            # Module-level skips carry the reason in the element text and the
            # generic message "collection skipped" in the attribute.
            message = " ".join(x for x in (skip.get("message", ""), (skip.text or "").strip()) if x)
            if skip.get("type") == "pytest.xfail":
                counts["xfailed"] += 1
                xfails.append((name, message))
            else:
                counts["skipped"] += 1
                skips.append((name, message))
        else:
            counts["passed"] += 1
    return {"counts": dict(counts), "skips": skips, "xfails": xfails}


def evaluate(result: dict, policy: dict) -> list[str]:
    problems = []
    counts = result["counts"]
    for key in ("failed", "errors"):
        if counts.get(key, 0):
            problems.append(f"{counts[key]} test(s) {key}")
    floor = int(policy["min_passed"])
    if counts.get("passed", 0) < floor:
        problems.append(f"only {counts.get('passed', 0)} tests passed; the suite floor is {floor}")
    allowed = [re.compile(p) for p in policy.get("allowed_skip_reasons", [])]
    for name, message in result["skips"]:
        if not any(p.search(message) for p in allowed):
            problems.append(f"unexpected skip: {name}: {message!r}")
    if len(result["skips"]) > int(policy.get("max_skipped", 0)):
        problems.append(f"{len(result['skips'])} skips exceed the policy maximum {policy['max_skipped']}")
    for name, message in result["xfails"]:
        if "known-failures.txt" not in message:
            problems.append(f"xfail not recorded in tests/known-failures.txt: {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", required=True)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--policy", type=Path, default=POLICY)
    args = parser.parse_args(argv)
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))["suites"][args.suite]
        result = classify(args.junit)
    except (OSError, KeyError, ValueError, ET.ParseError) as exc:
        print(f"test-execution gate: cannot evaluate: {exc}", file=sys.stderr)
        return 2
    problems = evaluate(result, policy)
    c = result["counts"]
    line = (f"suite={args.suite} passed={c.get('passed', 0)} failed={c.get('failed', 0)} "
            f"errors={c.get('errors', 0)} skipped={c.get('skipped', 0)} xfailed={c.get('xfailed', 0)} "
            f"floor={policy['min_passed']}")
    print(line)
    labels = Counter(re.sub(r"\s\(?'?/\S+.*$", "", m) for _, m in result["skips"])
    for reason, n in labels.most_common():
        print(f"  skipped x{n}: {reason}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Test execution ({args.suite})\n\n`{line}`\n\n")
            for p in problems:
                fh.write(f"- FAIL: {p}\n")
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
