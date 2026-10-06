# HYBA Style Guide — Frontend & Product (McKinsey-Grade)

**Status:** Authoritative style reference for all HYBA frontend, product, and document work.  
**Posture:** Mirrors McKinsey executive style as institutional DNA.  
**Evidence class:** *Doctrine / brand law* — implement against this; do not treat aspirational UI as shipped until tokens and surfaces match.

---

<aside>

**Posture:** HYBA is the McKinsey of the world. Every product brought to market must look, feel, and perform like a McKinsey deliverable — UI, UX, information architecture, empty/error states, analytics surfaces, onboarding, and operational polish at board-grade institutional standard. No startup-product aesthetics.

</aside>

---

## 0. BLUF

| Rule | Mandate |
| --- | --- |
| Look | Oxford / McKinsey blues; gold only for prize numbers; sand/grey calm |
| Feel | Quiet authority — clear hierarchy, deliberate motion, board-readable density |
| Perform | Production reliability; in-product claims evidence-backed (Rule 7) |
| Type | Victor Serif for identity and executive display; system sans for dense UI |
| Ship bar | If it would embarrass a McKinsey client room, it does not ship |

**Repo anchors (this workspace):**

| Artifact | Path |
| --- | --- |
| This guide | `docs/HYBA_STYLE_GUIDE_FRONTEND_PRODUCT.md` |
| Live token target (CSS) | `docs/brand/hyba_tokens.css` |
| Interactive style system | `docs/brand/hyba_style_system.html` |
| Product frontend today | `frontend/src/index.css` (see § Gap — current vs law) |

---

## 1. Interactive Style System (Live Reference)

Live reference covering palette, typography, logo usage, components (tabs, accordion, slider, carousel), writing style, tables, presentation slides, and announcement patterns:

→ [`docs/brand/hyba_style_system.html`](brand/hyba_style_system.html)

---

## 2. Colour System

### 2.1 Primary — McKinsey / Oxford Blues

| Token | Name | Hex | Role |
| --- | --- | --- | --- |
| `--hyba-oxford` | Oxford Blue | `#002147` | Deepest institutional / academic authority |
| `--hyba-midnight` | Midnight Blue | `#001E3C` | Dark canvases, executive decks |
| `--hyba-logo-navy` | Logo Navy | `#001E46` | Wordmark / hex mark (from master logo) |
| `--hyba-deep` | Deep Blue | `#00426A` | Headers, primary surfaces |
| `--hyba-primary` | McKinsey Primary | `#0066B2` | Links, actions, secondary emphasis |
| `--hyba-bright` | Bright Blue | `#009FDA` | Highlights, data viz accents |
| `--hyba-light` | Light Blue | `#7FB8DD` | Secondary text on dark, charts |
| `--hyba-pale` | Pale Blue | `#C7E6F5` | Soft fills, table zebra, callout tints |

### 2.2 Accent — Veuve Clicquot

| Token | Name | Hex | Role |
| --- | --- | --- | --- |
| `--hyba-gold` | Veuve Gold | `#F2A900` | Prize / key numbers / premium accent |
| `--hyba-gold-dark` | Gold Dark | `#D99000` | Gold on light for contrast |
| `--hyba-gold-light` | Gold Light | `#FFD45F` | Soft gold fills |
| `--hyba-tagline-gold` | Tagline Gold | `#FFBE00` | *Intelligent Solutions.* (logo-matched) |
| `--hyba-orange` | Veuve Orange | `#E86C1E` | Spark / alerts / energy (sparingly) |
| `--hyba-orange-dark` | Orange Dark | `#C85A10` | Orange on light |
| `--hyba-orange-light` | Orange Light | `#FF9147` | Soft orange fills |

### 2.3 Neutrals — Luxurious Grey & Sand

| Token | Name | Hex | Role |
| --- | --- | --- | --- |
| `--hyba-charcoal` | Charcoal | `#1A1A1A` | Near-black body on light |
| `--hyba-slate` | Luxurious Grey | `#2D3748` | Secondary text, rules |
| `--hyba-slate-light` | Grey Mid | `#3D4A5C` | Borders on dark |
| `--hyba-grey` | Grey | `#718096` | Captions, meta |
| `--hyba-silver` | Silver | `#A0AEC0` | Disabled / hairlines |
| `--hyba-sand` | Sand | `#D4C5B9` | Warm neutral accent |
| `--hyba-sand-light` | Sand Light | `#E8DDD3` | Warm surfaces |
| `--hyba-cream` | Cream | `#F5F1ED` | Light canvas / cream wordmark on dark |
| `--hyba-white` | White | `#FFFFFF` | Primary light canvas |

