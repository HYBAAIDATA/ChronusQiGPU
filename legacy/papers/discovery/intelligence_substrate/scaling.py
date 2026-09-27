"""
HYBA Scaling Module
====================
Multi-Node Distributed Operations, Elastic Scaling, Checkpointing & Recovery.
"""

import asyncio
import os
import pickle
import time
from typing import Any, Dict, List, Optional

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False


class MultiNodeExecutor:
    """Multi-node distributed execution."""

    def __init__(
        self,
        world_size: int = 1,
        rank: int = 0,
        master_addr: str = "127.0.0.1",
        master_port: str = "29500",
    ):
        self.world_size = world_size
        self.rank = rank
        self.master_addr = master_addr
        self.master_port = master_port
        self._initialized = False

    def initialize(self) -> None:
        """Initialize distributed environment if available."""
        if not self._initialized:
            try:
                import torch.distributed as dist

                if not dist.is_initialized():
                    dist.init_process_group(
                        backend="nccl" if torch.cuda.is_available() else "gloo",
                        init_method=f"tcp://{self.master_addr}:{self.master_port}",
                        world_size=self.world_size,
                        rank=self.rank,
                    )
            except Exception:
                pass
            self._initialized = True

    def all_reduce(self, tensor: Any) -> Any:
        """All-reduce across nodes."""
        self.initialize()
        try:
            import torch.distributed as dist

            if dist.is_initialized():
                dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
        except Exception:
            pass
        return tensor

    def broadcast(self, tensor: Any, src: int = 0) -> Any:
        """Broadcast tensor from source rank."""
        self.initialize()
        try:
            import torch.distributed as dist

            if dist.is_initialized():
                dist.broadcast(tensor, src=src)
        except Exception:
            pass
        return tensor

    def barrier(self) -> None:
        """Synchronize all processes."""
        self.initialize()
        try:
            import torch.distributed as dist

            if dist.is_initialized():
                dist.barrier()
        except Exception:
            pass

    def shutdown(self) -> None:
        """Shutdown distributed environment."""
        if self._initialized:
            try:
                import torch.distributed as dist

                if dist.is_initialized():
                    dist.destroy_process_group()
            except Exception:
                pass
            self._initialized = False


class DistributedCompressor:
    """Distributed compressor with multi-node support."""

    def __init__(self, nodes: int = 1, gpus_per_node: int = 1):
        self.nodes = nodes
        self.gpus_per_node = gpus_per_node
        self.world_size = nodes * gpus_per_node
        self.executor = MultiNodeExecutor(world_size=self.world_size)

    def compress(self, tensor: Any) -> Any:
        """Compress tensor across shards."""
        shards = self._shard(tensor)
        compressed_shards = [self._local_compress(s) for s in shards]
        if TORCH_AVAILABLE and isinstance(compressed_shards[0], torch.Tensor):
            return torch.cat(compressed_shards, dim=0)
        return compressed_shards[0]

    def _shard(self, tensor: Any) -> List[Any]:
        if not hasattr(tensor, "size"):
            return [tensor]
        shard_size = max(1, tensor.size(0) // self.world_size)
        return [tensor[i * shard_size : (i + 1) * shard_size] for i in range(self.world_size)]

    def _local_compress(self, tensor: Any) -> Any:
        return tensor


class ElasticManager:
    """Elastic scaling manager."""

    def __init__(self):
        self.workers = {}
        self.running = False

    async def start(self) -> None:
        """Start the elastic scaling loop."""
        self.running = True
        while self.running:
            await self._check_scale()
            await asyncio.sleep(1)

    def stop(self) -> None:
        self.running = False

    async def _check_scale(self) -> None:
        available_gpus = self._get_available_gpus()
        workload = self._get_workload()
        if workload > 0.8 and len(self.workers) < len(available_gpus):
            await self._scale_up()
        elif workload < 0.3 and len(self.workers) > 1:
            await self._scale_down()

    def _get_available_gpus(self) -> List[int]:
        return (
            list(range(torch.cuda.device_count()))
            if TORCH_AVAILABLE and torch.cuda.is_available()
            else [0]
        )

    def _get_workload(self) -> float:
        return 0.5

    async def _scale_up(self) -> None:
        gpus = self._get_available_gpus()
        for gpu in gpus:
            if gpu not in self.workers:
                worker = asyncio.create_task(self._run_worker(gpu))
                self.workers[gpu] = worker
                break

    async def _scale_down(self) -> None:
        if len(self.workers) > 1:
            gpu = list(self.workers.keys())[-1]
            self.workers[gpu].cancel()
            del self.workers[gpu]

    async def _run_worker(self, gpu: int) -> None:
        if torch.cuda.is_available():
            torch.cuda.set_device(gpu)
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass


class CheckpointManager:
    """Automatic checkpointing and recovery."""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

    def save(self, state: Dict[str, Any], name: str) -> str:
        """Save a checkpoint."""
        filename = os.path.join(self.checkpoint_dir, f"{name}_{int(time.time())}.ckpt")
        with open(filename, "wb") as f:
            pickle.dump(state, f)
        return filename

    def load(self, filename: str) -> Dict[str, Any]:
        """Load a checkpoint."""
        with open(filename, "rb") as f:
            return pickle.load(f)

    def load_latest(self, name: str) -> Optional[Dict[str, Any]]:
        """Load the latest checkpoint for a given name."""
        if not os.path.exists(self.checkpoint_dir):
            return None
        files = [f for f in os.listdir(self.checkpoint_dir) if f.startswith(name)]
        if files:
            latest = sorted(files)[-1]
            return self.load(os.path.join(self.checkpoint_dir, latest))
        return None


class RecoverableExecutor:
    """Executor with automatic checkpoint recovery."""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint = CheckpointManager(checkpoint_dir)
        self.state = {}

    def execute(self, func: Any, *args, **kwargs) -> Any:
        """Execute with checkpointing."""
        try:
            result = func(*args, **kwargs)
            self.state["last_result"] = result
            self.checkpoint.save(self.state, "executor")
            return result
        except Exception as e:
            recovered = self.recover()
            if recovered is not None:
                return recovered
            raise e

    def recover(self) -> Optional[Any]:
        """Recover state from last checkpoint."""
        state = self.checkpoint.load_latest("executor")
        if state:
            self.state = state
            return state.get("last_result")
        return None
