# l_hras/floor/hashrate.py

from dataclasses import dataclass

from l_hras.experimental.blueprint.layers.igpu import measure_igpu
from l_hras.experimental.blueprint.layers.gpu import measure_gpu
from l_hras.experimental.blueprint.layers.asic import measure_asic


@dataclass
class Hashrate:
    igpu: float
    gpu: float
    asic: float
    total: float
    attestation: str


def measure_hashrate() -> Hashrate:
    """Measure the total hashrate from all layers."""
    igpu_meas = measure_igpu()
    gpu = measure_gpu()
    asic = measure_asic()
    total = igpu_meas.hps + gpu.hps + asic.hps
    return Hashrate(
        igpu=igpu_meas.hps,
        gpu=gpu.hps,
        asic=asic.hps,
        total=total,
        attestation=f"hashrate_{total}",
    )
