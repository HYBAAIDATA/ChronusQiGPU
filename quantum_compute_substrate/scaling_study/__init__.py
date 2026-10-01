"""Scaling studies beyond phi^37 (institutional-grade).

Provides systematic scaling analysis: dimension vs. runtime, dimension vs.
reconstruction fidelity, dimension vs. norm-preservation error. Fits a log-log
exponent and reports 95%% CI from residual variance.
"""

from .beyond_phi37 import ScalingStudy, ScalingResult

__all__ = ["ScalingStudy", "ScalingResult"]
