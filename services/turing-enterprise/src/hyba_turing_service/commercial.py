"""Current approved scope; no pricing, charging unit or provider contract.

Hermitten avoided-cost data billing is separate. Future TURING/VQC billing is
contractually agreed usage-based billing; it is deferred in this release.
"""

BILLING_SCOPE = "deferred"


def validate_scope(config):
    if config.get("billing_scope", BILLING_SCOPE) != BILLING_SCOPE:
        raise ValueError("active billing needs an approved commercial contract and interface")
    for name in ("billing_url", "billing_token_file", "billing_import_path", "require_spend"):
        if config.get(name):
            raise ValueError("billing is deferred; legacy provider/spend wiring is not authorised")
    config["billing_scope"] = BILLING_SCOPE