### 2.4 Colour Law

1. **Blue is the institution** — default for structure, type, mark, navigation.
2. **Gold is the prize** — key numbers, milestones, premium moments, tagline.
3. **Orange is the spark** — rare: alerts, founder notes, energy beats — never wallpaper.
4. **Grey & sand** — luxury calm; body hierarchy and warm breathing room.
5. Never let gold/orange overwhelm blue.

---

## 3. Typography

### 3.1 Primary: Victor Serif

- **Family:** Victor Serif
- **Weights:** Light → Regular → Medium → Semibold → Bold → Black
- **Use:** all display, titles, wordmarks-adjacent headlines, executive body
- **HYBA wordmark optical class:** heavy / bold serif matching master logo authority
- **Company line (Data / Analytics / …):** lighter weight than HYBA, same family, tracked to match master ANALYTICS optical system

### 3.2 Type Hierarchy (Executive)

| Level | Treatment |
| --- | --- |
| Display / cover | Victor Serif Bold/Black, generous tracking |
| Section head | Victor Serif Semibold |
| Body | Victor Serif Regular (or pair sans when chosen) |
| Caption / meta | Smaller; grey (`--hyba-grey`) |
| Key number | Victor Serif; gold (`--hyba-gold`) when "prize" |

### 3.3 Dense product UI

- Tables, telemetry, forms, code: system / IBM Plex Sans + mono stack is acceptable.
- Display and executive chrome stay Victor Serif (or licensed equivalent until font files are vendored).

---

## 4. Logo System

- **Mark:** official hex only
- **Wordmark:** **HYBA** in navy (cream on dark)
- **Company line:** Data · Analytics · Intelligence · Finance — same optical class as master Analytics line
- **Tagline:** *Intelligent Solutions.* — house-level, gold italic
- **First to market:** HYBA Data

### 4.1 Documentation Branding (Mandatory)

- Every document, deck, page must carry the proper HYBA logo lockup
- **No generic icons** as brand marks (no emoji stand-ins)
- **No wrong company line** — Data lockup only when content is Data-only
- Place logo on cover / header of every formal deliverable

---

## 5. McKinsey Form (Required on Every Artifact)

1. **BLUF / answer first** — recommendation or insight in the first line
2. **Pyramid** — governing thought → supporting arguments → evidence
3. **One idea per slide / section** — no cluttered multi-thesis pages
4. **Exhibit discipline** — charts and tables titled with the *insight*, not the data category
5. **Action titles** — headlines state the conclusion
6. **Sparse colour** — navy structure; gold only for prize numbers; orange rare
7. **Victor Serif** for identity and executive type
8. **Evidence trail** — claims separable into *implemented / validated / planned / aspirational*

---

## 6. McKinsey Form (Required on Every Product)

1. **Look** — institutional visual system (Oxford/McKinsey blues, gold sparingly, sand/grey calm); no startup chrome
2. **Feel** — quiet authority in interaction: clear hierarchy, deliberate motion, zero clutter, board-readable density
3. **Perform** — production reliability, measurable outcomes, evidence-backed claims in-product
4. **IA** — answer-first surfaces; insight titles on charts; executive summary paths before deep detail
5. **States** — empty, loading, error, and permission states designed to the same standard as happy path
6. **Onboarding** — structured like a briefing, not a consumer app tour
7. **Ship bar** — if it would embarrass a McKinsey client room, it does not ship

---

## 7. Frontend Application

### 7.1 Design Tokens (CSS Custom Properties)

Canonical copy also lives in `docs/brand/hyba_tokens.css`:

