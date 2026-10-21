<b>Locked identity:</b> enterprise virtual quantum computation and exact, capability-bounded algebra on classical infrastructure. Not a physical quantum computer and not a mining engine by definition.

<b>Status:</b> product/authority baseline documented; current runtime qualification incomplete. Existing implementation findings are commit-scoped, not a fresh execution or release approval.

## Authority and dependencies

TURING owns backend capability admission, supported program semantics, representation selection, measurement interfaces and run witnesses. Kellogg remains the tensor mathematics dependency; Chronus owns eligible device execution. A QPU adapter refuses unless a real provider is registered/configured. A wide Clifford register is not an unrestricted universal amplitude vector.

## Contract and API inventory

| Surface | Documented contract | Qualification condition |
| --- | --- | --- |
| Backend registry / capability envelopes | Admit only programs supported by the selected backend and resource budget; refuse out-of-domain operations rather than truncate or approximate silently | Pin exact package exports and capability matrix |
| Exact Clifford tableau | Supported Clifford-state evolution and bounded queries | Re-run phase, measurement, marginal and continuation parity |
| Exact Clifford+T algebra | Exact field Q(√2)+i·Q(√2) within declared resource limits | Do not extrapolate width from the tableau backend |
| Marginals / sampling | Explicit readout, shots, seed and limits; probability/count consistency | Caller readout order versus sorted/deduplicated implementation remains unresolved |
| QPU adapter | Explicit provider requirement and honest execution identity | No configured provider means refusal, not simulated hardware success |
| Certificates / claims | Backend, representation and actual evidence scope | <code>tableau_bits=2*n</code> must not be sold as actual stored bit count |

Documented operator entry point: <code>turing-vqc</code>; documented caller contract: <code>docs/TURING_VQC_CALLER_CONTRACT.md</code>. These references do not prove a network API or installed package on a customer system. No new HTTP routes are invented by this record.

## Non-mining acceptance requirement

Execute Bell/GHZ, deterministic and random bounded circuits against an independent reference; verify measurement continuations, readout order, seed replay, count conservation and refusal beyond supported domain. Qualify entropy and end-to-end QEC separately. Tests using stand-ins cannot qualify real adapter bindings.

## Optional mining boundary

Mining-specific hash/search/swarm code must remain an adapter or separately scoped module. TURING does not own SHA-256d target correctness, pool acceptance, wallets or revenue accounting. Quantum-inspired algebra does not confer an unmeasured search advantage.

## Customer and publication schedule

Deliver only the named backend classes, resource limits and interfaces qualified for the supplied version. No universal-width, physical-QPU, QEC-pipeline or mining-profit warranty. Price, license scope, support, SLA and data-processing terms remain to be attached to an approved order form; this technical lock is not a signed contract.

## Source traceability

- <mention url="https://app.notion.com/p/ef634a9a2941468abd2da3a3400edb8d">TURING VQC — Product Boundary Elevation (v1.2)</mention>
- <mention url="https://app.notion.com/p/3f113476fb44496e99a2fcbb37546ccb">HYBA — Enterprise Product Lock Register</mention>