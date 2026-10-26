"""Bounded software GPU packages; tier limits are resources, never hash-rate promises."""

from dataclasses import asdict, dataclass
import json
import threading

from aethel.enterprise.governance import Quotas
from aethel.fibonacci import BinetIndex, fibonacci, cassini_quadruple, cassini_holds
from chronus.igpu.scaled_plan import ScaledPlan
from chronus.triad import ChronusTriad
from chronus.virtual_igpu.abi import canonical_json


@dataclass(frozen=True)
class CapacityTier:
    name: str
    max_workers: int
    max_items_per_request: int
    max_input_bytes: int
    max_resident_bytes: int
    max_custody_bytes: int
    max_custody_records: int
    scale_index: int
    storage_index: int

    def __post_init__(self):
        if not self.name or any(
            type(v) is not int or v < 1 for k, v in asdict(self).items() if k != "name"
        ):
            raise ValueError("tier limits must be positive integers")
        if self.max_workers > 120 or self.max_items_per_request > 1_000_000:
            raise ValueError("tier exceeds supported local execution bounds")
        plan = ScaledPlan(base_items=32, scale_index=self.scale_index)
        if not 2 <= self.storage_index <= 32:
            raise ValueError("storage index must be in 2..32")
        if self.max_items_per_request > plan.effective_items:
            raise ValueError("tier exceeds its Lucas/Pisot work budget")
        if self.max_custody_bytes > fibonacci(self.storage_index) * 1024 * 1024:
            raise ValueError("tier exceeds its Fibonacci storage budget")
        if BinetIndex(self.storage_index).value != fibonacci(
            self.storage_index
        ) or not cassini_holds(cassini_quadruple(self.storage_index)):
            raise ValueError("storage algebra certificate failed")

    def manifest(self):
        return {
            "schema": "chronus.capacity-tier/v1",
            **asdict(self),
            "price": None,
            "guaranteed_hashrate": None,
            "scaling": {
                "lucas_factor": ScaledPlan(1, self.scale_index).factor,
                "pisot_conjugate_bound": [2**self.scale_index, 3**self.scale_index],
            },
            "storage": {
                "fibonacci_pages": fibonacci(self.storage_index),
                "page_bytes": 1024 * 1024,
                "cassini_witness": cassini_quadruple(self.storage_index),
                "binet_value": BinetIndex(self.storage_index).value,
                "fold_codec": "zeckendorf_vector_v1",
            },
            "live_pool_authority": False,
            "reserved_recovery_slots_sold": 0,
        }


MIB = 1024 * 1024
TIERS = {
    "starter": CapacityTier("starter", 1, 3936, MIB, 16 * MIB, 55 * MIB, 1000, 10, 10),
    "pro": CapacityTier("pro", 4, 43648, 4 * MIB, 64 * MIB, 233 * MIB, 10000, 15, 13),
    "fleet": CapacityTier("fleet", 12, 484064, 16 * MIB, 256 * MIB, 987 * MIB, 100000, 20, 16),
}


class CapacityExceeded(RuntimeError):
    pass


class PackagedGPU:
    """One bounded local GPU instance. Host memory is accounted payload residency."""

    def __init__(self, root, *, tenant, tier="starter", **kwargs):
        self.tier = TIERS[tier] if isinstance(tier, str) else tier
        if not isinstance(self.tier, CapacityTier):
            raise TypeError("a validated capacity tier is required")
        self._busy = threading.Lock()
        if "custody_options" in kwargs:
            raise ValueError("custody quotas are controlled by the package tier")
        self.triad = ChronusTriad(
            root,
            tenant=tenant,
            custody_options={
                "quotas": Quotas(
                    max_payload=self.tier.max_input_bytes * 4,
                    max_records=self.tier.max_custody_records,
                    max_tenant_bytes=self.tier.max_custody_bytes,
                )
            },
            **kwargs,
        )
        self.triad.runtime.memory.max_host_bytes = self.tier.max_resident_bytes

    def submit(self, workload):
        if len(canonical_json(workload.input).encode()) > self.tier.max_input_bytes:
            raise CapacityExceeded("input exceeds package byte limit")
        value = workload.input
        if isinstance(value, dict):
            if (
                str(getattr(workload.kind, "value", workload.kind)) == "sha256d_scan"
                and value.get("nonces") is None
            ):
                count = value.get("count", 1)
                if type(count) is not int or not 1 <= count <= self.tier.max_items_per_request:
                    raise CapacityExceeded("scan range exceeds package item limit")
            for field in ("nonces", "indices"):
                if field in value and len(value[field]) > self.tier.max_items_per_request:
                    raise CapacityExceeded("work exceeds package item limit")
        if not self._busy.acquire(blocking=False):
            raise CapacityExceeded("GPU instance is busy")
        try:
            return self.triad.submit(workload)
        finally:
            self._busy.release()

    def manifest(self):
        return {
            **self.tier.manifest(),
            "product_mode": self.triad.capacity.product_mode.value,
            "tenant": self.triad.tenant,
            "logical_devices": 1,
            "custody": self.triad.ovid.health(),
            "storage_measurements": self.triad.ovid.storage_measurements(),
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tiers", "capacity"))
    parser.add_argument("--tier", choices=tuple(TIERS), default="starter")
    parser.add_argument("--root")
    parser.add_argument("--tenant")
    parser.add_argument("--mode", choices=("independent", "host"), default="independent")
    parser.add_argument("--scale-index", type=int, default=10)
    args = parser.parse_args()
    if args.command == "tiers":
        print(json.dumps([t.manifest() for t in TIERS.values()], sort_keys=True))
        return
    if not args.root or not args.tenant:
        parser.error("capacity requires --root and --tenant")
    from chronus.scaled_gpiu import ScaledGPIU

    gpu = PackagedGPU(args.root, tenant=args.tenant, tier=args.tier, mode=args.mode)
    engine = ScaledGPIU(gpu, tenant=args.tenant, mode=args.mode)
    result = engine.execute(
        workload_id="capacity",
        base_items=1,
        scale_index=args.scale_index,
        max_items=gpu.tier.max_items_per_request,
    )
    print(json.dumps({"package": gpu.manifest(), "result": result}, sort_keys=True))


if __name__ == "__main__":
    main()
