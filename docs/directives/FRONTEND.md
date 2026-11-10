# Frontend product design and implementation

**Current design authority:** Follow the [HYBA product style guide](PRODUCT_STYLE_GUIDE.md). It supersedes earlier visual and product-structure recommendations in this file or elsewhere when they conflict.

## Product identity

Chronus is HYBA Data’s product/platform, not a separate company. AL HARAS is HYBA Security. Keep product navigation, copy, and client-facing materials within the two market-facing companies: HYBA Data and HYBA Security.

## Frontend principles

- Build a coherent product experience for HYBA Data or HYBA Security; do not introduce additional market-facing company or product categories without owner direction.
- Translate complex capabilities into clear, complete enterprise workflows. Put the user’s task and decision first; expose technical detail progressively.
- Use a consistent, accessible design system for typography, spacing, color, charts, navigation, and interaction states.
- Use only real, sourced data for live metrics. Label sample, synthetic, illustrative, stale, and unverified information explicitly.
- Keep visible status tied to actual backend state. Do not infer qualification or security status from an application loading successfully.
- Every control must have a defined action, permission check, resulting state, and auditable outcome where appropriate.
- Design loading, empty, error, degraded, offline, and permission-denied states alongside the success path.
- Do not imply that quantum is a standalone market or product, or that Bitcoin mining is a customer offering; see the product style guide.

## Implementation and review

Before shipping a screen, verify its data source and API contract, keyboard and screen-reader behavior, responsive layout, color contrast, error handling, and action permissions. Do not use decorative architecture views as live topology or present demo values as operational telemetry. Claims about performance, hardware, security, and qualification must remain within the evidence documented in the [claim audit](../claim-audit.md) and [release decision](../../RELEASE_DECISION_MCKINSEY_TECH.md).
