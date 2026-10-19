# PYTHIA contract drift report

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

Compares the three projections of the contract — registry,
service fabric, and runtime — for unexplained divergence.

- registry: `pythia.api_registry/2` — 64 interfaces
- fabric: `pythia.service_fabric/1` — 85 dependency edges, 18 failure classes
- runtime taxonomy: `18` classes

## Result

**Zero unexplained divergence.** The registry's per-interface
dependency lists equal the fabric graph in both directions, the
fabric's failure enum is the runtime enum, and the control API's
error envelope applies the taxonomy at the single choke point.

