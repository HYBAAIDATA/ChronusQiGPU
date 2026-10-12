# PI-01 Claim–Evidence–Decision enforcement

The governing program is **Evidence Restoration and Operational Hardening**.
Preserve domain authority; strengthen surrounding infrastructure; require executed
evidence for readiness claims. Architecture and code presence are not qualification.

## Implemented controls

`governance/cedr.json` is the readiness register. It seeds the owner's 23 claims;
none is represented as qualified. `al_haras/cedr.py` evaluates required claims against
an exact candidate commit, the SHA-256 of actual artifact bytes, the approved scope,
authorized Ed25519 reviewer keys, required executed acceptance checks, current review,
retention and freshness. Missing or malformed evidence blocks promotion.

- PASS, FAIL, SKIP, NOT_RUN and execution ERROR remain distinct. Only PASS qualifies a
  required check; FAIL/ERROR invalidate execution. SKIP/NOT_RUN never imply success.
- VERIFIED and CONDITIONALLY VERIFIED are the only potentially eligible statuses.
  Conditional verification also needs signed, unexpired risk acceptance.
- Packages bind the reviewed claim statement, title and owner, claim identity, build identity, source commit, artifact, scope,
  execution time, custody window, limitations, review and expiry. Package content and
  artifact bytes are digested; a package signature is verified against the profile's
  reviewer trust policy. A signature does not prove factual correctness.
- Production requires the `mining-production` profile, including hardware qualification;
  the weaker pilot profile cannot issue a production receipt.
- `scripts/advance_state.py` re-evaluates CEDR **before issuing a promotion receipt**.
  The promotion workflow builds one candidate wheel, retains it, and evaluates those
  exact bytes after environment approvals. Approval alone is not qualification.
- `make release-gate` additionally requires a CEDR decision after mandatory assurance
  gates and defect closure. Both release and promotion fail closed.

## Policy configuration still required

An accountable reviewed change must set each intended operating scope, owners,
reviewer **public keys** and key IDs, maximum evidence age, and custody locations.
The seed intentionally contains null scope/freshness fields and no trusted reviewers;
this is not permissive default configuration. Never commit private signing keys or
credentials. Required acceptance-check names are explicit per claim in each profile.

Evidence producers retain a `cedr.evidence/1` JSON package with claim ID, source commit,
artifact digest, build ID, scope, execution date, retained-until, checks, limitations,
freshness and review. Each check has name, result, execution reference, retained_artifact (a relative file
within custody) and retained_digest. The gate hashes the retained execution bytes;
a reference string without the retained evidence cannot qualify a claim.
Attestation records reviewer, key ID, Ed25519 algorithm, trust policy and hexadecimal
signature over canonical JSON of the complete package excluding `attestation` (sorted
keys, compact separators, finite JSON). The register records its package path and digest.
Packages and candidate artifacts must remain within the checkout/custody root. Reviewers
must inspect actual retained evidence before signing; the engine cannot establish the
truth of an external log merely from a reference or a signature.

No scope, approval, acknowledgment, hardware result, or fleet qualification is invented.
Actual telemetry/identity/hardware failure exercises remain required work; passing the
engine's unit tests qualifies its tested behavior, not those operational claims.

## Commands

```bash
# Structural validation only; this is explicitly not a readiness certificate.
python -m scripts.cedr_gate --validate

# Evaluate a retained candidate. Initially exits nonzero: claims remain unqualified.
python -m scripts.cedr_gate --profile pilot-operations --artifact dist/candidate.whl

# Full release gate; never bypass assurance or defect closure.
make release-gate CEDR_PROFILE=mining-production CEDR_ARTIFACT=dist/candidate.whl
```

The complete CEDR decision digest is included in the signed promotion receipt.
The JSON decision report is retained at `results/cedr-decision.json`. Do not add
`|| true`, convert unknown to accepted, relax thresholds to match observed failures,
or administratively bypass required review. Cloud-dependency profiles separately require
CEDR-100/101/102 evidence; they do not provision Azure resources or authorize spending.

## Test and operational distinction

The CEDR CI job validates structure and exercises positive/negative controls with
isolated artifacts and ephemeral fixture keys. Fixture reviewers are never installed
in production policy. Green engine tests are not a green operational release decision.

A next-phase go/no-go still requires all mandatory CI checks, required approving review,
and eligible CEDR claims within the actual intended scope. Unavailable hardware remains
UNVERIFIED; missed evidence freshness becomes STALE. No live mining or deployment is
performed by adoption of this program.
