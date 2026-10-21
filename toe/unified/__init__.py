"""Unified analytics platform.

One runtime for the capabilities the TOE package was built to carry:
connectors, a single data layer, tensor models, business intelligence,
operations, the cost model, and the scholarship ledger.
"""

from .platform import UnifiedAnalyticsPlatform
from .tenancy import TenantGateway, TenantResult, TenantSession

__all__ = ["UnifiedAnalyticsPlatform", "TenantGateway", "TenantSession", "TenantResult"]
