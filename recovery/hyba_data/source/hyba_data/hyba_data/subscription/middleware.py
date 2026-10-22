"""
HYBA_DATA Tier-Based API Middleware

Enforces quotas and features based on subscription tier.
Adapted for standard-library deployment (no FastAPI required).

Author: Andre Taylor-Morris - HYBA Software Ltd
"""
from typing import Any, Callable, Dict, Optional
from .tiers import (
    Tier, TierDefinition, TIER_DEFINITIONS, TIER_ORDER,
    get_tier_by_name, get_min_tier_for_feature, tier_meets_requirement,
)
from .service import SubscriptionService


class TierMiddleware:
    """Middleware to enforce tier-based access."""

    def __init__(self, subscription_service: SubscriptionService):
        self.subscription_service = subscription_service

    def check_feature(self, user_id: str, feature: str) -> Dict[str, Any]:
        """Check if user's tier supports a feature."""
        sub = self.subscription_service.get_subscription(user_id)
        tier_name = sub.get("tier", "free")
        tier_def = get_tier_by_name(tier_name)
        if not tier_def:
            return {"allowed": False, "reason": f"Unknown tier: {tier_name}"}

        if not getattr(tier_def.features, feature, False):
            min_tier = get_min_tier_for_feature(feature)
            return {
                "allowed": False,
                "reason": f"Feature '{feature}' requires {min_tier} tier or higher",
                "current_tier": tier_name,
                "min_tier": min_tier,
            }
        return {"allowed": True, "tier": tier_name}

    def check_quota(self, user_id: str, metric: str, amount: int = 1) -> Dict[str, Any]:
        """Check and consume quota for a metric."""
        return self.subscription_service.check_usage(user_id, metric, amount)

    def check_tier(self, user_id: str, min_tier: str) -> Dict[str, Any]:
        """Check if user's tier meets minimum requirement."""
        sub = self.subscription_service.get_subscription(user_id)
        current_tier = sub.get("tier", "free")
        if not tier_meets_requirement(current_tier, min_tier):
            return {
                "allowed": False,
                "reason": f"Requires {min_tier} tier or higher",
                "current_tier": current_tier,
                "min_tier": min_tier,
            }
        return {"allowed": True, "tier": current_tier}

    def get_tier_headers(self, user_id: str) -> Dict[str, str]:
        """Get tier info headers for API response."""
        sub = self.subscription_service.get_subscription(user_id)
        tier_name = sub.get("tier", "free")
        tier_def = get_tier_by_name(tier_name)
        headers = {"X-Tier": tier_name}
        if tier_def:
            headers["X-Tier-Name"] = tier_def.name
            usage = sub.get("usage", {})
            api_usage = usage.get("api_calls_per_month", {})
            remaining = tier_def.quota.api_calls_per_month - api_usage.get("used", 0)
            headers["X-API-Usage-Remaining"] = str(remaining)
        return headers


def require_feature(feature: str):
    """Decorator factory to require a specific feature."""
    def decorator(func: Callable) -> Callable:
        def wrapper(subscription_service: SubscriptionService, user_id: str, *args, **kwargs):
            middleware = TierMiddleware(subscription_service)
            result = middleware.check_feature(user_id, feature)
            if not result["allowed"]:
                return {"status": 403, "error": result["reason"]}
            return func(subscription_service, user_id, *args, **kwargs)
        wrapper.__wrapped__ = func
        wrapper._required_feature = feature
        return wrapper
    return decorator


def require_quota(metric: str, amount: int = 1):
    """Decorator factory to check and consume quota."""
    def decorator(func: Callable) -> Callable:
        def wrapper(subscription_service: SubscriptionService, user_id: str, *args, **kwargs):
            result = subscription_service.check_usage(user_id, metric, amount)
            if not result["allowed"]:
                return {
                    "status": 429,
                    "error": f"Quota exceeded for {metric}. Limit: {result['limit']}, Used: {result['usage']}",
                }
            return func(subscription_service, user_id, *args, **kwargs)
        wrapper.__wrapped__ = func
        wrapper._quota_metric = metric
        return wrapper
    return decorator


def require_tier(min_tier: str):
    """Decorator factory to require a minimum tier."""
    def decorator(func: Callable) -> Callable:
        def wrapper(subscription_service: SubscriptionService, user_id: str, *args, **kwargs):
            middleware = TierMiddleware(subscription_service)
            result = middleware.check_tier(user_id, min_tier)
            if not result["allowed"]:
                return {"status": 403, "error": result["reason"]}
            return func(subscription_service, user_id, *args, **kwargs)
        wrapper.__wrapped__ = func
        wrapper._min_tier = min_tier
        return wrapper
    return decorator