```css
:root {
  /* McKinsey Blues */
  --hyba-oxford: #002147;
  --hyba-midnight: #001E3C;
  --hyba-logo-navy: #001E46;
  --hyba-deep: #00426A;
  --hyba-primary: #0066B2;
  --hyba-bright: #009FDA;
  --hyba-light: #7FB8DD;
  --hyba-pale: #C7E6F5;

  /* Veuve Clicquot */
  --hyba-gold: #F2A900;
  --hyba-gold-dark: #D99000;
  --hyba-gold-light: #FFD45F;
  --hyba-tagline-gold: #FFBE00;
  --hyba-orange: #E86C1E;
  --hyba-orange-dark: #C85A10;
  --hyba-orange-light: #FF9147;

  /* Neutrals */
  --hyba-charcoal: #1A1A1A;
  --hyba-slate: #2D3748;
  --hyba-slate-light: #3D4A5C;
  --hyba-grey: #718096;
  --hyba-silver: #A0AEC0;
  --hyba-sand: #D4C5B9;
  --hyba-sand-light: #E8DDD3;
  --hyba-cream: #F5F1ED;
  --hyba-white: #FFFFFF;

  /* Type */
  --hyba-font-display: "Victor Serif", "Fraunces", Georgia, serif;
  --hyba-font-ui: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif;
  --hyba-font-mono: "JetBrains Mono", "IBM Plex Mono", monospace;
}
```

### 7.2 Component Standards

| Element | Token / rule |
| --- | --- |
| Backgrounds | `--hyba-midnight` dark canvases; `--hyba-cream` light |
| Surfaces | `--hyba-deep` elevated panels; `--hyba-slate` cards on dark |
| Primary actions | `--hyba-primary` buttons, white text |
| Key metrics | `--hyba-gold` prize numbers only — never decorative chrome |
| Alerts | `--hyba-orange` sparingly; never default accent |
| Typography | Victor Serif headings; system sans dense UI/tables |
| Spacing | Generous, institutional — never cramped |
| Motion | Deliberate, slow, quiet — no bouncy or playful animation |
| Charts | Insight titles (exhibit discipline); navy/gold palette |

---

## 8. Gap — current frontend vs this law (honest)

**Implemented today** (`frontend/src/index.css`): PYTHIA Ops executive-fintech palette (`--pythia-*`), Fraunces + IBM Plex, blurple `#635bff` as “gold” stand-in.

| Law (this guide) | Current product CSS | Class |
| --- | --- | --- |
| `--hyba-oxford` / McKinsey blue stack | `--pythia-text` ink navy + void paper | **Partial** — institutional calm, wrong token names & accents |
| `--hyba-gold` Veuve `#F2A900` | `--pythia-gold: #635bff` (blurple) | **Non-compliant** — prize colour is not gold |
| Victor Serif | Fraunces | **Planned substitute** until Victor is licensed/vendored |
| Full HYBA lockup on every surface | Hex clip utility only (`.clip-hex`) | **Partial** |

**Rule 7:** Do not claim the product UI is “on HYBA McKinsey style” until `frontend` consumes `--hyba-*` (or an explicit mapped alias layer) and prize metrics render Veuve gold.

**Recommended migration (planned, not done here):**

1. Import `docs/brand/hyba_tokens.css` into the frontend entry.
2. Alias `--pythia-*` → `--hyba-*` during transition *or* replace usages in one pass.
3. Remap prize metrics from blurple to `--hyba-gold`.
4. Keep telemetry mono stack; swap display serif when Victor files are available.

---

## 9. Canonical References

| Reference | Notes |
| --- | --- |
| Style System (Authoritative) | This document + `docs/brand/hyba_style_system.html` |
| Brand tokens | `docs/brand/hyba_tokens.css` |
| Brand & Logo Assets | Master logo lockup (official hex + wordmark) — vendor under `docs/brand/assets/` when available |
| Brand Architecture & GTM | Product-line lockups (Data first) |
| Board resolution (external) | `docs/ceo_manual/BOARD_RESOLUTION_EXECUTIVE_STYLE_GUIDE_AND_BRAND_PALETTE.md` — *not present in this clone; link when restored* |
| Claims discipline | Repo Rule 7 / evidence trail — implemented · validated · planned · aspirational |

---

## 10. Writing & exhibit checklist (ship gate)

Before any frontend, deck, or doc ships:

- [ ] BLUF in the first screenful
- [ ] One governing idea per view/section
- [ ] Chart/table title states the insight
- [ ] Prize numbers in gold; structure in blue
- [ ] Orange only if alert/energy is the point
- [ ] Empty / loading / error / permission states designed
- [ ] No emoji-as-logo; correct company line
- [ ] Claims tagged implemented / validated / planned / aspirational
- [ ] Would survive a McKinsey client room

---

*This page consolidates the authoritative style system for frontend and product work in this repository. Interactive specimen: `docs/brand/hyba_style_system.html`. Tokens: `docs/brand/hyba_tokens.css`.*
