"""
HYBA_DATA Subscription Service

Complete subscription, billing, and usage management.
Adapted for standard-library deployment (no Stripe/asyncpg required).
Uses in-memory storage for demo; production uses PostgreSQL.

Author: Andre Taylor-Morris - HYBA Software Ltd
"""
import time
import uuid
import hashlib
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from .tiers import (
    Tier, BillingPeriod, TierQuota, TierFeatures, Pricing,
    TierDefinition, TIER_DEFINITIONS, TIER_ORDER,
    get_tier_by_name, tier_meets_requirement,
)


@dataclass
class Subscription:
    """Subscription record."""
    id: str
    user_id: str
    tenant_id: str
    tier: str
    status: str = "active"
    billing_period: str = "monthly"
    start_date: float = 0.0
    end_date: float = 0.0
    trial_end_date: Optional[float] = None
    auto_renew: bool = True
    plan_name: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tier": self.tier,
            "status": self.status,
            "billing_period": self.billing_period,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "auto_renew": self.auto_renew,
            "plan_name": self.plan_name,
        }


@dataclass
class UsageRecord:
    """Usage tracking record."""
    subscription_id: str
    metric_name: str
    used_amount: int = 0
    quota_limit: int = 0
    period_start: float = 0.0
    period_end: float = 0.0

    @property
    def remaining(self) -> int:
        return max(0, self.quota_limit - self.used_amount)

    @property
    def percent(self) -> float:
        return (self.used_amount / self.quota_limit * 100) if self.quota_limit > 0 else 0.0


@dataclass
class Invoice:
    """Invoice record."""
    id: str
    subscription_id: str
    user_id: str
    invoice_number: str
    status: str = "draft"
    amount: float = 0.0
    currency: str = "USD"
    tax_amount: float = 0.0
    discount_amount: float = 0.0
    due_date: float = 0.0
    paid_date: Optional[float] = None
    created_at: float = 0.0

    @property
    def total(self) -> float:
        return self.amount + self.tax_amount - self.discount_amount


