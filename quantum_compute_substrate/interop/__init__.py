"""
Interoperability adapters for AI/ML, HPC, cloud, and edge deployments.

All adapters degrade gracefully when the target framework is absent.
"""

from .ml_adapters import TorchAdapter, TensorFlowAdapter
from .hpc_adapter import MPIAdapter
from .cloud_adapter import KubernetesManifest
from .edge_adapter import EdgeDeployment
