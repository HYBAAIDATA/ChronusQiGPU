"""Run the pre-registered EUCLID v17 research programme and write the report.

Usage::

    python scripts/run_euclid_v17_research.py --output reports/euclid_v17

Writes ``research_report.json`` (every episode row, every interval) and
``research_report.md``.  Exit status 0 means the programme completed; the
release-gate verdict is reported, not enforced, so negative results are kept.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from euclid.cognition.research.programme import (  # noqa: E402
    ProgrammeConfig,
    run_programme,
    write_report,
)
from euclid.cognition.research.report import render  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "euclid_v17")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    config = ProgrammeConfig(seeds=tuple(range(args.seeds)), workers=args.workers)
    report = run_programme(config, progress=lambda line: print(line, flush=True))
    args.output.mkdir(parents=True, exist_ok=True)
    write_report(report, str(args.output / "research_report.json"))
    (args.output / "research_report.md").write_text(render(report), encoding="utf-8")
    gate = report["release_gate"]
    print(f"REPORT={args.output / 'research_report.md'}")
    print(f"RELEASE_GATE={'PASSED' if gate['passed'] else 'NOT_PASSED'}")
    print(f"LEAKAGE_FREE={report['leakage_free']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
