"""Al Haras protection layer, migrated and adapted from HYBA_PROD_READY.

This package ports the concrete, dependency-light Al Haras primitives that
were verified to be real (not decorative/simulated) during the HYBA_PROD_READY
audit: a tamper-evident audit chain, a pre-launch secret-hygiene/security
gate, and a general-purpose byte-level compression utility.

HYBA_INTELLIGENCE's own protection surface was previously limited to a
single `hyba_genesis_api/api/security.py` API-key check. This package adds a
real, testable protection layer underneath it.
"""

from al_haras.quantum_defense.five_form_swarm import FiveFormDutySwarm, IntelligenceForm

from al_haras.millennium_security_stack import MillenniumSecurityStack
