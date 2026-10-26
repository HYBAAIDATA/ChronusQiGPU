# API lifecycle policy (2B.6 / 2B.7)

How canonical interfaces are versioned, how compatibility is preserved, and
how interfaces are deprecated. This policy binds every entry in
`governance/api_registry.yaml` and the merged constitution in
`docs/SERVICE_CONSTITUTION.yaml`. It is enforced by
`tests/test_service_constitution.py`.

## Versioning

Every interface carries a `version` equal to its registry `schema_version`
(e.g. `chronus.mla1517.status/1`, `remote_opencl_v2`). The trailing integer
is the contract major version.

- **Additive changes** — new optional response fields, new query
  parameters, new endpoints under an existing registered api — are allowed
  within the same major version and require only a registry update plus
  re-render of the contract docs.
- **Breaking changes** — removing or renaming a field, changing a field's
  type, changing an emitted `OPERATIONAL_ERROR` code, tightening an
  authentication class, or changing verdict semantics — require a new
  `schema_version` (major bump) on a new entry or an explicit version
  transition declared in the registry.

An unversioned breaking change is a contract drift violation: the gate
fails when a non-`LEGACY`, non-`RESERVED_NAMESPACE` entry lacks a
`schema_version`, or when an alias loses its `canonical_successor` link.

## Compatibility

- `CANONICAL` entries are the stable contract. Consumers may rely on the
  declared request/response schema, error taxonomy, and truth class.
- `COMPATIBILITY_ALIAS` entries are frozen aliases (currently
  `legacy.api_health` → `pythia.health`). An alias must not diverge from
  its canonical successor and must not gain new semantics.
- `RESERVED_NAMESPACE` entries are permanently reserved prefixes guarded
  by the AL HARAS boundary. A reserved namespace may only be promoted to an
  implemented API by a new canonical registry entry with architecture
  sign-off; a reserved namespace must never silently gain a handler.
- `DEPRECATED` entries are removal candidates; they must not gain new
  consumers and must keep working until the deprecation window closes.

## Deprecation procedure

1. Mark the entry `deprecation_state: DEPRECATED` in the registry and name
   the `canonical_successor`.
2. Announce the deprecation window in the rendered contract docs (the
   renderer emits the deprecation state).
3. Keep the interface serving through the window; consumers are inventoried
   in each entry's `consumers` field — every listed consumer must have a
   migration path before removal.
4. Remove the route and its registry entry together in one PR; the contract
   suite fails if a route is removed while still registered or vice versa.

## Consumer inventory (2B.4)

Every API's `consumers` field is the authoritative caller inventory. The
constitution gate requires the field to be non-empty for every entry —
including `operators`, `operator-console`, `load-balancer`, internal
callers, or wire peers — so a change can always name its blast radius.

## Ownership

Every API's `lifecycle_owner` resolves to the owning subsystem plus the
named accountable owner (`@bollingertm`, the repository owner of record in
`.github/CODEOWNERS`). The lifecycle owner owns version bumps and
deprecation decisions for that interface.

## Error taxonomy

Error codes are part of the contract. Every emitted code is registered in
`docs/ERROR_TAXONOMY.yaml`; a new code or a removed code without a taxonomy
update fails the gate. `DYNAMIC_DETAIL` and `AVAILABILITY_PROSE` content is
never contractual.

## Correlation standard (2B.9)

Every HTTP response carries `X-Request-Id`: a sane caller-supplied
`X-Request-Id`/`X-Correlation-Id` is echoed, otherwise a fresh id is
minted — including on denial paths. AL HARAS signed receipts carry
`request_id`/`evidence_id` so a denied call is end-to-end correlatable.
