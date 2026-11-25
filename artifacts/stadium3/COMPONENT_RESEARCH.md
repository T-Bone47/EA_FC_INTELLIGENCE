# STADIUM 3.0 — 21ST.DEV COMPONENT RESEARCH & EVALUATION

**Design Goal:** Identify the highest-quality component primitives, microinteractions, and visual patterns across 21st.dev to adapt into the Stadium 3.0 Design System.

---

### 1. Component Discovery Catalog

| Category | 21st.dev ID / Component | Author | Evaluated Capabilities | Decision & Adaptation |
| :--- | :--- | :--- | :--- | :--- |
| **Glow & Light Effects** | `#57 Glow Effect` | `ibelick` | Radial glow, animated pulse, multi-color ambient lighting, reduced-motion friendly. | **Selected & Adapted**: Implemented custom CSS ambient floodlights (`.stadium-ambient-lights`) and tier glows without external dependencies. |
| **Statistics Cards** | `#8321 Stats Card` | `ravikatiyar162` | Single metric display, color-coded trend indicators, high contrast. | **Selected & Adapted**: Adapted into `<StatCard />` in Squad Lab & DNA breakdown. |
| **Bento & Feature Grid** | `#10457 Bento Card` | `0xUrvish` | Interactive bento cards with micro-transitions and workspace preview. | **Selected & Adapted**: Adapted for Overview Command Center workflow cards and intelligence highlights. |
| **Select & Combobox** | `#279 Select` | `originui` | Separators, accessible focus rings, keyboard navigation, dark theme. | **Selected & Adapted**: Adapted for formation, position, and tactical archetype dropdowns. |
| **Radar Visualizations** | `#2353 Radar Chart` | `airbnb-visx` | Multi-variable attribute comparisons, customizable polygon fills. | **Selected & Adapted**: Adapted into pure SVG `<TacticalRadar />` with 6 facets (PAC, SHO, PAS, DRI, DEF, PHY). |
| **Tabs & Segmented Controls** | `#4086 Tabs` | `sean0205` | Pill-shaped navigation, active indicator transitions, touch targets. | **Selected & Adapted**: Adapted into `.stadium-tabs` for View toggles (Grid/Table) and Workspace tabs. |

---

### 2. Integration Strategy
Rather than importing bloated packages with incompatible styling, Stadium 3.0 extracts the **best interaction and visual patterns** from 21st.dev and crafts them into native, ultra-fast, zero-dependency React + SVG + CSS primitives tailored specifically for football intelligence.
