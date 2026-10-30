# Who Pays When the Control Plane Fails — A City Note on Delivering and Contracting AL HARAS

<aside>
⚖️

**For the board and the general counsel.** If HYBA sells security as the absence of incidents, we will lose the argument the first time a sophisticated buyer’s external counsel opens the schedule. If we sell a **specified control plane**—fail-closed gates, sealed decisions, crypto-agility tooling, intelligence that assists path analysis—and we price and cap liability for **defects in that specification**, we are bankable. The rest of this note is how a City C-suite that reads the *Financial Times* should expect the product to be delivered, and how a technology, IP, privacy, AI and cyber lawyer who has sat on the bank side of those negotiations would allocate risk when it goes wrong.

</aside>

---

## Author’s lens

This is written as if for a Monday morning read between the markets open and the risk committee pack: not a sales annex, not a developer runbook.

The contracting instincts come from advising on **software, technology, IP, privacy, AI and cyber** on the institutional buy-side—including cyber terms and liability questions of the kind that dominate bank MSAs—and from earlier work in **market data** (Deloitte) and **risk** (EY). That background matters because market-data and risk professionals already understand a truth cyber vendors often obscure: **you can be paid for a feed, a model, or a control, without underwriting the client’s P&L for the universe.**

HYBA’s commercial doctrine remains: **HYBA paper**—MSA, service schedules, order forms—not the bank’s standard tech schedule wholesale. That is not arrogance. It is category honesty. A control-plane and CIaaS economics do not fit a commodity SaaS template written for seat licences and uptime credits alone.

