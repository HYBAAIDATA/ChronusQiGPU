# hyba-salamander

SALAMANDER — the canonical fail-closed autonomic control plane.

`salamander` provides bounded actuation under an independent authority:
every action must be authorised by the bundled AL HARAS guardian, every
actuator carries an independent postcondition verifier, and every decision
is committed to a tamper-evident evidence ledger. An unauthenticated or
unregistered actuation attempt is refused — there is no permissive path.

```python
from salamander import ActionRegistry, EvidenceLedger
from salamander.control_plane import FailClosed

ledger = EvidenceLedger()
digest = ledger.append("boot", {"ok": True}, at_ns=1)
assert ledger.verify()

registry = ActionRegistry()
try:
    registry.execute(None)  # no bound AL HARAS authorization
except FailClosed:
    pass  # refused, as required
```

The wheel ships `salamander` plus the bundled `al_haras` guardian
substrate. `salamander.discovery_optimisation` remains importable but its
authority-boundary constants (`toe.intelligences`) are outside the product
boundary; without them every discovery candidate is refused fail-closed
rather than admitted without the forbidden-domain check.
