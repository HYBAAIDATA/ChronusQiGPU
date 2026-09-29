"""Claims that must not be promoted by generated pages or release text."""
CLAIMS_STILL_REFUTED=(
"PULVINI is compression","Pisot truncation is lossless","Prime addressing creates physical storage",
"Universal Binet compression","Lucas/Pisot quantum speedup","Exponential speedup","Unlimited capacity or speed",
"10 EH/s","One device equals 20,000 NVIDIA GPUs","Spectral gap is drug-binding energy",
"Simulator is physical quantum","Reference path is deployed silicon",
"Public-pool share validity from Cassini seal alone","Compliance pack is legal certification",
"Autonomous operations without acknowledgement","Any unmeasured performance claim")
class ClaimRefuted(ValueError):pass
def assert_claims(text:str)->None:
    folded=text.casefold()
    for claim in CLAIMS_STILL_REFUTED:
        if claim.casefold() in folded:raise ClaimRefuted(claim)
