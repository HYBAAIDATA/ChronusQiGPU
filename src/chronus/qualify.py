"""Local diagnostics are never a production qualification verdict."""
from __future__ import annotations
import time
from chronus.gates import Fixture,GATES
from chronus.verdict import GateResult,Status,Verdict
from chronus.crypto.signers import SignerUnavailable

def qualify(fixture:Fixture,budget_s:float=120)->Verdict:
    start=time.monotonic()
    results=[]
    for gate in GATES:
        if time.monotonic()-start>budget_s:
            results.append(GateResult(gate.__name__,Status.UNQUALIFIED,"budget exhausted"))
            continue
        try:
            results.append(gate(fixture))
        except SignerUnavailable as exc:
            results.append(GateResult(gate.__name__,Status.UNQUALIFIED,str(exc)))
        except Exception as exc:
            results.append(GateResult(gate.__name__,Status.FAIL,f"{type(exc).__name__}: {exc}"))
    return Verdict(tuple(results))
