# Navigation & Game Context Report — Project Stadium 2.0

**Module:** Global Application Shell (`Nav.tsx`, `App.tsx`)  
**Status:** Completed & Integrated  
**Primary Enhancements:** Elevated Sidebar Brand & Navigation, Unified Command Search, Game Version Clarity (FC26 Historical vs FC27 Research).

---

## 1. Key Transformation Highlights

1. **Stadium 2.0 Brand & Navigation System:**
   - Redesigned sidebar with distinct active states, icon-text alignment, and collapsible functionality.
   - Preserves all navigation titles (`Overview`, `Discover`, `Intelligence`, `Squad Lab`, `Compare`, `Evidence Lab`, `Profile`) and character marks (`⌂Overview`) required by E2E test assertions.
   - Smooth slide-out mobile drawer with accessible Escape key dismissal and focus restoration to the Menu button.

2. **Game-Version Communication Architecture:**
   - Solved the confusion between global game version selection and research scopes.
   - **FC26 Context:** Labeled as Canonical Data with direct release status indicators.
   - **FC27 Context:** Displays prominent `FC27 Research` tag, dataset release hash, and explicit opt-in controls for experimental card intelligence.
   - Prevents accidental cross-version contamination across Discover, Intelligence Studio, and Squad Lab.

3. **Command / Quick Search Interface:**
   - Single prominent search bar in the global header with clear label `Command / Search players…`.
   - Dispatches debounced query directly to `/search?q=...` with instant results rendering.
