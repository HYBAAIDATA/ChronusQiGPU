"""Claims that must not be promoted by generated pages or release text."""

CLAIMS_STILL_REFUTED = (
    "PULVINI is compression",
    "Pisot truncation is lossless",
    "Prime addressing creates physical storage",
    "Universal Binet compression",
    "Lucas/Pisot quantum speedup",
    "Exponential speedup",
    "Unlimited capacity or speed",
    "10 EH/s",
    "One device equals 20,000 NVIDIA GPUs",
    "Spectral gap is drug-binding energy",
    "Simulator is physical quantum",
    "Reference path is deployed silicon",
    "Public-pool share validity from Cassini seal alone",
    "Compliance pack is legal certification",
    "Autonomous operations without acknowledgement",
    "Any unmeasured performance claim",
    "Zeckendorf is generic address compression",
    "Float64 Binet is lossless at high indices",
    "Lucas/Pisot phase rule yields quantum speedup",
    "Prime-derived addressing creates physical capacity",
    "Positive spectral gap proves a domain property",
    "Cassini seal is proof-of-work",
    "Physical GPU/FPGA/ASIC/QPU throughput exists",
    "Missing OpenCL/Docker/HDL/Rust toolchain is a pass",
    "Exponential speed is universal",
)

# Phrasings retired from the quantum simulation modules. Each is a claim the
# repository does not support: a parallelism factor no assignment of the
# module's own constants produces, an unlabelled materialisation clamp, a
# placeholder difficulty fed into a cost estimate, and a field name that reads
# as a measured speedup when it is an oracle-query ratio. The source lint in
# ``quantum_compute_substrate/tests/test_amplitude_amplification.py`` keeps them
# out of the module; these entries keep them out of generated text.
CLAIMS_RETIRED_FROM_QUANTUM_MODULES = (
    "8192x parallelism",
    "8,192x parallelism",
    "Grover search at 8,192x parallelism",
    "theoretical_speedup",
)


class ClaimRefuted(ValueError):
    pass


def assert_claims(text: str) -> None:
    folded = text.casefold()
    for claim in CLAIMS_STILL_REFUTED + CLAIMS_RETIRED_FROM_QUANTUM_MODULES:
        if claim.casefold() in folded:
            raise ClaimRefuted(claim)
