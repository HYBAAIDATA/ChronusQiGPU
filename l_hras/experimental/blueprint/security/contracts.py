# l_hras/security/contracts.py

CONTRACTS = {
    "Guardian": [
        "I will stand in all five modes at all times.",
        "I will entangle all six intelligences.",
        "I will attest every event I process.",
        "I will write every attestation to Aethel.",
        "I will refuse if any mode or intelligence fails.",
        "I will never transition. I will only stand.",
        "I will never sleep.",
        "I will never let the adversary pass.",
        "You shall not pass.",
    ],
    "Swarm": [
        "No single Guardian is the coordinator.",
        "The swarm continues if fewer than 1/3 fail.",
        "Every Guardian's output is attested.",
        "The topology changes as Guardians join and leave.",
        "The consensus threshold is 2/3.",
    ],
    "Intelligence": [
        "All six intelligences are entangled.",
        "A measurement on one collapses all.",
        "The entanglement is exact.",
        "The correlations are exact.",
    ],
    "Mode": [
        "All five modes are active simultaneously.",
        "No mode transitions to another mode.",
        "No mode is a response. All modes stand.",
    ],
    "Aethel": [
        "Every attestation is written to Aethel.",
        "Aethel's address space is open-ended.",
        "Each block is one finite payload.",
        "Aethel is replayable.",
        "Forgery of Aethel fails replay.",
    ],
    "Floor": [
        "The floor is 10 EH/s.",
        "The floor is gated on measured hashrate.",
        "No multipliers are applied to the hashrate.",
        "The floor is attested.",
        "The floor is replayable.",
    ],
}
