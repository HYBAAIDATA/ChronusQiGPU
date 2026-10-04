"""Compatibility import for the canonical EUCLID delegation module.

Historical recovery tests and callers imported ``euclid_delegation`` from the
repository root. The maintained implementation lives at ``euclid.delegation``;
this module deliberately contains no second implementation.
"""
from euclid.delegation import *  # noqa: F401,F403
