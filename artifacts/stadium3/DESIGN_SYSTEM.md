# STADIUM 3.0 — DESIGN SYSTEM SPECIFICATION
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Status: Production Active | Target: World-Class Football Intelligence*

---

## 1. Design Philosophy: The Digital Match Stadium

Stadium 3.0 is designed as a high-density, football-native operating environment. Rather than looking like a generic SaaS analytics dashboard or a static card database, the interface fuses three core visual disciplines:

1. **Broadcast Football Analytics:** Inspired by elite tactical software used by Premier League/Champions League scouting departments and broadcast analysis studios (Sky Sports Monday Night Football, StatsBomb, Wyscout).
2. **Ultimate Team Card Artifacts:** High-contrast, tactile physical card representations with authentic ratings, hexagon attribute distributions, playstyles, and card tier treatments (Gold, Special/In-Form, Silver, Bronze).
3. **Immersive Night Stadium HUD:** Deep stadium night darkness (`#060A10`), floodlight atmospheric luminescence, authentic pitch markings (corner arcs, penalty boxes, center circles), and crisp tactical neon accents (`#B8F57A` pitch lime, `#52C9E8` tactical cyan, `#E8B66D` elite gold).

---

## 2. Color Architecture & Design Tokens

### 2.1 Surfaces & Canvas (Dark OLED & Floodlight Stadium)
```css
--canvas: #060A10;                /* Pure stadium night pitch perimeter */
--surface-primary: #0B1320;       /* Base workspace background */
--surface-elevated: #111D2E;      /* Secondary panels & elevated rail containers */
--surface-card: #152236;          /* Interactive card bodies & table rows */
--surface-hover: #1C2D45;         /* Active state & hover highlights */
--surface-inset: #080E17;         /* Form inputs & sunken metrics */
--surface-pitch: #071914;         /* Authentic grass pitch dark base */
--surface-pitch-accent: #0C2820;  /* Pitch mowing stripes / turf variation */
```

### 2.2 Borders & Structural Grids
```css
--border-subtle: #192738;         /* Minimal division lines */
--border-strong: #263A52;         /* Standard card & container outlines */
--border-active: #52C9E8;         /* Focused / active component borders */
--border-pitch: #1E4B3E;          /* Pitch perimeter boundary line */
--pitch-line: rgba(184, 245, 122, 0.35); /* Penalty boxes, center spot, corner arcs */
```

### 2.3 Semantic Accents & Football Tactical Palette
```css
--accent-lime: #B8F57A;           /* Primary tactical action / Pitch lime / Fit score */
--accent-cyan: #52C9E8;           /* Intelligence / Analytics / Tactical role / Focus */
--accent-gold: #E8B66D;           /* Elite tier / Top rated 85+ / MOTM */
--accent-violet: #B1A5FF;         /* Research preview / FC27 exploratory data */
--accent-amber: #F5A623;          /* Squad upgrade candidate / Warning */
--positive: #5CE592;              /* Chemistry boost / Stat surplus */
--negative: #F46571;              /* Out of position / Stat deficit / Danger */
--on-accent: #080D14;             /* High contrast text on neon lime/cyan */
```

### 2.4 Rating Tiers
```css
--rating-elite: #E8B66D;          /* 85+ OVR */
--rating-high: #B8F57A;           /* 78 - 84 OVR */
--rating-mid: #52C9E8;            /* 70 - 77 OVR */
--rating-low: #8FA4B9;            /* < 70 OVR */
```

### 2.5 Atmospheric Glows & Shadows
```css
--shadow-sm: 0 2px 6px rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
--shadow-lg: 0 8px 30px rgba(0, 0, 0, 0.55);
--shadow-glow-lime: 0 0 20px rgba(184, 245, 122, 0.28);
--shadow-glow-cyan: 0 0 20px rgba(82, 201, 232, 0.28);
```

---

## 3. Typography Hierarchy

