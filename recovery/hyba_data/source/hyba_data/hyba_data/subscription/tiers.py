"""
HYBA_DATA Subscription Tier Definitions

Complete tier definitions with quotas, features, and pricing.
5 tiers: Free, Pro, Team, Enterprise, Government.

Author: Andre Taylor-Morris - HYBA Software Ltd
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class Tier(Enum):
    """Subscription tiers."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"
    CUSTOM = "custom"


class BillingPeriod(Enum):
    """Billing periods."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"


@dataclass
class TierQuota:
    """Quota limits per tier."""
    api_calls_per_day: int
    api_calls_per_month: int
    concurrent_workers: int
    total_workers: int
    storage_gb: int
    compute_hours: int
    mining_hashes: int
    quantum_ops: int
    training_jobs: int
    compressed_datasets: int
    regions_available: List[str]
    retention_days: int


@dataclass
class TierFeatures:
    """Features available per tier."""
    quantum_engine: bool
    vqc_training: bool
    geodesic_search: bool
    phi_compression: bool
    ai_training: bool
    gpu_scaling: bool
    qec_codes: List[str]
    manifold_types: List[str]
    data_sovereignty: bool
    audit_logs: bool
    compliance_frameworks: List[str]
    priority_support: bool
    dedicated_environment: bool
    custom_algorithms: bool
    white_label: bool
    sla_guarantee: Optional[str]


@dataclass
class Pricing:
    """Pricing structure."""
    monthly: float
    yearly: float
    per_seat: Optional[float]
    overage: Dict[str, float] = field(default_factory=dict)


@dataclass
class TierDefinition:
    """Complete tier definition."""
    tier: Tier
    name: str
    description: str
    quota: TierQuota
    features: TierFeatures
    pricing: Pricing
    is_public: bool
    display_order: int
    metadata: Dict[str, str] = field(default_factory=dict)


TIER_ORDER = ["free", "pro", "team", "enterprise", "government"]

TIER_DEFINITIONS: Dict[Tier, TierDefinition] = {
    Tier.FREE: TierDefinition(
        tier=Tier.FREE,
        name="Free",
        description="Try φ-Grover with basic features",
        quota=TierQuota(
            api_calls_per_day=100,
            api_calls_per_month=3000,
            concurrent_workers=1,
            total_workers=1,
            storage_gb=1,
            compute_hours=10,
            mining_hashes=1000000,
            quantum_ops=1000,
            training_jobs=1,
            compressed_datasets=5,
            regions_available=["US_EAST"],
            retention_days=7,
        ),
        features=TierFeatures(
            quantum_engine=True,
            vqc_training=False,
            geodesic_search=True,
            phi_compression=True,
            ai_training=False,
            gpu_scaling=False,
            qec_codes=["BitFlip"],
            manifold_types=["M32"],
            data_sovereignty=False,
            audit_logs=False,
            compliance_frameworks=[],
            priority_support=False,
            dedicated_environment=False,
            custom_algorithms=False,
            white_label=False,
            sla_guarantee=None,
        ),
        pricing=Pricing(
            monthly=0.0,
            yearly=0.0,
            per_seat=None,
            overage={"api_calls": 0.001, "storage_gb": 0.50, "compute_hours": 0.50},
        ),
        is_public=True,
        display_order=1,
        metadata={"trial": "forever"},
    ),
    Tier.PRO: TierDefinition(
        tier=Tier.PRO,
        name="Pro",
        description="Professional quantum & AI tools",
        quota=TierQuota(
            api_calls_per_day=10000,
            api_calls_per_month=300000,
            concurrent_workers=5,
            total_workers=10,
            storage_gb=100,
            compute_hours=500,
            mining_hashes=100000000,
            quantum_ops=100000,
            training_jobs=10,
            compressed_datasets=100,
            regions_available=["US_EAST", "EU_WEST"],
            retention_days=30,
        ),
        features=TierFeatures(
            quantum_engine=True,
            vqc_training=True,
            geodesic_search=True,
            phi_compression=True,
            ai_training=True,
            gpu_scaling=True,
            qec_codes=["BitFlip", "PhaseFlip"],
            manifold_types=["M32", "GoldenRatioSphere", "FibonacciLattice"],
            data_sovereignty=False,
            audit_logs=True,
            compliance_frameworks=["GDPR"],
            priority_support=False,
            dedicated_environment=False,
            custom_algorithms=False,
            white_label=False,
            sla_guarantee="99.9%",
        ),
        pricing=Pricing(
            monthly=99.0,
            yearly=990.0,
            per_seat=None,
            overage={"api_calls": 0.0001, "storage_gb": 0.10, "compute_hours": 0.10, "mining_hashes": 0.0000001},
        ),
        is_public=True,
        display_order=2,
        metadata={"trial_days": 14},
    ),
    Tier.TEAM: TierDefinition(
        tier=Tier.TEAM,
        name="Team",
        description="Collaborative quantum & AI platform",
        quota=TierQuota(
            api_calls_per_day=100000,
            api_calls_per_month=3000000,
            concurrent_workers=20,
            total_workers=50,
            storage_gb=1000,
            compute_hours=5000,
            mining_hashes=10000000000,
            quantum_ops=1000000,
            training_jobs=50,
            compressed_datasets=500,
            regions_available=["US_EAST", "EU_WEST", "AP_SOUTH"],
            retention_days=90,
        ),
        features=TierFeatures(
            quantum_engine=True,
            vqc_training=True,
            geodesic_search=True,
            phi_compression=True,
            ai_training=True,
            gpu_scaling=True,
            qec_codes=["BitFlip", "PhaseFlip", "Steane"],
            manifold_types=["M32", "GoldenRatioSphere", "FibonacciLattice", "Icosahedral", "Dodecahedral"],
            data_sovereignty=True,
            audit_logs=True,
            compliance_frameworks=["GDPR", "CCPA", "HIPAA"],
            priority_support=True,
            dedicated_environment=False,
            custom_algorithms=False,
            white_label=False,
            sla_guarantee="99.95%",
        ),
        pricing=Pricing(
            monthly=499.0,
            yearly=4990.0,
            per_seat=25.0,
            overage={"api_calls": 0.00001, "storage_gb": 0.05, "compute_hours": 0.05, "mining_hashes": 0.00000001},
        ),
        is_public=True,
        display_order=3,
        metadata={"min_seats": 5},
    ),
    Tier.ENTERPRISE: TierDefinition(
        tier=Tier.ENTERPRISE,
        name="Enterprise",
        description="Full quantum & AI platform for large organizations",
        quota=TierQuota(
            api_calls_per_day=1000000,
            api_calls_per_month=30000000,
            concurrent_workers=100,
            total_workers=500,
            storage_gb=10000,
            compute_hours=50000,
            mining_hashes=1000000000000,
            quantum_ops=10000000,
            training_jobs=500,
            compressed_datasets=5000,
            regions_available=["US_EAST", "US_WEST", "EU_WEST", "EU_NORTH", "AP_SOUTH", "AP_EAST"],
            retention_days=365,
        ),
        features=TierFeatures(
            quantum_engine=True,
            vqc_training=True,
            geodesic_search=True,
            phi_compression=True,
            ai_training=True,
            gpu_scaling=True,
            qec_codes=["BitFlip", "PhaseFlip", "Steane", "Surface"],
            manifold_types=["M32", "Grassmannian", "Stiefel", "GoldenRatioSphere", "FibonacciLattice", "Icosahedral", "Dodecahedral", "LieGroup"],
            data_sovereignty=True,
            audit_logs=True,
            compliance_frameworks=["GDPR", "CCPA", "HIPAA", "FedRAMP", "FIPS_140_2", "NIST_800_53", "PCI_DSS", "SOX"],
            priority_support=True,
            dedicated_environment=True,
            custom_algorithms=True,
            white_label=True,
            sla_guarantee="99.999%",
        ),
        pricing=Pricing(
            monthly=4999.0,
            yearly=49990.0,
            per_seat=None,
            overage={"api_calls": 0.000001, "storage_gb": 0.01, "compute_hours": 0.01, "mining_hashes": 0.000000001},
        ),
        is_public=False,
        display_order=4,
        metadata={"custom_deployment": True},
    ),
    Tier.GOVERNMENT: TierDefinition(
        tier=Tier.GOVERNMENT,
        name="Government",
        description="Classified quantum & AI platform for sovereign nations",
        quota=TierQuota(
            api_calls_per_day=10000000,
            api_calls_per_month=300000000,
            concurrent_workers=1000,
            total_workers=5000,
            storage_gb=100000,
            compute_hours=500000,
            mining_hashes=1000000000000000,
            quantum_ops=100000000,
            training_jobs=5000,
            compressed_datasets=50000,
            regions_available=["US_EAST", "US_WEST", "EU_WEST", "EU_NORTH", "AP_SOUTH", "AP_EAST", "CA_CENTRAL", "AU_SOUTH", "SA_EAST"],
            retention_days=0,
        ),
        features=TierFeatures(
            quantum_engine=True,
            vqc_training=True,
            geodesic_search=True,
            phi_compression=True,
            ai_training=True,
            gpu_scaling=True,
            qec_codes=["BitFlip", "PhaseFlip", "Steane", "Surface"],
            manifold_types=["M32", "Grassmannian", "Stiefel", "GoldenRatioSphere", "FibonacciLattice", "Icosahedral", "Dodecahedral", "LieGroup"],
            data_sovereignty=True,
            audit_logs=True,
            compliance_frameworks=["GDPR", "CCPA", "HIPAA", "FedRAMP", "FIPS_140_2", "NIST_800_53", "PCI_DSS", "SOX"],
            priority_support=True,
            dedicated_environment=True,
            custom_algorithms=True,
            white_label=True,
            sla_guarantee="99.9999%",
        ),
        pricing=Pricing(
            monthly=99999.0,
            yearly=999990.0,
            per_seat=None,
            overage={},
        ),
        is_public=False,
        display_order=5,
        metadata={
            "classification_levels": "CONFIDENTIAL, SECRET, TOP_SECRET",
            "requires_cleared_personnel": True,
            "custom_security_audit": True,
        },
    ),
}


def get_tier_by_name(name: str) -> Optional[TierDefinition]:
    """Get tier definition by name string."""
    for tier, definition in TIER_DEFINITIONS.items():
        if tier.value == name:
            return definition
    return None


def get_min_tier_for_feature(feature: str) -> str:
    """Get minimum tier required for a feature."""
    tier_map = {
        "vqc_training": "pro",
        "gpu_scaling": "pro",
        "ai_training": "pro",
        "data_sovereignty": "team",
        "custom_algorithms": "enterprise",
        "white_label": "enterprise",
        "dedicated_environment": "enterprise",
    }
    return tier_map.get(feature, "free")


def tier_meets_requirement(current_tier: str, min_tier: str) -> bool:
    """Check if current tier meets minimum tier requirement."""
    try:
        return TIER_ORDER.index(current_tier) >= TIER_ORDER.index(min_tier)
    except ValueError:
        return False
