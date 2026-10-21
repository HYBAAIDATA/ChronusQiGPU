# Integrate with the actual interface

## Two software surfaces

The canonical VQC pipeline and the additive typed facade are distinct interfaces. The facade delegates computation; it does not replace all legacy wrappers or expose every algorithm in the engine.

| Surface | Meaning |
| --- | --- |
| Canonical pipeline | VQC request, stages, result, certificate/witness, optional custody/replay |
| Typed facade | Compile, submit/run, estimate, bounded local jobs and finite-family minimisation |
| Enterprise service | Separate organisation/access/capacity/metering integration; not inferred from local API use |

## Integration sequence

1. Obtain the reviewed source or approved distribution and its exact version.
2. Follow that candidate's installation and dependency instructions.
3. Run its genuine end-to-end example and inspect exact reference values.
4. Validate input domains, errors, timeout/cancellation and provenance handling.
5. Qualify your consumer against the exact wheel and sdist-derived build.

There is no newly documented public HTTP endpoint or invented authentication header here. Network authentication and API credentials must follow the actual deployed service, once qualified.

The internal developer manual links to authoritative generated signatures, installation, migration and executable examples rather than maintaining copied signatures. See [job semantics](lifecycle.md).
