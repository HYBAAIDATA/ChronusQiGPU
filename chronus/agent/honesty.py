"""Every asserted execution/observation/verification/completion needs matching evidence."""

from dataclasses import dataclass
from ._contracts import ContractError, text, sha


@dataclass(frozen=True)
class Claim:
    text: str
    execution_refs: tuple[str, ...] = ()
    observation_refs: tuple[str, ...] = ()
    verification_refs: tuple[str, ...] = ()
    derivation_refs: tuple[str, ...] = ()
    completion_refs: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    authorization_refs: tuple[str, ...] = ()

    def __post_init__(self):
        text(self.text)
        for name, value in self.__dict__.items():
            if name != "text":
                if type(value) is not tuple:
                    raise ContractError("immutable evidence references required")
                for ref in value:
                    sha(ref)


def honest_report(claim, *, established_refs):
    required = {
        "executed": claim.execution_refs,
        "observed": claim.observation_refs,
        "verified": claim.verification_refs,
        "completed": claim.completion_refs,
        "proven": claim.proof_refs,
        "approved": claim.authorization_refs,
    }
    return {
        "claim": claim.text,
        "states": {
            name: bool(refs) and all(ref in established_refs for ref in refs)
            for name, refs in required.items()
        },
        "assertion": "evidence-qualified; unsupported states are not established",
    }
