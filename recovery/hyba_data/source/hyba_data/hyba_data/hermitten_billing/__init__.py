"""
HYBA_DATA Hermitten Billing System

Savings-based pricing: charges 25% of GPU memory/workload savings.
"We reduce your GPU memory usage by 50-92%, and we only charge 25% of the savings we generate for you."

Author: Andre Taylor-Morris - HYBA Software Ltd
"""
from .billing import (
    GPUMetrics,
    WorkloadSavings,
    HermittenBill,
    WorkloadCategory,
    WORKLOAD_CATEGORIES,
    HermittenBillingService,
)

__all__ = [
    "GPUMetrics",
    "WorkloadSavings",
    "HermittenBill",
    "WorkloadCategory",
    "WORKLOAD_CATEGORIES",
    "HermittenBillingService",
]
