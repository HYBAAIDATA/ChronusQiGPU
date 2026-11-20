# medical imaging archive — reference design / HOLD

Components: customer source → AL HARAS tenant admission → OVID transformation and exactness evidence → THESEUS durable custody and replay → customer export. Existing connector surface: object storage; DICOM/PACS adapter not verified (src/chronus/storage/connectors.py); source presence is not external integration evidence.

Trust boundaries: customer tenant and keys; connector admission; immutable custody; authorised export. Patient data remains in the authorised clinical boundary. DICOM compatibility and clinical safety review are open.

RACI (roles only, names and consent pending): customer data owner accountable; integration engineer responsible; AL HARAS security consulted; OVID exactness and THESEUS custody owners responsible for respective contracts; customer finance responsible for M&V; independent QC consulted; operator informed of escalation.

SLOs: availability, restoration time, durability, escalation and retrieval latency targets require customer agreement and exact-workload measurement. No numerical SLO is guaranteed. For M&V use [customer-operated report](../../docs/settlement/IPMVP_CONFORMITY.md). Validate baseline invoices, actual metered spend, scope, adjustments and every digest inside the customer boundary before settlement.
