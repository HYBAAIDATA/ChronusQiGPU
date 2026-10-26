# Portal design and implementation specification

## Extend the repository, do not assume Next.js

The inspected `frontend/package.json` and AGENTS.md describe a React/TypeScript + Vite PYTHIA operator application, built to `dist/public` and served by Python. No existing dedicated TURING docs framework was identified in that frontend. Do not inject an unverified Next.js service or change operator authentication to host documentation.

This increment supplies a standalone **review preview**, not a second production application. A pinned Markdown renderer, shared manifest and static shell demonstrate the reading experience. A future React documentation route can consume the same manifest/content after deployment and authorisation decisions; alternatively mount the approved static public output separately.

## Information architecture

Four views share the same source: product/enterprise, developer, mathematics/research, architecture/assurance. Existing package docs, generated references, ADRs and evidence stay where they are. The internal source map links them. Public content describes approved-to-review semantics without exporting restricted source/runbooks.

## Reading shell

- Brand: TURING / COMPUTATIONAL INTELLIGENCE; editorial overview, compact technical pages.
- Desktop: persistent left navigation, 680–760px central column, contextual heading navigation.
- Mobile: keyboard-operable navigation disclosure, single-column reading, scrollable code/tables only.
- Colour: white/soft neutral canvas, blue links; semantic statuses always include text. Respect system dark mode.
- Type: system sans, disciplined heading scale, readable 16px body; monospace identifiers.
- Search: title/body/API/error/concept keyword search across the selected audience output; no restricted index entries. Current preview searches approved-for-preview text and symbol keywords; deep generated-reference indexing remains a future build integration, not claimed implemented.
- Continuity: section breadcrumbs, active page, previous/next, heading links and source/defect route appropriate to audience.
- Code: fenced blocks, copy control and clear prerequisites. Preview code remains unhighlighted; production highlighting is a remaining acceptance item. Do not add language tabs with no genuine supported examples.
- Mathematics: production renderer must support accessible MathML, defined symbols, anchors and referenced equation numbers. The preview uses textual equations deliberately; full rendering is not claimed complete.

## Access and content model

The manifest supplies immutable page IDs/slugs, audience, version, ownership and review information. Reuse existing generated reference rather than duplicate typed signatures. Add source-bound references to API pages on the approved internal/customer surface only after disclosure review. Planned/unavailable and experimental/deprecated labels must be distinguishable from stable; a draft page is not a stable capability.

## Acceptance tests before deployment

Target WCAG 2.2 AA; do not claim certification. Check keyboard/focus order, skip link, search status/empty results, navigation at 390px and desktop, contrast, 200% zoom/reflow, screen-reader equations, labelled diagrams and reduced motion. Automated and screenshot checks supplement human review, not replace it.

Verify hosting base paths, CSP, route isolation, no internal assets/maps/search entries in public output, no secret-bearing examples and no stale version links. Decide content origin, authenticated routing, supported version archive, responsible owners and public contact before production integration.
