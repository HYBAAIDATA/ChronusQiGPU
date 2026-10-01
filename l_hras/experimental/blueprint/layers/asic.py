# l_hras/layers/asic.py

from dataclasses import dataclass

@dataclass
class ASICMeasurement:
    hps: float
    model: str
    attestation: str

def measure_asic() -> ASICMeasurement:
    """Measure ASIC H/s."""
    # ASICs are not typically attached to the host;
    # this returns 0 unless a pool API reports it.
    return ASICMeasurement(
        hps=0.0,
        model="none",
        attestation="asic_absent",
    )
