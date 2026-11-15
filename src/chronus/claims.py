"""Claims are never promoted by gate evaluation; only demoted."""
from __future__ import annotations
from dataclasses import dataclass,replace
from enum import Enum
from chronus.verdict import Status

class Publish(str,Enum):
    PUBLISHABLE="publishable"
    HELD="held"
    RETIRED="retired"

@dataclass(frozen=True)
class Claim:
    code: str
    text: str
    gates: tuple[str,...]
    state: Publish=Publish.HELD

def gate_claims(claims:list[Claim], verdicts:dict[str,Status])->list[Claim]:
    result=[]
    for claim in claims:
        if claim.state is not Publish.PUBLISHABLE:
            result.append(claim)
        elif not claim.gates or any(verdicts.get(g) is not Status.PASS for g in claim.gates):
            result.append(replace(claim,state=Publish.HELD))
        else:
            result.append(claim)
    return result