| Style | Font Family | Weight | Size Range | Letter Spacing | Use Cases |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display / Hero** | `Space Grotesk` | 700 / 800 | 2.0rem – 3.2rem | `-0.035em` | Hero titles, Command Center headlines, OVR badges |
| **Section Heading** | `Space Grotesk` | 600 / 700 | 1.15rem – 1.6rem | `-0.02em` | Module titles, Pitch headers, Radar titles |
| **Subhead / Role** | `Inter` | 600 | 0.88rem – 1.0rem | `0.00em` | Tactical role tags, player position, stat categories |
| **Body / Readout** | `Inter` | 400 / 500 | 0.85rem – 0.95rem | `0.00em` | Analytical explanations, card descriptions |
| **Data / Numbers** | `IBM Plex Mono` | 600 / 700 | 0.75rem – 1.1rem | `+0.02em` | Attribute ratings (PAC/SHO/PAS), Chemistry (33/33), Price |

---

## 4. UI Components & Interaction System

### 4.1 Button System (`.btn`)
- `.btn.primary`: Floodlight neon lime background, dark obsidian text, energetic glow hover, active spring depression.
- `.btn.secondary`: Elevated charcoal surface, cyan border hover, white text.
- `.btn.outline`: 1.5px subtle border, lime highlight on hover.
- `.btn.ghost`: Clean borderless state, elevated hover wash.
- `.btn.danger`: Subtle red translucent tint with crimson hover for squad clearing and card removal.
- Sizes: `.btn.sm` (34px compact), standard (42px touch-friendly), `.btn.lg` (48px hero).

### 4.2 Tactical Pitch Architecture (`.stadium-pitch`)
- **Turf Geometry:** Scaled proportional 68m × 105m pitch ratio rendered in pure responsive CSS/SVG.
- **Markings:** High-precision touchlines, penalty areas, 18-yard box, 6-yard box, center circle, penalty spot, and **corner arcs** (`.pitch-corner-tl`, `.pitch-corner-tr`, `.pitch-corner-bl`, `.pitch-corner-br`).
- **Atmospheric Floodlights:** Ambient multi-radial lighting (`.stadium-ambient-lights`) casting top-down illumination onto the green pitch mat.
- **Card Nodes:** Formation coordinate positioning for 11 pitch slots with dynamic state badges (filled, unfilled, candidate replacement, chemistry boost indicator).

### 4.3 FIFA/UT Card Visual Tiers (`.football-card`)
- `.card-tier-gold`: Rich dual-tone gold gradient (`#1B170E` to `#2A2210`), gold border (`#E8B66D`), elite crest styling.
- `.card-tier-special`: Holographic prismatic shimmer (`@keyframes holo-shimmer`), iridescent border, violet-cyan gradient.
- `.card-tier-silver`: Metallic brushed aluminum sheen (`#161C24` to `#232B36`).
- `.card-tier-bronze`: Rich burnished bronze finish (`#18120D` to `#261B13`).
- **Attribute Grid:** Compact 6-stat readouts (PAC, SHO, PAS, DRI, DEF, PHY) with color-coded tier ratings.

### 4.4 Glassmorphism HUD Panels (`.glass-panel`, `.glass-hud`)
- High-efficiency `backdrop-filter: blur(16px)` with layered semi-transparent obsidian surfaces (`rgba(11, 19, 32, 0.75)`).
- Subtle 1px translucent borders (`rgba(255, 255, 255, 0.08)`) simulating professional broadcast glass monitors.

---

## 5. Motion & Physics Specifications

- **Micro-Interactions:** `cubic-bezier(0.16, 1, 0.3, 1)` easing curve for tactile snappy response.
- **Card Hover:** Subtle `translateY(-3px)` lift with accelerated shadow expansion (`--shadow-md` to `--shadow-lg`).
- **Tactical Transitions:** 180ms ease-out on filter changes and tab selections.
- **Reduced Motion:** Full `@media (prefers-reduced-motion: reduce)` compliance automatically disabling holographic shimmers and transforms.

---

## 6. Accessibility & Honest Data Constraints

- **WCAG 2.2 AA Contrast Compliance:** All readable text exceeds 4.5:1; key tactical labels achieve 7:1+ on OLED black.
- **Keyboard Navigation:** Universal `:focus-visible` ring in vibrant tactical cyan with 3px offset.
- **Strict Data Integrity:** Zero simulated stats. `NO_DATA` / `UNKNOWN` rendered explicitly in neutral steel gray (`--text-muted`).
- **Version Isolation:** Canonical FC26 vs Research FC27 strictly segregated via badge hierarchy and warning ribbons.
