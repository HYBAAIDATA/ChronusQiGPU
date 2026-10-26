"""Lucas/Pisot streaming execution for Chronus independent and host modes."""

from chronus.compiler.exact_kernel import ExactKernelIR, MASK
from chronus.igpu.scaled_plan import ScaledPlan
from chronus.virtual_igpu.abi import Workload, ProductMode, execution_policy_for_product_mode


class ScaledGPIU:
    def __init__(
        self,
        runtime,
        *,
        tenant,
        mode="independent",
        host_adapter_id=None,
        allow_software_fallback=True,
    ):
        modes = {
            "independent": ProductMode.NATIVE_CHRONUS_GPU,
            "host": ProductMode.HOST_GPU_AUGMENTATION,
            "native_chronus_gpu": ProductMode.NATIVE_CHRONUS_GPU,
            "host_gpu_augmentation": ProductMode.HOST_GPU_AUGMENTATION,
        }
        if not isinstance(tenant, str) or not tenant or mode not in modes:
            raise ValueError("tenant and declared software GPU mode required")
        if type(allow_software_fallback) is not bool:
            raise ValueError("allow_software_fallback must be boolean")
        self.product_mode = modes[mode]
        if self.product_mode == ProductMode.NATIVE_CHRONUS_GPU and host_adapter_id is not None:
            raise ValueError("host adapter selection belongs to augmentation mode")
        self.allow_software_fallback = allow_software_fallback
        self.runtime, self.tenant, self.mode = runtime, tenant, mode
        self.host_adapter_id = host_adapter_id

    def execute(
        self, *, workload_id, base_items, scale_index=10, seed=0, max_items=65536, chunk_items=256
    ):
        if type(max_items) is not int or not 1 <= max_items <= 1048576:
            raise ValueError("max_items must be in 1..1048576")
        plan = ScaledPlan(base_items=base_items, scale_index=scale_index)
        if plan.effective_items > max_items:
            raise MemoryError("scaled work exceeds explicit execution budget")
        if type(seed) is not int or not 0 <= seed <= MASK:
            raise ValueError("seed must be uint32")
        if type(chunk_items) is not int or not 1 <= chunk_items <= 65536:
            raise ValueError("chunk_items must be in 1..65536")
        if self.host_adapter_id is not None:
            adapter = next((a for a in self.runtime.adapters if a.id == self.host_adapter_id), None)
            if adapter is None or adapter.kind.value in ("software", "cpu_reference", "unknown"):
                raise ValueError("host mode requires a bound host accelerator adapter")
        ir = ExactKernelIR()
        receipts, rows, custody = [], [], []
        for start, end in plan.chunks(chunk_items):
            request = Workload(
                id=f"{workload_id}:{start}:{end}",
                tenant=self.tenant,
                kind="exact_kernel",
                input={
                    "ir": ir.to_dict(),
                    "indices": [scale_index] * (end - start),
                    "seed": (seed + start * 0x9E3779B9) & MASK,
                },
                execution_policy=(
                    "required_adapter"
                    if self.host_adapter_id
                    else execution_policy_for_product_mode(self.product_mode)
                ),
                required_adapter_id=self.host_adapter_id,
                allow_software_fallback=self.allow_software_fallback,
            )
            result = self.runtime.submit(request)
            if (
                result.status != "ok"
                or result.receipt.get("verification", {}).get("verdict") != "match"
            ):
                raise RuntimeError("scaled kernel did not verify")
            rows.extend(result.output["rows"])
            receipts.append(result.receipt)
            if "custody" in result.metrics:
                custody.append(result.metrics["custody"])
        return {
            "mode": self.mode,
            "product_mode": self.product_mode.value,
            "plan": plan.manifest(),
            "rows": rows,
            "receipts": receipts,
            "custody": custody,
            "executed_items": len(rows),
            "golden_pisot_conjugate_bound": [2**scale_index, 3**scale_index],
        }


def main():
    """Execute a bounded capacity request using either canonical product mode."""
    import argparse
    import json
    from .triad import ChronusTriad

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("independent", "host"), default="independent")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--workload-id", required=True)
    parser.add_argument("--base-items", type=int, default=1)
    parser.add_argument("--scale-index", type=int, default=10)
    parser.add_argument("--max-items", type=int, default=65536)
    parser.add_argument("--chunk-items", type=int, default=256)
    parser.add_argument("--host-adapter-id")
    parser.add_argument("--no-software-fallback", action="store_true")
    args = parser.parse_args()
    engine = ChronusTriad(
        args.store_root,
        tenant=args.tenant,
        mode=args.mode,
        host_adapter_id=args.host_adapter_id,
        allow_software_fallback=not args.no_software_fallback,
    )
    result = engine.execute(
        workload_id=args.workload_id,
        base_items=args.base_items,
        scale_index=args.scale_index,
        max_items=args.max_items,
        chunk_items=args.chunk_items,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
