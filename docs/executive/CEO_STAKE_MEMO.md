# CEO decision — attested storage closure
**HOLD | Internal decision memorandum | 19 November 2026**

## What is at stake
Audit defence takes staff time and evidence retrieval resources; a trustworthy log is necessary but not a quantified cost saving. [NIST SP 800-92](https://csrc.nist.gov/pubs/sp/800/92/final), inspected 2026-11-19.
For high-risk AI systems, Article 12 requires automatic event logging; applicability must be assessed per deployment. [European Commission, Article 12](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12), inspected 2026-11-19.
Silent data corruption can cause undetected incorrect results in large fleets. [Meta engineering field report](https://engineering.fb.com/2021/02/23/data-infrastructure/silent-data-corruption/), inspected 2026-11-19.
No HYBA-specific cost, regulatory conformity or fleet risk reduction is asserted.

## The argument
- Fold group law — formal source; independent replay pending; not a capacity claim.
- Ergodicity programme — research direction, not completed or certified.
- Fold-residency — event log 7/8, object store 6/7, analytics 1/6 on committed synthetic traces. Analytics is boundary-heavy (five of six operations); thresholding makes its join empty. No general workload inference. Matched identity/candidate observations and outputs; measured, not benchmarked. Evidence: `evidence/residency/0f94d2d6ae917eb819943dda6cb7d58baa99a08c/campaign.json`, SHA-256 `95da6c4d659c8795765ac14512840423bfa6559824777b5835c6e72ae2d396c9`. Independent replay pending.

## The ask
Approve the independent TEI study budget; authorise the customer-operated measurement campaign and consent-based reference interviews; appoint named support, dispute, security, maintenance and QC owners.
No publication or production sign-off before the findings and independent QC gates close.
