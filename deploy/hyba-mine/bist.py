"""Deployment wrapper for the packaged mining known-answer self-test."""

from chronus.execution.mining_selftest import main, run

__all__ = ["main", "run"]

if __name__ == "__main__":
    raise SystemExit(main())
