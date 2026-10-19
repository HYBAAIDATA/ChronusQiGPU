"""Detached local custody snapshots; not signatures or independent attestations."""
from dataclasses import asdict, dataclass
import json

from ..models.candidate import DiscoveryEnvelope, EmergentCandidate, ReproductionProtocol


class CandidateCustodyError(ValueError):
    """An observed qualification input no longer matches its entry snapshot."""


@dataclass(frozen=True)
class CandidateSnapshot:
    payload: bytes
    fingerprint: str

    @classmethod
    def capture(cls, candidate: EmergentCandidate):
        payload = json.dumps(asdict(candidate), sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        snapshot = cls(payload, candidate.compute_fingerprint())
        snapshot.verify(candidate)
        snapshot.verify(snapshot.materialize())
        return snapshot

    def materialize(self):
        body = json.loads(self.payload)
        envelope = body.pop("discovery_envelope")
        envelope["parameter_bounds"] = {
            key: tuple(value) for key, value in envelope["parameter_bounds"].items()
        }
        protocol = body.pop("reproduction_steps")
        for key in ("seed_suite", "required_observables", "steps"):
            protocol[key] = tuple(protocol[key])
        return EmergentCandidate(discovery_envelope=DiscoveryEnvelope(**envelope),
                                 reproduction_steps=ReproductionProtocol(**protocol), **body)

    def verify(self, candidate):
        try:
            actual = candidate.compute_fingerprint()
        except (TypeError, ValueError, AttributeError) as exc:
            raise CandidateCustodyError("Candidate is no longer canonically serializable") from exc
        if actual != self.fingerprint:
            raise CandidateCustodyError("Candidate or protocol changed during qualification")
