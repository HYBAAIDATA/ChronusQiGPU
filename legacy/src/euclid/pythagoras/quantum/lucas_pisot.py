"""Exact Lucas/Pisot scaling contracts — canonical surface re-export.

The implementation lives in the declared ``lucas`` substrate package
(``lucas.pisot``); this module preserves the ``src.euclid`` import path so
existing research-surface consumers keep resolving.
"""

from lucas.pisot import (
    DOMAIN_SCALE_INDEX,
    HendrixSchedule,
    HendrixStructuredSearch,
    LucasPisotScale,
    SUPPORTED_SCALE_INDICES,
    operation_record,
    resolve_scale,
    scaled_budget,
)

__all__ = [
    "SUPPORTED_SCALE_INDICES",
    "DOMAIN_SCALE_INDEX",
    "LucasPisotScale",
    "resolve_scale",
    "scaled_budget",
    "operation_record",
    "HendrixSchedule",
    "HendrixStructuredSearch",
]
