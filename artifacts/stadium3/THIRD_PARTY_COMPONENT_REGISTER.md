# STADIUM 3.0 — THIRD-PARTY COMPONENT & PATTERN REGISTER

This register records all design patterns, interaction models, and code references derived from 21st.dev and open design specifications during the Stadium 3.0 engineering phase.

---

### Component Provenance Register

| Component Name | Source / Author | Original Reference | Applicable Licence | Dependencies | Adaptations Made for EA FC Intelligence | Location in Repository |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Glow & Ambient Floodlights** | `ibelick` | `21st.dev/r/ibelick/glow-effect` | MIT | Zero (Pure CSS) | Extracted radial stadium floodlight technique; implemented `.stadium-ambient-lights` and tier glow utility classes. | `stadium.css` |
| **Stats Card** | `ravikatiyar162` | `21st.dev/r/ravikatiyar162/stats-card-1` | MIT | Zero | Adapted for Squad DNA total fit, mean coverage, and scored slots metrics. | `CardSquadLab.css`, `CardSquadLab.tsx` |
| **Bento & Action Grid** | `0xUrvish` | `21st.dev/r/0xUrvish/bento-card` | MIT | Zero | Adapted into `.overview-modules` for 4-phase scouting lifecycle with hover elevation. | `Dashboard.tsx`, `stadium.css` |
| **Pill Tabs** | `sean0205` | `21st.dev/r/sean0205/tabs` | MIT | Zero | Replaced bulky tab rectangles with `.stadium-tabs` pill controls and keyboard accessibility. | `stadium.css`, `Search.tsx`, `Cards.tsx` |
| **Multi-Facet Radar** | `airbnb-visx` / `LegionWebDev` | `21st.dev/r/LegionWebDev/radar-chart` | MIT | Zero (Pure SVG) | Built zero-dependency SVG `<TacticalRadar />` mapping the 6 FIFA facets with dual polygon overlays. | `Visualizations.tsx` |
| **Holographic Card Sheen** | Custom Football Design Pattern | EA Sports Ultimate Team card spec | Original CSS | Zero | Implemented diagonal iridescent sweep animation on card hover. | `stadium.css`, `FootballCard.tsx` |

---

### Licensing & Asset Integrity Statement
- **Zero Paid Dependencies**: ₹0 budget consumed.
- **No Copyrighted Portraits**: Zero unauthorized player face assets; player portraiture uses deterministic silhouette and typography monogram badges.
- **Strict Data Honesty**: Zero simulated statistics or synthetic chemistry.
