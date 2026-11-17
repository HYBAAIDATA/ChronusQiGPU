# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Start-at-login entry point for Windows Task Scheduler and systemd.

Task Scheduler cannot set environment variables for a task, so the task runs
``python -m hyba_mine.launch --home <dir> --logs <dir>``; this module sets
``HYBA_MINE_HOME`` / ``HYBA_MINE_LOG_DIR`` and then runs ``hyba-mine start``,
which always runs the pre-flight before mining (the same contract as
``scripts/mine/run.sh`` on macOS).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hyba_mine.launch")
    parser.add_argument("--home", required=True)
    parser.add_argument("--logs", required=True)
    args, rest = parser.parse_known_args(argv)
    os.environ["HYBA_MINE_HOME"] = args.home
    os.environ["HYBA_MINE_LOG_DIR"] = args.logs
    from hyba_mine.cli import main as cli_main

    return cli_main(["start", *rest])


if __name__ == "__main__":
    sys.exit(main())