class SubscriptionService:
    """
    Complete subscription management service.
    Uses in-memory storage for demo; production uses PostgreSQL.
    """

    PERIOD_DAYS = {
        "monthly": 30,
        "quarterly": 90,
        "annual": 365,
    }

    def __init__(self):
        self._subscriptions: Dict[str, Subscription] = {}
        self._usage: Dict[str, Dict[str, UsageRecord]] = {}
        self._invoices: Dict[str, Invoice] = {}
        self._usage_events: List[Dict[str, Any]] = []
        self._audit_log: List[Dict[str, Any]] = []
        self.tiers = TIER_DEFINITIONS

    def get_tier(self, tier: Tier) -> TierDefinition:
        return self.tiers[tier]

    def list_tiers(self, include_private: bool = False) -> List[TierDefinition]:
        return [t for t in self.tiers.values() if t.is_public or include_private]

    def create_subscription(self, user_id: str, tier: Tier,
                            billing_period: str = "monthly") -> Dict[str, Any]:
        tier_def = self.tiers[tier]
        now = time.time()
        days = self.PERIOD_DAYS.get(billing_period, 30)
        end_date = now + days * 86400

        sub_id = str(uuid.uuid4())
        sub = Subscription(
            id=sub_id,
            user_id=user_id,
            tenant_id=user_id,
            tier=tier.value,
            status="active",
            billing_period=billing_period,
            start_date=now,
            end_date=end_date,
            plan_name=f"{tier.value}_{billing_period}",
            created_at=now,
            updated_at=now,
        )
        self._subscriptions[sub_id] = sub

        self._initialize_usage(sub_id, tier_def, now, end_date)

        self._audit("subscription_create", user_id, sub_id, {
            "tier": tier.value, "billing_period": billing_period,
        })

        return {
            "subscription_id": sub_id,
            "tier": tier.value,
            "status": "active",
            "start_date": now,
            "end_date": end_date,
            "features": self._features_to_dict(tier_def.features),
            "quota": self._quota_to_dict(tier_def.quota),
        }

    def get_subscription(self, user_id: str) -> Dict[str, Any]:
        for sub in self._subscriptions.values():
            if sub.user_id == user_id and sub.status == "active":
                usage = self._get_usage(sub.id)
                tier_def = self.tiers.get(Tier(sub.tier))
                return {
                    "subscription_id": sub.id,
                    "tier": sub.tier,
                    "status": sub.status,
                    "start_date": sub.start_date,
                    "end_date": sub.end_date,
                    "days_remaining": max(0, int((sub.end_date - time.time()) / 86400)),
                    "auto_renew": sub.auto_renew,
                    "usage": usage,
                    "features": self._features_to_dict(tier_def.features) if tier_def else {},
                    "quota": self._quota_to_dict(tier_def.quota) if tier_def else {},
                }
        return {"status": "no_subscription", "tier": "free"}

    def update_tier(self, user_id: str, new_tier: Tier,
                   billing_period: str = "monthly") -> Dict[str, Any]:
        current = self.get_subscription(user_id)
        if current["status"] == "no_subscription":
            return self.create_subscription(user_id, new_tier, billing_period)

        sub_id = current["subscription_id"]
        sub = self._subscriptions[sub_id]
        old_tier = sub.tier
        sub.tier = new_tier.value
        sub.billing_period = billing_period
        sub.updated_at = time.time()

        tier_def = self.tiers[new_tier]
        self._initialize_usage(sub_id, tier_def, time.time(),
                               time.time() + self.PERIOD_DAYS.get(billing_period, 30) * 86400)

        self._audit("subscription_update", user_id, sub_id, {
            "old_tier": old_tier, "new_tier": new_tier.value,
        })

        return {
            "subscription_id": sub_id,
            "tier": new_tier.value,
            "status": "updated",
            "features": self._features_to_dict(tier_def.features),
            "quota": self._quota_to_dict(tier_def.quota),
        }

    def cancel_subscription(self, user_id: str, immediate: bool = False) -> Dict[str, Any]:
        current = self.get_subscription(user_id)
        if current["status"] == "no_subscription":
            return {"error": "No subscription to cancel"}

        sub_id = current["subscription_id"]
        sub = self._subscriptions[sub_id]
        sub.status = "canceled"
        end_date = time.time() if immediate else sub.end_date
        sub.end_date = end_date
        sub.updated_at = time.time()

        self._audit("subscription_cancel", user_id, sub_id, {
            "immediate": immediate, "end_date": end_date,
        })

        return {
            "subscription_id": sub_id,
            "status": "canceled",
            "end_date": end_date,
        }

    def check_usage(self, user_id: str, metric: str, amount: int = 1) -> Dict[str, Any]:
        sub = self.get_subscription(user_id)
        if sub["status"] == "no_subscription":
            tier = Tier.FREE
        else:
            tier = Tier(sub["tier"])

        tier_def = self.tiers[tier]
        quota_limit = getattr(tier_def.quota, metric, 0)
        sub_id = sub.get("subscription_id")
        usage = self._get_usage_metric(sub_id, metric)

        if usage >= quota_limit:
            return {
                "allowed": False,
                "metric": metric,
                "usage": usage,
                "limit": quota_limit,
                "percent": (usage / quota_limit * 100) if quota_limit > 0 else 0,
            }

        self._record_usage(sub_id, metric, amount)

        return {
            "allowed": True,
            "metric": metric,
            "usage": usage + amount,
            "limit": quota_limit,
            "remaining": quota_limit - usage - amount,
            "percent": ((usage + amount) / quota_limit * 100) if quota_limit > 0 else 0,
        }

    def generate_invoice(self, subscription_id: str) -> Dict[str, Any]:
        sub = self._subscriptions.get(subscription_id)
        if not sub:
            return {"error": "Subscription not found"}

        tier_def = self.tiers.get(Tier(sub.tier))
        if not tier_def:
            return {"error": "Unknown tier"}

        amount = tier_def.pricing.monthly
        invoice_id = str(uuid.uuid4())
        invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:8]}"
        now = time.time()

        invoice = Invoice(
            id=invoice_id,
            subscription_id=subscription_id,
            user_id=sub.user_id,
            invoice_number=invoice_number,
            status="draft",
            amount=amount,
            due_date=now + 30 * 86400,
            created_at=now,
        )
        self._invoices[invoice_id] = invoice

        return {
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "amount": amount,
            "status": "draft",
            "due_date": invoice.due_date,
        }

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._audit_log[-limit:]

    def _initialize_usage(self, sub_id: str, tier_def: TierDefinition,
                          period_start: float, period_end: float):
        if sub_id not in self._usage:
            self._usage[sub_id] = {}
        for attr in ["api_calls_per_day", "api_calls_per_month", "concurrent_workers",
                      "total_workers", "storage_gb", "compute_hours", "mining_hashes",
                      "quantum_ops", "training_jobs", "compressed_datasets"]:
            quota = getattr(tier_def.quota, attr, 0)
            self._usage[sub_id][attr] = UsageRecord(
                subscription_id=sub_id,
                metric_name=attr,
                used_amount=0,
                quota_limit=quota,
                period_start=period_start,
                period_end=period_end,
            )

    def _record_usage(self, sub_id: Optional[str], metric: str, amount: int):
        if sub_id and sub_id in self._usage and metric in self._usage[sub_id]:
            self._usage[sub_id][metric].used_amount += amount
        self._usage_events.append({
            "subscription_id": sub_id,
            "metric_name": metric,
            "amount": amount,
            "timestamp": time.time(),
        })

    def _get_usage(self, sub_id: str) -> Dict[str, Dict[str, Any]]:
        if sub_id not in self._usage:
            return {}
        return {
            metric: {"used": rec.used_amount, "limit": rec.quota_limit, "percent": rec.percent}
            for metric, rec in self._usage[sub_id].items()
        }

    def _get_usage_metric(self, sub_id: Optional[str], metric: str) -> int:
        if not sub_id or sub_id not in self._usage:
            return 0
        if metric not in self._usage[sub_id]:
            return 0
        return self._usage[sub_id][metric].used_amount

    def _audit(self, action: str, user_id: str, resource_id: str, details: Dict):
        self._audit_log.append({
            "action": action,
            "user_id": user_id,
            "resource_id": resource_id,
            "details": details,
            "timestamp": time.time(),
        })

    @staticmethod
    def _features_to_dict(features: TierFeatures) -> dict:
        return {
            "quantum_engine": features.quantum_engine,
            "vqc_training": features.vqc_training,
            "geodesic_search": features.geodesic_search,
            "phi_compression": features.phi_compression,
            "ai_training": features.ai_training,
            "gpu_scaling": features.gpu_scaling,
            "qec_codes": features.qec_codes,
            "manifold_types": features.manifold_types,
            "data_sovereignty": features.data_sovereignty,
            "audit_logs": features.audit_logs,
            "compliance_frameworks": features.compliance_frameworks,
            "priority_support": features.priority_support,
            "dedicated_environment": features.dedicated_environment,
            "custom_algorithms": features.custom_algorithms,
            "white_label": features.white_label,
            "sla_guarantee": features.sla_guarantee,
        }

    @staticmethod
    def _quota_to_dict(quota: TierQuota) -> dict:
        return {
            "api_calls_per_day": quota.api_calls_per_day,
            "api_calls_per_month": quota.api_calls_per_month,
            "concurrent_workers": quota.concurrent_workers,
            "total_workers": quota.total_workers,
            "storage_gb": quota.storage_gb,
            "compute_hours": quota.compute_hours,
            "mining_hashes": quota.mining_hashes,
            "quantum_ops": quota.quantum_ops,
            "training_jobs": quota.training_jobs,
            "compressed_datasets": quota.compressed_datasets,
            "regions_available": quota.regions_available,
            "retention_days": quota.retention_days,
        }
