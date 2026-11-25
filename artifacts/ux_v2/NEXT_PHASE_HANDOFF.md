# EA FC Intelligence — Next Phase Engineering Handoff

## 1. System Architecture & File Organization

The Stadium 2.0 design and UI/UX transformation is completely encapsulated within standard React + CSS modules without introducing external runtime baggage.

### Key Components Catalog
```
PROJECT/EA_FC_INTELLIGENCE-main/frontend/src/
├── components/
│   ├── FootballCard.tsx          # High-density football player scouting tile
│   ├── PlayerIdentity.tsx        # Silhouette & monogram identity badge
│   ├── TacticalPreview.tsx       # Live formation miniature pitch preview
│   ├── Visualizations.tsx        # SuitabilityScore, AttributeBar, TacticalDeltaMatrix, TacticalRadar, EvidenceBadge
│   ├── StadiumPitch.tsx          # Full-size tactical pitch renderer
│   ├── Nav.tsx                   # Authoritative global sidebar & mobile header
│   └── common.tsx                # Ovr, Pos, Badges, Field, Modal, Loading, Empty
├── pages/
│   ├── Search.tsx                # Priority 1: Discover scouting workspace
│   ├── CardSquadLab.tsx          # Priority 3: Squad Lab pitch cockpit
│   ├── Compare.tsx               # Compare Studio with radar & delta matrix
│   ├── PerformanceEvidenceLab.tsx# Empirical gameplay research evidence
│   ├── Dashboard.tsx             # Workspace hero & quick access
│   ├── PlayerPage.tsx            # Canonical player profile
│   ├── CardPage.tsx              # UT card version profile
│   └── Squads.tsx / SquadDetail  # Squad management & builder
├── intelligence/
│   ├── Intelligence.tsx          # Priority 2: 3-step decision flow & inspector
│   ├── TacticalPreview.tsx       # Embedded slot visualizer
│   └── Card.tsx                  # Recommendation ladder item
└── stadium.css                   # Stadium 2.0 token design system & styles
```

---

## 2. Reusable Component APIs

### A. `<FootballCard />`
```tsx
import { FootballCard } from '../components/FootballCard'

<FootballCard
  id="p-101"
  name="Lamine Yamal"
  overall={81}
  position="RW"
  secondaryPositions={["RM"]}
  club="FC Barcelona"
  nation="Spain"
  league="La Liga"
  facades={{ pace: 85, shooting: 78, passing: 82, dribbling: 88, defending: 36, physicality: 54 }}
  playstyles={[{ playstyle_name: "Quick Step", tier: "plus" }, { playstyle_name: "Finesse Shot", tier: "base" }]}
  isCompared={false}
  onCompareToggle={(id, checked) => handleCompare(id, checked)}
/>
```

### B. `<TacticalPreview />`
```tsx
import { TacticalPreview } from '../components/TacticalPreview'

<TacticalPreview
  formation="4-3-3"
  selectedSlot="RW"
  onSelectSlot={(slot) => setSelectedSlot(slot)}
/>
```

### C. `<AttributeBar />`
```tsx
import { AttributeBar } from '../components/Visualizations'

<AttributeBar
  label="sprint_speed"
  value={89}
  max={99}
  delta={+4}
  showValue={true}
/>
```

### D. `<TacticalRadar />`
```tsx
import { TacticalRadar } from '../components/Visualizations'

<TacticalRadar
  title="Candidate Facet Comparison"
  nameA="Base Candidate"
  facadesA={{ pace: 84, shooting: 82, passing: 80, dribbling: 86, defending: 40, physicality: 68 }}
  nameB="Target Upgrade"
  facadesB={{ pace: 90, shooting: 85, passing: 84, dribbling: 91, defending: 42, physicality: 70 }}
/>
```

---

## 3. Design System CSS Tokens (`stadium.css`)

All design tokens are defined on `:root` and adapt cleanly to dark mode:
```css
:root {
  /* Surfaces */
  --canvas: #080D16;
  --surface-primary: #111B29;
  --surface-elevated: #162234;
  --surface-card: #192639;
  --surface-hover: #223249;

  /* Typography */
  --font-display: "Space Grotesk", sans-serif;
  --font-sans: "Inter", sans-serif;
  --font-mono: "IBM Plex Mono", monospace;

  /* Accents */
  --accent-lime: #B8F57A;
  --accent-cyan: #52C9E8;
  --accent-gold: #E8B66D;
  --accent-violet: #B1A5FF;

  /* Pitch Turf */
  --pitch-turf-dark: #071713;
  --pitch-turf-light: #0D2B23;
  --pitch-line: rgba(184, 245, 122, 0.4);
}
```

---

## 4. Verification & Testing Commands

To run the verification suite and verify production builds at any time:
```bash
# 1. Run Vitest Unit & Regression Tests
npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run test

# 2. Run TypeScript Verification & Production Vite Build
npm --prefix PROJECT/EA_FC_INTELLIGENCE-main/frontend run build
```

---

## 5. Recommended Future Enhancements
1. **Framer Motion Micro-Interactions:** Enhance slot selection and card hover with lightweight spring transitions.
2. **Offline Shortlist Sync:** Store user shortlists and tactical comparisons in browser IndexedDB for seamless offline scouting.
3. **PWA Mobile Manifest:** Package the mobile layout as an installable Progressive Web App for sideline pitch analysis.
