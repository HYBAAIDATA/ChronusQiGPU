# l_hras/floor/hashrate.py

from dataclasses import dataclass
from l_hras.experimental.blueprint.layers.chronus import measure_chronus
from l_hras.experimental.blueprint.layers.gpu import measure_gpu
from l_hras.experimental.blueprint.layers.asic import measure_asic


@dataclass
class Hashrate:
    chronus: float
    gpu: float
    asic: float
    total: float
    attestation: str


def measure_hashrate() -> Hashrate:
    """Measure the total hashrate from all layers."""
    chronus = measure_chronus()
    gpu = measure_gpu()
    asic = measure_asic()
    total = chronus.hps + gpu.hps + asic.hps
    return Hashrate(
        chronus=chronus.hps,
        gpu=gpu.hps,
        asic=asic.hps,
        total=total,
        attestation=f"hashrate_{total}",
    )
