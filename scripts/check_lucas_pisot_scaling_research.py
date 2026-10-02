"""One-command deterministic Lucas/Pisot research closure."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucas.scaling_research import research_report, verify_content_sha256
RESULT = ROOT / "artifacts" / "lucas-pisot-scaling-research.json"


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_lucas_pisot_scaling_research", "-v"],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode:
        return completed.returncode
    report = research_report()
    if not verify_content_sha256(report):
        raise AssertionError("canonical report digest failed self-verification")
    RESULT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"LUCAS_PISOT_RESEARCH=PASS artifact={RESULT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
