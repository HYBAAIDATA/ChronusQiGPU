# Limitations and frequently asked questions

## Is this physical quantum hardware?

The documented software mathematics does not require a physical QPU. The inspected package has no bundled provider adapter. Only actual completed provider-job evidence could support a measured-QPU claim.

## Does a large qubit count admit every circuit?

No. Admission depends on the representation, state/gate class and resource envelope. Tableau Clifford execution and statically bounded exact MPS do not establish unrestricted universal computation at the same width.

## Does exact mean all outputs are exact numbers?

No. Certified exact coefficients, floating display conversions and sampled observations have different meanings. A sampled estimate has sampling uncertainty even when its underlying mathematical distribution is exact.

## Can a running local job always be cancelled?

No. The current native facade supports cancellation before execution; a running computation drains. A wait timeout does not terminate or resubmit work. Local job recovery and idempotency are not durable service guarantees.

## Are security certification, uptime and performance guaranteed?

Not by this documentation. Such claims require specific independently reviewable evidence and, where applicable, approved contractual terms.

## Where is the research?

See [research and reproducibility](../research/overview.md). A manuscript scaffold is not a peer-reviewed publication. No DOI, novelty priority or accepted paper is assumed.
