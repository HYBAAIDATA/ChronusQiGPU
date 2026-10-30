# HYBA Data MCP Server (OVID Data Edition)

<aside>
🔌

**HYBA Data MCP Server (OVID Data Edition)**  

**Company:** HYBA Data  

**Board:** Andre Taylor-Morris  

**Purpose:** Exposing the PHI-Space Substrate directly to AI Agents via the Model Context Protocol (MCP).

</aside>

---

## 1. The Mode of Delivery

We are not just delivering an SDK for human developers to write classical code against. We are delivering an **MCP Server** so that enterprise AI agents (Devin, Cursor, Copilot) can command the PHI-Space substrate directly using natural language.

We have successfully cloned the OVID server architecture from `HYBA_UNIFIED_BACKEND` and stripped away the 170+ non-Data platform tools (e.g., COBBLA, Millennium Maths). We rebranded it and packaged it exclusively for **HYBA Data**.

## 2. The MCP Capabilities

The HYBA Data MCP Server exposes three primary tool commands to AI IDEs:

- **`phi_fold_data`**: Allows an AI agent to ingest massive local datasets into the hyperbolic manifold. The agent writes `client.call("phi_fold_data", {path: "..."})`, and the data is compressed by $6.85\times$.
- **`phi_geodesic_search`**: Allows the agent to query the folded manifold directly in $O(\log N)$ time without unfolding it into classical arrays.
- **`generate_ciaas_invoice`**: Directly hooks into the PCEL (Compliance & Evidence Layer). An AI agent can calculate the exact DRAM footprint saved by the $\phi$-compression and immediately emit the cryptographic seal for the 25% HYBA Success Fee.

## 3. Enterprise Value

When a hyperscaler or enterprise CTO integrates the HYBA Data MCP, they do not need to retrain their engineering teams on $\mathbb{Z}[\phi]$ ring arithmetic. Their AI agents already understand the protocol. They simply prompt their IDE: *"Optimize this tick data pipeline using the HYBA Data MCP."* The agent will automatically call the `phi_fold_data` tools, bypassing classical memory bottlenecks instantly.