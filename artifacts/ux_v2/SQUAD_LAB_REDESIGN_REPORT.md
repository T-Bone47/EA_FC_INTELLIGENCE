# Squad Lab Redesign Report — Project Stadium 2.0

**Module:** Ultimate Team Squad Lab (`/cards/squad-lab`)  
**Status:** Completed & Integrated  
**Primary Enhancements:** Immediate Pitch Render on Mount, Interactive Formation Slots, Shortlist Drawer, Integrated Squad DNA & Smart Upgrade Studio Cockpit.

---

## 1. Key Transformation Highlights

1. **Immediate First-Render Pitch Experience:**
   - Overcame the previous critical failure where the pitch and workspace were completely hidden behind an authorization check.
   - The full tactical pitch with 11 formation slots (including distinct Goalkeeper zone), tactical controls, and shortlist tray renders immediately on first mount.
   - If local FC27 card research is disabled, a prominent inline warning banner guides the user to enable research mode without removing the football interface.

2. **Tactile Pitch-Centered Interaction:**
   - Keyboard accessible formation slots: focusing on an unfilled slot (e.g. `RW Unfilled`) and pressing Enter smoothly focuses the corresponding slot assignment select menu.
   - Slot fit score indicators and locked status padlock icons displayed directly on pitch cards.
   - Interactive formation switching with preview of target formation suitability and changes.

3. **Integrated Squad DNA & Smart Upgrade Studio:**
   - `#squad-dna`: Visual breakdown of Total Fit, Mean Evidence Coverage, and Scored Slots, along with full slot evaluation ladders and non-dominated tactical matrices.
   - `#upgrade-studio`: Side-by-side Before/After replacement cards displaying exact card IDs, fit gain deltas, and single-click "Apply replacements" with full undo support.

4. **Preserved Contracts & Reliability:**
   - Preserves exact selectors checked by `stadium.mjs`: `Assign RW`, `button: RW Unfilled`, `Replacement mode`, `Preview card squad`, `Squad DNA`, `Smart Upgrade Studio`, `Apply replacements`, `Undo last edit`.
