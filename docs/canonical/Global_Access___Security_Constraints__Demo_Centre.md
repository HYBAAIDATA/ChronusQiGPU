# Global Access & Security Constraints (Demo Centre)

# Global Access & Security Constraints (Demo Centre)

## BLUF

HYBA Data infrastructure is heavily restricted. The demonstration environments are fundamentally uncoupled from consumer SaaS architecture, utilizing strict verification pipelines to prevent intellectual property exposure, anonymous surveillance, or sanctions violations.

## 1. Authentication Doctrine

We have deprecated generic SSO (Google/GitHub) for public access. 

- **Access Control:** Visitors to the HYBA website must request a demonstration. Sales operators provision an explicit, securely generated token and email it to the prospect.
- **The Flow:** The client enters via the `[ Authenticate ]` gateway using their provided secure email and access token.
- **Execution Modes:** Clients can either proceed via a **Guided Walkthrough** with a HYBA engineer or enter **Solo Execution** mode if granted extended clearance.

## 2. Geo-Fencing & Network Compliance (World Order Ban)

The backend middleware (`security_middleware.py`) actively enforces international trade laws and secures the Sovereign Substrate from hostile technical probing.

- **Geo-IP Blocking:** Connections originating from **Russia (RU), China (CN), North Korea (KP), Iran (IR), and Syria (SY)** are rejected at the network edge with an HTTP 451 (Unavailable For Legal Reasons).
- **VPN & Anonymous Proxy Ban:** The system queries commercial threat intelligence feeds (e.g., Cloudflare WARP signatures, known Tor exit nodes, data center IP ranges). If an IP is masked, the UI triggers a critical terminal error: `CRITICAL: ANONYMOUS ROUTING DETECTED`, and blocks the authentication attempt entirely.

## 3. Real-World Datasets & Reproducible Benchmarks

Demos do not rely on simulated integers. We deploy empirical, reproducible datasets to prove the exact mathematical claims:

- **PULVINI:** Tested against 14-qubit structural matrices and protein sequence datasets, proving the 85.6% ($\phi^4$) compression ratio deterministically.
- **HERMES & VQC:** Demos ingest these arrays into the `phi_quantize` kernel, establishing the 7x scaling factor visually in the Workstation.

## 4. Visual Evidence (Video Integration)

We have developed high-fidelity WebM/MP4 visual captures within the application (`QuantumVideoShowcase.tsx`) to illustrate the physics.

- **The Visuals:** Users watch the continuous coordinate topology in action—real 14-qubit matrix state reductions collapsing into their $\phi^4$ resonant bounds.
- **The Design Language:** Framed in a deeply minimalist, Thirst/Pentagram/McKinsey aesthetic. Deep obsidian (`#18181b`), pulsing terminal text (`#10b981`), and strict `font-mono` metrics overlay the video player, ensuring the presentation feels like an institutional-grade physics tool, not a startup promo.