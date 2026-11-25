# Stadium Intelligence 2.0 — Design System Specification

**Design Identity:** Stadium Intelligence 2.0 — Football Performance Workspace  
**Aesthetic Principles:** Precision, Tactical Football Intelligence, Sports Analytics Clarity, Depth & Contrast.

---

## 1. Color Palette Tokens

### Surface & Canvas Architecture
```css
--canvas: #070B12;                /* Deep pitch carbon background */
--surface-primary: #0D1522;       /* Primary panel surface */
--surface-elevated: #142032;      /* Elevated card & inspector surface */
--surface-card: #101B2B;          /* Football player card background */
--surface-hover: #1A293E;         /* Interactive hover layer */
--surface-pitch: #091F19;         /* Tactical pitch turf green */
--surface-pitch-accent: #0E2922;  /* Tactical pitch alternating stripes */
```

### Borders & Dividing Lines
```css
--border-subtle: #1C2B3E;         /* Standard card & container borders */
--border-strong: #2D435E;         /* Active / selected container borders */
--border-focus: #52C9E8;          /* WCAG 2.2 compliant focus ring (3px) */
--border-pitch: #215143;          /* Pitch perimeter markings */
--pitch-line: rgba(184, 245, 122, 0.28); /* Tactical pitch inner lines */
```

### Typography & Foregrounds
```css
--text-primary: #F4F7FB;          /* Highest contrast headers and primary data */
--text-secondary: #A0B5C9;        /* Descriptive body text & labels */
--text-tertiary: #7189A0;         /* Metadata, hints, footnotes */
--text-muted: #53697E;            /* Inactive or placeholder state */
```

### Functional & Semantic Accents
```css
--accent-lime: #B8F57A;           /* Primary football brand action & fit score */
--accent-cyan: #52C9E8;           /* Analytical intelligence & capability data */
--accent-gold: #E8B66D;           /* Elite ratings (88+ OVR) & special editions */
--accent-violet: #B1A5FF;         /* Research release & experimental data */
--positive: #5CE592;              /* Advantageous stat delta (+1 or higher) */
--negative: #F46571;              /* Disadvantageous stat delta (-1 or lower) */
--neutral: #8FA4B9;               /* Unchanged or equal stat delta */
```

### Football Rating Tiers
```css
--rating-elite: #E8B66D;          /* 88 - 99: Gold / Masterclass */
--rating-high: #B8F57A;           /* 82 - 87: Lime / Top Flight */
--rating-mid: #52C9E8;            /* 75 - 81: Cyan / Standard */
--rating-entry: #8FA4B9;          /* < 75: Silver / Developing */
```

---

## 2. Typography Hierarchy

| Style Role | Font Family | Size Range | Weight | Letter Spacing | Use Case |
|---|---|---|---|---|---|
| **Display Heading** | Space Grotesk | 28px – 38px | 700 | -0.03em | Primary workspace page titles |
| **Section Heading** | Space Grotesk | 18px – 22px | 650 | -0.02em | Panel titles, Inspector headers |
| **Card Title** | Space Grotesk | 15px – 17px | 600 | -0.01em | Player card name, modal title |
| **Interface Body** | Inter | 14px – 15px | 400 / 500 | Normal | Form inputs, descriptions, body |
| **Label / Eyebrow**| Inter | 11px – 12px | 600 | +0.03em | Field labels, badges, status pills |
| **Data & Metrics** | IBM Plex Mono | 12px – 15px | 600 / 700 | -0.01em | OVR, Suitability Score, Facet stats |

---

## 3. Elevation & Depth System

- **Tier 0 (Canvas):** Flat base `#070B12`.
- **Tier 1 (Surface Primary):** `#0D1522` with `1px solid var(--border-subtle)` and `box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3)`.
- **Tier 2 (Surface Elevated):** `#142032` with `box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45)`.
- **Tier 3 (Active / Floating):** `#1A293E` with `box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6)` and `border-color: var(--accent-lime)`.

---

## 4. Football-First Design Patterns

1. **Football Card Framing:** Distinctive sports card proportion with top badge (OVR + Position), stylized player silhouette avatar, name plate, 6-facet attribute pills (PAC, SHO, PAS, DRI, DEF, PHY), and PlayStyle indicator tags.
2. **Tactical Pitch:** Interactive pitch rendering true-to-scale football field markings (penalty box, six-yard box, center circle, penalty spot) with 11 distinct slot nodes, goalkeeper distinction, and keyboard navigation.
3. **Contextual Inspector:** Scouting drawer/rail that breaks down engine suitability into capability dimensions, PlayStyle contributions, and tactical suitability deltas.
4. **Suitability Indicators:** Color-coded circular score dials and comparative horizontal bars that never misrepresent model suitability as match win probabilities.
