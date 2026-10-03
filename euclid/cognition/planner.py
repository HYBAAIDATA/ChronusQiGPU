"""Hierarchical planning for the cognitive loop.

Re-exports the deterministic reference planner from baselines; the planner
is intentionally small at this stage and derives goal DAGs from the declared
goal plus world-model state.  Evidence-driven cost/depth learning is the
meta-controller's job upstream.
"""
from .baselines import HierarchicalPlanner

__all__ = ["HierarchicalPlanner"]
