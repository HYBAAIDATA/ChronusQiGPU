"""
HYBA_DATA Multi-Region Disaster Recovery Implementation

Multi-region disaster recovery with active-active replication.
RPO < 1 hour, RTO < 15 minutes, 99.999% uptime target.

Author: Andre Taylor-Morris — HYBA Software Ltd
"""
import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class RegionStatus(Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


@dataclass
class Region:
    """Cloud region configuration."""
    name: str
    endpoint: str
    api_key: str = ""
    priority: int = 1
    status: str = "active"
    last_heartbeat: float = field(default_factory=time.time)
    latency: float = 0.0
    region: str = ""  # geographic region (US_EAST, EU_WEST, etc.)
    jurisdiction: str = ""  # legal jurisdiction

    def is_healthy(self) -> bool:
        return self.status == "active" and (time.time() - self.last_heartbeat) < 60

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "priority": self.priority,
            "status": self.status,
            "latency": self.latency,
            "last_heartbeat_age": time.time() - self.last_heartbeat,
            "region": self.region,
            "jurisdiction": self.jurisdiction,
        }


@dataclass
class ReplicationConfig:
    """Data replication configuration."""
    region: str
    sync_mode: str = "async"  # "async", "sync", "semi_sync"
    replication_factor: int = 3
    compression_enabled: bool = True
    encryption_enabled: bool = True


@dataclass
class FailoverResult:
    """Result of a failover operation."""
    status: str
    old_region: str
    new_region: str
    timestamp: float
    rto_seconds: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "old_region": self.old_region,
            "new_region": self.new_region,
            "timestamp": self.timestamp,
            "rto_seconds": self.rto_seconds,
            "reason": self.reason,
        }


@dataclass
class DRHealthReport:
    """Disaster recovery health report."""
    regions: Dict[str, dict]
    active_region: str
    total_regions: int
    healthy_regions: int
    replication_lag_seconds: float
    uptime_percentage: float
    rpo_compliant: bool
    rto_compliant: bool

    def to_dict(self) -> dict:
        return {
            "regions": self.regions,
            "active_region": self.active_region,
            "total_regions": self.total_regions,
            "healthy_regions": self.healthy_regions,
            "replication_lag_seconds": self.replication_lag_seconds,
            "uptime_percentage": self.uptime_percentage,
            "rpo_compliant": self.rpo_compliant,
            "rto_compliant": self.rto_compliant,
        }


class DisasterRecoveryEngine:
    """
    Multi-region disaster recovery with active-active replication.
    RPO < 1 hour, RTO < 15 minutes, 99.999% uptime target.
    """

    TARGET_UPTIME = 99.999  # five nines
    TARGET_RPO_SECONDS = 3600  # 1 hour
    TARGET_RTO_SECONDS = 900  # 15 minutes

    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.replication_configs: Dict[str, ReplicationConfig] = {}
        self.active_region: Optional[str] = None
        self.replication_queue: List[Dict[str, Any]] = []
        self.failover_log: List[FailoverResult] = []
        self.uptime_start = time.time()
        self.downtime_seconds = 0.0
        self._replicated_data: Dict[str, List[Dict[str, Any]]] = {}  # region -> data list

    def add_region(self, region: Region) -> None:
        """Add a cloud region."""
        self.regions[region.name] = region
        if self.active_region is None:
            self.active_region = region.name
        self._replicated_data[region.name] = []

    def configure_replication(self, config: ReplicationConfig) -> None:
        """Configure replication for a region."""
        self.replication_configs[config.region] = config

    def replicate_data(self, data: Dict[str, Any], source_region: str) -> Dict[str, Any]:
        """Replicate data to all configured regions (synchronous)."""
        results = {}
        for region_name, region in self.regions.items():
            if region_name == source_region:
                continue
            config = self.replication_configs.get(region_name)
            if not config:
                continue
            try:
                # Simulate replication
                if config.compression_enabled:
                    data_copy = json.loads(json.dumps(data, default=str))
                else:
                    data_copy = data.copy()
                self._replicated_data[region_name].append({
                    "data": data_copy,
                    "source": source_region,
                    "timestamp": time.time(),
                })
                results[region_name] = {"status": "success"}
            except Exception as e:
                results[region_name] = {"status": "failed", "error": str(e)}
        return results

    def failover(self, failed_region: str) -> FailoverResult:
        """Trigger failover to next available region."""
        failover_start = time.time()

        if failed_region not in self.regions:
            return FailoverResult(
                status="error", old_region=self.active_region or "",
                new_region="", timestamp=time.time(),
                reason="Region not found",
            )

        # Mark failed region
        self.regions[failed_region].status = "failed"

        # Find next available region by priority
        available = [
            (r.name, r.priority) for r in self.regions.values()
            if r.name != failed_region and r.status == "active"
        ]
        if not available:
            self.downtime_seconds += time.time() - failover_start
            return FailoverResult(
                status="error", old_region=self.active_region or "",
                new_region="", timestamp=time.time(),
                reason="No available regions for failover",
            )

        available.sort(key=lambda x: x[1])
        new_region = available[0][0]
        old_region = self.active_region
        self.active_region = new_region

        rto = time.time() - failover_start
        result = FailoverResult(
            status="failover_complete",
            old_region=old_region,
            new_region=new_region,
            timestamp=time.time(),
            rto_seconds=rto,
            reason=f"Region {failed_region} failed",
        )
        self.failover_log.append(result)
        return result

    def heartbeat(self, region_name: str, latency: float = 0.0) -> None:
        """Update region heartbeat."""
        if region_name in self.regions:
            self.regions[region_name].last_heartbeat = time.time()
            self.regions[region_name].latency = latency

    def get_health(self) -> DRHealthReport:
        """Get health status of all regions."""
        region_health = {}
        healthy = 0
        for name, region in self.regions.items():
            is_healthy = region.is_healthy()
            if is_healthy:
                healthy += 1
            region_health[name] = {
                "status": region.status,
                "latency": region.latency,
                "last_heartbeat_age": time.time() - region.last_heartbeat,
                "healthy": is_healthy,
            }

        uptime = self._calculate_uptime()
        rpo = self._check_rpo_compliance()
        rto = self._check_rto_compliance()

        return DRHealthReport(
            regions=region_health,
            active_region=self.active_region or "",
            total_regions=len(self.regions),
            healthy_regions=healthy,
            replication_lag_seconds=0.0,
            uptime_percentage=uptime,
            rpo_compliant=rpo,
            rto_compliant=rto,
        )

    def _calculate_uptime(self) -> float:
        """Calculate current uptime percentage."""
        total_time = time.time() - self.uptime_start
        if total_time <= 0:
            return 100.0
        return (total_time - self.downtime_seconds) / total_time * 100.0

    def _check_rpo_compliance(self) -> bool:
        """Check if RPO is within target."""
        return True  # Simplified — would check actual replication lag

    def _check_rto_compliance(self) -> bool:
        """Check if RTO is within target."""
        if not self.failover_log:
            return True
        last_failover = self.failover_log[-1]
        return last_failover.rto_seconds <= self.TARGET_RTO_SECONDS

    def get_failover_history(self) -> List[Dict[str, Any]]:
        """Get failover event history."""
        return [f.to_dict() for f in self.failover_log]

    def get_replicated_data_count(self, region: str) -> int:
        """Get count of replicated data items in a region."""
        return len(self._replicated_data.get(region, []))
