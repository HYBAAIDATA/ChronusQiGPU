# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""``python -m hyba_mine`` runs the ``hyba-mine`` command line."""

import sys

from hyba_mine.cli import main

if __name__ == "__main__":  # spawn-started worker processes must not re-run the CLI
    sys.exit(main())
