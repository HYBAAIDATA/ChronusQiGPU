# Compliance & Government Readiness Checklist

This checklist ensures the IGPU deployment meets the typical requirements for regulated enterprise or government adoption.

1. Governance & Policy
   - [ ] Documented roles: operator, evidence approver, auditor
   - [ ] Governance policy repository with immutable change log
   - [ ] SLA and incident response playbook

2. Authentication & Authorization
   - [ ] mTLS for intra-service communication
   - [ ] Centralized identity provider (OIDC/SAML)
   - [ ] Role-Based Access Control applied per namespace

3. Data Protection
   - [ ] KMS-backed encryption at rest for PVCs and object storage
   - [ ] Key rotation policy
   - [ ] Tenant isolation and logical separation

4. Auditing & Provenance
   - [ ] SHA256d digest chain enabled for all ingests
   - [ ] Evidence receipts for each material decision (TOE receipts)
   - [ ] Immutable logs (WORM) for required retention period

5. Operational Controls
   - [ ] Readiness / liveness probes for every service
   - [ ] Fail-closed mode on missing evidence or hardware
   - [ ] Disaster recovery plan and journal replay tested

6. Compliance Testing
   - [ ] Penetration test report
   - [ ] Third-party audit (SOC 2 / ISO 27001) scoping
   - [ ] Regulatory checklist per jurisdiction (FCA/DFSA/FINMA templates)

7. Privacy
   - [ ] Data minimization and anonymization for pilot datasets
   - [ ] Export controls review (technical and contractual)

8. Documentation & Training
   - [ ] Operator runbooks
   - [ ] On-call escalation procedures
   - [ ] Playbooks for auditors

9. Legal & Contracts
   - [ ] Data processing agreement
   - [ ] Export controls clause
   - [ ] Liability and indemnity terms for evidence assertions

10. Certification
   - [ ] A final certification step where an authorized evidence approver marks the environment `production-ready` after all gates pass
