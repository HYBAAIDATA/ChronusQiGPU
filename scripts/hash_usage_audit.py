"""Advisory hash-usage inventory. Never imports or rewrites scanned code."""

import argparse
import json
from pathlib import Path
import re
import subprocess


SOURCE_SUFFIXES = {".py", ".c", ".cc", ".cpp", ".h", ".hpp", ".js", ".ts", ".cl"}
PATTERNS = {
    "bucketing-review": re.compile(
        r"\b(?:hash\w*|h)\s*%\s*(?:\d+|[A-Za-z_]\w*)"
        r"|%\s*(?:bucket\w*|num_buckets)\b",
        re.IGNORECASE,
    ),
    "sha256-context-review": re.compile(r"\b(?:sha256|SHA256|sha256d)\b", re.IGNORECASE),
    "hmac-context": re.compile(r"\b(?:hmac|compare_digest)\b", re.IGNORECASE),
}


def scan_text(path, text):
    """Emit locations only; findings are review candidates, not vulnerabilities."""
    findings = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for category, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"path": path, "line": line_number, "category": category})
    return findings


def audit(root):
    root = Path(root).resolve()
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True
    )
    findings = []
    scanned = 0
    for raw_path in sorted(set(result.stdout.split(b"\0")) - {b""}):
        relative = raw_path.decode("utf-8")
        path = root / relative
        if path.suffix.lower() not in SOURCE_SUFFIXES or path.is_symlink():
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError("Tracked path escapes repository root")
        data = path.read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8")
        scanned += 1
        findings.extend(scan_text(relative, text))
    return {
        "advisory_only": True,
        "scope": "tracked source files; symlinks and binary files excluded",
        "files_scanned": scanned,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Scanned {report['files_scanned']} files; {len(report['findings'])} review locations")


if __name__ == "__main__":
    main()
