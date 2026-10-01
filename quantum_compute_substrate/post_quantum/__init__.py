"""Post-quantum substrate: where the fold theory transcends CPTP quantum."""

from .agi_scale import AGIScale, AGIScalePoint, AGI_SCALE_LEVELS
from .beyond_quantum import (
    sorkin_third_order_interference,
    fold_cross_section,
    pr_box_correlator,
    beyond_tsirelson_fold_chsh,
    fold_information_capacity,
)

__all__ = [
    "AGIScale",
    "AGIScalePoint",
    "AGI_SCALE_LEVELS",
    "sorkin_third_order_interference",
    "fold_cross_section",
    "pr_box_correlator",
    "beyond_tsirelson_fold_chsh",
    "fold_information_capacity",
]
