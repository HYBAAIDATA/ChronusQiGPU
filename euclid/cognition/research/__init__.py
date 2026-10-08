"""EUCLID v17 research programme: pre-registered, ablated, repeated-seed evaluation.

See :mod:`.programme` for the protocol, :mod:`.stats` for the statistics and
:mod:`.report` for the Markdown rendering.  Nothing here is imported by the
agent; evaluation code reads hidden truth only to score outcomes.
"""
from .programme import EVAL_SLICES, ProgrammeConfig, run_programme
from .stats import brier, expected_calibration_error, paired_bootstrap, t_interval, wilson

__all__ = [
    "EVAL_SLICES",
    "ProgrammeConfig",
    "brier",
    "expected_calibration_error",
    "paired_bootstrap",
    "run_programme",
    "t_interval",
    "wilson",
]
