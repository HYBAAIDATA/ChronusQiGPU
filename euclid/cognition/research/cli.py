"""Console entry point: run the EUCLID v17 research programme."""
from __future__ import annotations

import argparse
from pathlib import Path

from .programme import ProgrammeConfig, run_programme, write_report
from .report import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="euclid-v17-research", description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("euclid_v17_report"))
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--suite-base", type=int, default=2000,
                        help="2000 is the pre-registered evaluation base")
    args = parser.parse_args(argv)
    config = ProgrammeConfig(seeds=tuple(range(args.seeds)), workers=args.workers,
                             suite_base=args.suite_base)
    report = run_programme(config, progress=lambda line: print(line, flush=True))
    args.output.mkdir(parents=True, exist_ok=True)
    write_report(report, str(args.output / "research_report.json"))
    (args.output / "research_report.md").write_text(render(report), encoding="utf-8")
    print(f"RELEASE_GATE={'PASSED' if report['release_gate']['passed'] else 'NOT_PASSED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
