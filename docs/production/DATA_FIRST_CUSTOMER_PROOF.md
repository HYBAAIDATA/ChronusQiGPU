# HYBA Data — first customer proof and commercial admission

**Status:** internal commercial engineering contract, not public marketing copy.
**Scope:** data-first Chronus–OVID–THESEUS capability. Internal treasury/mining
operations are confidential and excluded from this demonstration, customer
packages, press, external MCP descriptions and public evidence.

## The first reproducible transaction

A prospective customer's actual, licensed workload is admitted only after the
operator verifies the dataset rights and provides a **private** manifest:
`chronus.real-workload-manifest/1`. The current bounded proof processes either
safe NumPy tensor inputs or opaque state snapshots (max 16 MiB by program
policy, typically **1 MiB per source** under THESEUS's default custody limit).
Other proprietary file formats, arbitrary custom tensor encodings, live
connectors and large datasets are **not** covered by this path.

```bash
# Run from the private repository checkout, using its installed dependencies.
# Operator supplies existing private files, not generated test data.
python benchmarks/real_workload_benchmark.py \
  --manifest /secure/customer-demo/manifest.yaml \
  --custody-db /secure/customer-demo/triad.sqlite3 \
  --output /secure/customer-demo/benchmark-evidence.json

# Produce a concise internal demonstration brief from the verified evidence.
# The summarizer rejects test fixtures, invalid hashes or missing readback.
python scripts/demo/real_data_proof_report.py \
  --evidence /secure/customer-demo/benchmark-evidence.json \
  --output /secure/customer-demo/customer-proof.md
```

The output demonstrates the **implemented software** chain: source SHA-256,
Chronus reference execution, OVID reversible representation, THESEUS durable
local custody, fresh-instance readback and independently compared values.
PULVINI's numerical fold reports full kernels and tolerance; it does not imply
lossless byte compression. Exact H4 traversal is **UNAVAILABLE** for a general
input. Real input and local measurement do not imply production approval,
independent signing, external cloud deployment or customer acceptance.

This is a private demonstration protocol. Its receipts and report must be
independently reviewed before use in a buyer/investor meeting; remove paths,
tenants, data names, PII, secrets and unapproved proprietary information.

## What a buyer is shown

1. **Source and permission:** exact file rights, controlled input SHA-256 and
   declared transformation fidelity. Do not display the original private
   dataset or claim its authenticity beyond evidence received.
2. **Execution:** run the maintained code on that same input; identify
   software reference vs device backend, and record exact source commit.
3. **Reversibility:** inspect output equivalence, accepted numerical tolerance
   and complete kernel/serialization costs; no unmeasured net compression.
4. **Custody:** use the maintained OVID–THESEUS transaction and a *fresh*
   service instance to verify materialised bytes and journal continuity.
5. **Evidence:** present original input SHA-256, measured timing units,
   recovered-data verdict, source commit, custody receipts and limitations.
6. **Customer decision:** collect written acceptance criteria, the selected
   dataset, authorised users, contractual protection and next environment
   before starting a paid proof-of-value.

## Four distinct commercial gates

| Gate | Evidence needed to pass | Initial status |
| --- | --- | --- |
| Software transaction | Exact code SHA, runnable commands, regression results, byte/numerical fidelity and restart receipts | Implemented; new PR tests not yet validated on full current checkout |
| Customer security | AL HARAS trusted authentication and tenant separation, role policy, key custody, logging, deletion and data rights | UNVERIFIED for a customer environment |
| Deployment and operations | Identified hosted environment, secret management, backup/restore, error recovery, rollback, support and monitoring results | UNAVAILABLE |
| Commercial admission | Approved service description, measurable target workload, same-workload cost baseline, pricing, liability terms and customer sign-off | UNVERIFIED |

A software demonstration may be shown **privately** with its actual evidence
without calling the full service production-qualified. Production admission
is governed by the existing exact-commit qualification gates, not this file.

## Funding and market claims: evidence-only use

The attached business proposals discuss CIaaS, four routes to market (sovereign,
enterprise, hyperscaler and data-centre), capability-based economics, gain-share
and modular service packaging. They are **product hypotheses and design inputs**,
not sufficient evidence that Gartner assigned a Magic Quadrant position, that
a company has certifications, that 13× acceleration was measured on this
release, or that illustrated TAM, forecast revenue, price cards, customer logos,
SLAs or partnerships have been verified. Keep claims in `docs/claim-audit.md`
until independently supported by primary documents and current execution.

The shortest credible paid-offer sequence is a **direct, bounded, private
data-service proof-of-value** for one approved customer workflow, then
enterprise integration and scale. Do not promise marketplace one-click
provisioning, sovereign certifications, or hardware performance before the
relevant integration and qualification evidence exists.

## Closeout responsibilities

- **Engineering:** run current software tests locally where possible; record
  exact revision, interpreter/dependencies, commands, raw output, failures,
  coverage and reproducible diagnosis. Continue Qodo/CodeRabbit issue closure
  on the original PR; do not conceal failing checks.
- **Verification:** independently reperform authorised real-input readback and
  compare against known input hash, shape, dtype and fidelity contract.
- **Security/operations:** test tenant isolation, AL HARAS principal validation,
  backup/restore, bounded errors, rollback and support incident handling.
- **Commercial:** confirm dataset rights, the actual first buyer's acceptance
  vector, required SLA and contract/payment structure; do not infer from sample
  revenue models or placeholder tier prices.
- **Release owner:** reconcile CI/runner availability and mandatory attested
  qualification; **do not manufacture a green CI status or release approval**.

All work remains private until the owner explicitly approves any commercial
publication or deployment. A data branch is not a secrecy boundary for shared
mining Git history; externally distributed packages must undergo independent
content/history review.

## Architecture reconciliation hold

A separate historical HYBAEnterprise QC note supplied for this closeout assigns
authoritative enduring custody to OVID and rebuildable projection/index roles
to THESEUS. The **maintained ChronusQiGPU repository**, however, implements
OVID representation transformation/materialisation and THESEUS durable custody
in `src/chronus/triad.py`. This is a concrete authority-map discrepancy
between artifacts, not permission to silently invert production ownership.
Before customer contractual documentation or an architectural migration,
reconcile the current owner-approved register, existing data migration and
recovery guarantees, and the runtime's actual ownership. **No authority
change is made by this benchmark or demonstration report.**
