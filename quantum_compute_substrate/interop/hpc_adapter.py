"""HPC integration — MPI/OpenMP for supercomputer deployment."""

import importlib
from typing import Any, Dict, Optional


def _try_import(name: str) -> Optional[Any]:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


class MPIAdapter:
    """Adapter for mpi4py."""

    def __init__(self):
        self.mpi4py = _try_import("mpi4py.MPI")
        self.available = self.mpi4py is not None
        self.rank = 0
        self.size = 1
        if self.available:
            self.comm = self.mpi4py.COMM_WORLD
            self.rank = self.comm.Get_rank()
            self.size = self.comm.Get_size()

    def status(self) -> Dict:
        return {
            "framework": "mpi4py",
            "available": self.available,
            "rank": self.rank,
            "size": self.size,
        }

    def all_reduce_sum(self, value):
        if not self.available:
            return value
        return self.comm.allreduce(value, op=self.mpi4py.SUM)
