"""Resonance intelligence package: feedback, calibration, and credit assignment.

Modules in this package cooperate through relative imports (for example
``feedback_core`` wires ``causal_attribution`` and ``truth_calibration``
together), so this package requires an ``__init__.py`` to be importable as
a package rather than as loose top-level scripts.
"""
