# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""HYBA Mine: HYBA's internal, private treasury mining runtime.

HYBA Mine is an in-house treasury activity. It is not a product, not a
service and never customer-facing. It consumes the Chronus platform (the
Chronus iGPU, the Stratum primitives in ``chronus.execution.stratum`` and
``chronus.stratum``, the golden stride in ``chronus.execution.elevation`` and
the Hendrix tables in ``chronus.hendrix``); Chronus and the HYBA products never
import HYBA Mine.

Ground rules the code enforces:

* The pool's acknowledgement is the only witness of a share. A submitted share
  is not an accepted share; the ledger records the pool's literal reply.
* Hashrate is reported only from executed, timed device work.
* SHA-256d of the header compared with the share target is the only accept
  predicate, and every candidate is rechecked on the host before it is sent.
* Missing device, credential, job or operator approval: nothing is hashed or
  submitted.
* Pool logins stay on the operator's machine (macOS Keychain or a 0600 file
  outside the repository) and are never written to the ledger or the logs.
"""

__version__ = "0.1.0.dev0"

PRODUCT_BOUNDARY = (
    "HYBA Mine is HYBA's internal treasury mining runtime; it is not a product "
    "and is never customer-facing."
)