**Related:** [Legal Operations: HYBA Contracting Doctrine & MSA Architecture](https://app.notion.com/p/Legal-Operations-HYBA-Contracting-Doctrine-MSA-Architecture-12989f3a8398494784c918656ae96498?pvs=21) · [HYBA Security White Paper — AL HARAS & Market Offerings (Board Draft)](HYBA%20Security%20White%20Paper%20%E2%80%94%20AL%20HARAS%20&%20Market%20Offe%2023c5f0750d10439fa6570548a0a78f7a.md) · [HYBA Product Portfolio — Full Architecture, SDK & Deployment (Ready)](HYBA%20Product%20Portfolio%20%E2%80%94%20Full%20Architecture,%20SDK%20&%20%20decc9092994043c5802627dc6058316e.md) · [Thought Piece — When Defence Still Assumes the Old Adversary](Thought%20Piece%20%E2%80%94%20When%20Defence%20Still%20Assumes%20the%20Old%200418afc7ca9f43519729b1246519d9be.md)

---

## 1. The board question is not “SDK or API?”

It is: **on whose stack does liability crystallise when something expensive happens at 3 a.m.?**

Delivery mode is how we answer that before the incident, not after.

### Four ways the City will actually take the product

**First, the library.** A versioned SDK in the client’s process—Python first, native bindings where latency or mobile/edge demand it. Lowest friction for engineering. Lowest HYBA operational surface. Highest customer duty to call it on the right paths. If the attack never touches the gated path, that is not a product failure; it is an integration fact.

**Second, the control plane.** REST or gRPC: clearance, audit append and verify, configuration, intelligence services. This is what security engineering and SOAR teams buy when the estate is plural. Here HYBA takes on **availability and access control of our plane**. We still do not take on the client’s entire cyber residual.

**Third, the runtime package.** Container, Kubernetes sidecar, optionally a host agent; air-gapped images for sovereign buyers. This is how platform teams standardise policy. Image CVEs and patch SLAs become ours where we ship the artefact; misconfiguration remains theirs.

**Fourth, the sovereign or single-tenant instance.** Customer VPC or on-prem, sometimes HYBA-operated under strict access. Ministries and certain banks will insist on this. We deliver verified artefacts and a harness; they operate. Support runs under sealed change control—not unlimited remote admin folklore.

Commercially, those surfaces map to packages, not poetry: a **core** security package (audit, production guard, AEAD, basic gate client); a **premium** intelligence and adversarial layer; optional **Salamander** proposals under a human gate; and **PULVINI / HERMES** only ever on **separate schedules**. Mixing data-plane gain-share with security-event indemnity in one schedule is how deals become incoherent under cross-examination.

### Acceptance is not bureaucracy—it is the warranty clock

No production reliance warranty should start until an **Acceptance Pack** is signed: version pins and SBOM; claim boundary for that SKU; harness results the client can re-run (tamper fails verify, guard blocks bypass, AEAD rejects bit-flips, gate deny/allow fixtures); RACI for keys, heal approval, and tickets; shared-responsibility matrix on the order form.

Until then, it is a pilot under evaluation terms. City institutions understand pilots. What they will not forgive is a production outage attributed to software that never passed a joint acceptance gate.

---

## 2. What “getting it wrong” means in a dealing room

After a serious incident, the FT does not print “vendor class F3.” The headline is simpler. Inside the bank, counsel will still need a taxonomy—or the claim becomes “everything is your fault because you sold security.”

### The only distinction that survives scrutiny

**HYBA does not warrant that the customer will not suffer a security incident.**

HYBA warrants that **deliverables materially conform to a written specification**, and that **documented control behaviours**—including fail-closed denials and audit-integrity properties under an agreed test suite—operate as specified when deployed and used in accordance with the documentation and the shared-responsibility matrix.

That is the same intellectual move market-data contracts make when they warrant feed integrity and timestamps, not that the desk will make money. It is the same move risk systems make when they warrant calculation conformity to a methodology, not absence of market loss.

### Nine ways it goes wrong—and who owns the narrative

**Control defect.** The audit verifies after tamper; authenticated encryption accepts modified ciphertext; a documented fail-closed path allows execution without clearance. This is **ours**, subject to cap and proof. It is the closest thing to a classical “product liability” story in this stack.

**Availability and support.** The control plane is down beyond SLA; a critical vulnerability in an image we ship is not patched in the promised window. **Service credits** first; limited damages only if the schedule says so. Uptime is not a cyber-insurance policy.

**Intelligence miss.** Six-form analysis does not flag a novel campaign; a predictive score is wrong. This is **customer residual** unless the schedule foolishly warranted completeness. No serious bank’s own models carry that warranty internally; they should not extract it from a vendor by adjective.

**Integration and misuse.** SDK not on the path; guard disabled; wrong keys; APIs called outside contract; bypass flags in production. **Customer.** If our own production-guard philosophy treats bypass as hostile, the contract should treat intentional disablement as material breach and suspend our liability for what follows.

**Estate residual.** Phishing, insider, unpatched applications outside the gated path, physical access, the client’s other vendors. **Customer.** Always.

**Representation mismatch.** Someone in sales promised “unhackable” or “zero breach or we pay.” That is a **HYBA commercial failure** of discipline. Cure it with entire-agreement language, claim-boundary annexes, and a forbidden-phrases list—not by litigating metaphors.

**IP.** Our code infringes. **Standard HYBA indemnity**, with the usual carve-outs for combinations, modifications, and obsolete versions.

**Privacy.** We process personal data outside the role we contracted. **Ours**—but only for data we actually process. Do not claim “zero access” in a SaaS API that sees content. Deloitte market-data work teaches the same lesson: **role follows the pipe**, not the brand.

**Extraordinary adversary class.** Nation-state novelty, physical compromise of roots of trust, events outside the published threat-model annex. **Excluded or shared** as scheduled. EY risk culture would call this residual risk appetite, not a vendor gift.

---

## 3. How the City will attack the paper—and how we hold it

Expect the buy-side playbook.

They will ask for **unlimited liability for “security failure.”** No control vendor that remains solvent accepts that. Offer a **general cap** at fees paid under the *Security Schedule* in the prior twelve months; optionally a **priced super-cap** (two or three times fees) for proven control defects causing defined direct losses. Keep fraud, certain IP indemnities, and wilful misconduct in the usual carve-outs. Never open the cap to ransom, lost profits, or the bank’s own regulatory fines for the bank’s own duties.

They will define **“security incident”** as any malware anywhere in the group. Refuse. Define it as **failure of an in-scope control on an in-scope path**, established under a **joint forensic protocol**: preserve versions, configs, audit roots, digests; reproduce on the sealed build; classify; then talk about money.

They will demand indemnity for **all third-party breach claims.** Limit HYBA’s indemnity to control defects and HYBA negligence; require the customer to indemnify for misuse and estate residual.

They will assert HYBA is **processor of crown-jewel data.** Answer with architecture and the order form. Edge SDK and customer-hosted plane often mean we are not. A multi-tenant API that inspects payloads may mean we are—**price the DPA** and stop pretending otherwise.

They will want **most-favoured security terms.** Reject. Deviations live on the order form for that business unit only, per HYBA’s modular MSA doctrine—so one ops team’s fifteen-minute alert clock does not rewrite the group MSA.

They will want **unlimited audit rights.** Annual, reasonable, confidential, cost-shifting if they find nothing material.

This is not hostility. It is the same craft used when banks buy market data, cloud, and model risk tooling. The institutions that sign unbounded cyber vendor liability are usually the ones whose procurement won and whose insurance and capital teams were not in the room.

---

## 4. Warranties we should give—and those we must not

**Give:** material conformity to specification after acceptance; no intentional malware; right to license; control behaviours under the acceptance suite; support response times.

**Do not give:** uninterrupted operation; detection of all threats; “unhackable”; fitness for a particular regulatory outcome (the bank owns its regulatory conclusions); any warranty that triggers solely because the customer lost money in an incident without a proven control defect.

**Separate the tools counsel confuses in a hurry:**

- **SLA credits** cure downtime of *our* plane.
- **Warranty** cures spec non-conformity.
- **Indemnity** addresses defined third-party claims.
- **Insurance** sits under residual catastrophe—customer primary cyber; HYBA tech E&O and cyber with honest sublimits. HYBA is not the ransom payor.

---

## 5. Shared responsibility is the exhibit that prevents fairy tales

Put it behind the signature block.

HYBA owns correctness of specified gate, audit, and AEAD behaviour in the artefact we release, and patching of images we supply within SLA. The customer owns supported versions, key custody when keys are theirs, calling the SDK on sensitive paths, not disabling fail-closed controls, identity and email and endpoint hygiene, approving heal proposals by default, classifying their data, and what they tell *their* clients about our product.

Self-healing without a sovereign or customer gate is unsupervised change management. Defaults stay **propose, do not auto-apply** in production. If a client insists on auto-apply, that is a priced deviation and a liability shift—never a silent default.

---

## 6. Privacy, AI, and IP—three City sensitivities

**Privacy.** Split B2B relationship data from payload. Controller and processor labels follow actual processing. DIFC data protection, UK GDPR, and EU GDPR analysis is deploy-pattern-specific. A false “we never touch data” claim is worse than a narrow processor schedule.

**AI.** Six-form intelligence and EUCLID-class systems are **assistive and governed**. Contract for transparency of role (decision support vs hard gate), human authority on irreversible actions, and no warranty of omniscience. That is consistent with how model risk is treated inside banks: useful, bounded, owned.

**IP.** Absolute retention of algorithms, models, and topology in the MSA is non-negotiable. Licence is to use the deliverables, not to own the substrate. Escrow or source access for sovereigns is a commercial lever, not a default giveaway.

---

## 7. Scenes from the morning after

**The phishing email that never hit the sidecar.** Customer residual. Offer paid incident support if useful; do not open the cap.

**The library bug that allowed a documented deny path to allow.** Control defect. Fix, warranty remedies, forensic proof, capped direct loss if the schedule allows.

**The model that did not “see” a novel ransomware family.** Intelligence miss. No completeness warranty if the paper is clean.

**Bypass flag in production “just for the migration weekend.”** Customer breach of contract; our liability for what follows is suspended.

**Four-hour control-plane outage.** Credits. The FT may still be unkind; the contract should already have chosen credits as exclusive remedy for availability.

**A deck from last year that said zero breaches.** Entire agreement, non-reliance, sales discipline, and a quiet funeral for that sentence.

---

## 8. What the C-suite should take to risk committee

1. **We deliver controls as packages**—SDK, API, runtime, sovereign instance—not a mystical guarantee.  
2. **We warrant specification and testable behaviour**, not the customer’s incident-free life.  
3. **Liability follows failure class**, with a fee-linked cap and a forensic condition precedent.  
4. **Data plane and security plane stay on separate schedules**—different physics, different money, different failure modes.  
5. **Absolute marketing language is a balance-sheet risk**, not a growth hack.  
6. **HYBA paper holds** because the category is infrastructure-grade computation and control, not seats.

That is how one writes for a City reader of the *FT*: clear about ambition, colder about residual risk, and unwilling to confuse a security product with an insurance treaty.

---

## Next instruments for Legal

1. **AL HARAS Security Schedule v0.9** — specification, warranties, cap, exclusions, forensic protocol, shared responsibility.  
2. **Acceptance Test exhibit** — named harnesses from CI.  
3. **Forbidden representations list** for anyone client-facing.  
4. **Bank paper negotiation card** — standard pushes and counters above, under DIFC / English law.

---

**Andre Taylor-Morris**  

Founder & CEO, HYBA  

Software, Technology, IP, Privacy, AI & Cyber  

Formerly institutional counsel and advisory (including bank-side cyber contracting; market data; risk)  

DIFC, Dubai

*Intelligent Solutions.*