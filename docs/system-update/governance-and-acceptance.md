# Governance and acceptance — process guidance

This document describes a proposed evidence process. It is not proof that any control, test, review, or release gate has been completed.

## Evidence record for a material claim

For each security, compliance, customer, performance, reliability, or financial claim, record:

- exact claim and intended audience;
- source commit and relevant implementation path;
- test or assessment method, environment, and raw artifact;
- result, limitations, exceptions, and date;
- accountable owner and independent reviewer;
- approval status and expiry/reassessment trigger.

## Release decisions

A release decision must be based on a defined acceptance plan and current evidence, not on the presence of code, a test file, a dashboard label, a historical report, or a CI workflow configuration. Separate functional tests, security review, compliance authorization, operational readiness, physical-hardware validation, and customer acceptance. Mark items “not demonstrated” until the relevant evidence is reviewed.

For the current repository status and withdrawn claims, see the [claim audit](../claim-audit.md).