# Hermiten measurement and verification report

**HOLD — Option C-style cost adaptation, not certified IPMVP conformity.**
IPMVP is an energy savings protocol; its measurement boundary and baseline
principles are applied here to a customer-defined cloud cost boundary.
Source: [EVO protocols, Option C and Option D](https://www.evo-world.org/en/822-main-menu/product-a-services/protocols), inspected 2026-11-19.

| Settlement line | Method |
|---|---|
| Counterfactual spend | Option C: customer baseline invoices plus explicit signed adjustments |
| Actual spend | Option C: customer tenant-metered spend in the reporting boundary |
| Net avoided | max(0, counterfactual minus actual) |
| Value share | 25% of net avoided, contract hermiten-net-avoided/1; source: docs/FINOPS_AND_COMMERCIAL_ROI_BRIEF.md at f7fa3002c272c80d9055443fed652e3bb2dccc79, section 2 |
| Customer retained | net avoided minus value share |

Option D requires committed calibrated model, parameters, calibration inputs
and independent validation. counterfactual_option=D_pending_simulator_artifact.

The report contains the measurement boundary, reporting period, baseline period,
adjustments, currency, contract version and SHA-256 of each embedded input.
Customer finance supplies the actual monetary source lines and validates origin
and completeness; the customer recomputes all lines offline with
chronus.service.ipmvp.verify_report. Exact rational minor units are preserved;
no payment rounding policy is asserted. Digests identify inputs, not authorship.

The current /billing/usage and /billing/hermiten/usage endpoints explicitly
report CCU, not an invoice. Do not relabel such receipts as metered currency
or use the AL HARAS transfer-batch settlement as a cost report.
No customer invoices, independently attested tenant cost data, approved M&V
plan or calibrated model were supplied. This report code does not issue invoices,
authenticate source origin, or grant production qualification.

Acceptance: python -m pytest -q tests/test_ipmvp.py.
The arithmetic fixtures establish recomputability only; a real customer report
and its source verification remain open findings.
