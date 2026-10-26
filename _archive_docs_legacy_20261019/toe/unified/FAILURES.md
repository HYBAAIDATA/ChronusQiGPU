# Failures

These fail closed:

- Missing credentials, an unknown protocol, or an unbound transport raises `ConnectorUnavailable` before a write.
- A non-object ingest row raises `TypeError` before any row in that call is stored.
- An unknown question raises `QueryError`.
- An unfitted model raises `ValueError` from `exact_linear`.
- A joint tensor state is rejected by the trainer.
- `range` preprocessing raises on a constant column.
- With `security.enforced` set, an actor without the action's role raises `AccessDenied` before the write.
- `require_gate` raises `GateUnavailable` when that gate has no measured source.
- A negative scholarship amount raises `ValueError` and writes no entry.
- A negative queue depth raises `ValueError` from `scale()`.


The claim register has no `UNSUPPORTED` rows. Each former gap now has a test named in `reports/toe_unified_disposition.md`.
