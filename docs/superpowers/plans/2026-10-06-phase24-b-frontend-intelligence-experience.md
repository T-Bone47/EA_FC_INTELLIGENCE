# Phase 24 / Plan B — Frontend Intelligence Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A page where a user states a football problem (FC27 → position → division → tactical style → optional preferences) and sees *why each player fits that problem* — with honest near-tie, evidence and interval presentation, plus 2–3 player comparison and deterministic what-if. The UI renders backend facts; it never ranks, scores or explains on its own.

**Architecture:** New isolated folder `frontend/src/intelligence/` (types, thin API wrappers, `RecommendationCard`, `Ladder`, `Intelligence` page, `ComparePanel`, `WhatIfPanel`) that reuses the existing client (`api.post`), hooks (`useAction`) and components (`Field`, `Loading`, `ErrorBox`, `Ovr`, `Pos`) and the existing dark design tokens in `styles.css`. The v2 pages stay untouched. One memorable element: the results ladder with **tie brackets and interval bars** (63–91% of adjacent top-10 pairs are within noise, so a strict ladder would lie).

**Tech Stack:** React 18 + TypeScript + Vite + vitest + @testing-library (already installed; **no new dependencies**). Commands from `frontend/`: `npx vitest run <file>`, `npm run build` (= `tsc --noEmit && vite build`).

**Spec:** `docs/superpowers/specs/2026-10-01-phase24-next-development-phase.md` + owner's Phase 24 directive §§9–14. API contract: `docs/API_V3.md` (Plan A, merged on this branch). Baseline: branch `phase24-v32-api-ui`; backend suite 747 passed / 24 failed / 1 skipped.

## Global Constraints

- "No frontend-side ranking formula. The backend ScoringContext is the single source of truth." Results render in **server order**; the UI never sorts, re-scores or computes deltas.
- "Do not allow the frontend or an LLM to independently calculate or invent the explanation." Every sentence about *why* is backend text (`explanation`, `why_ahead`, `why`, `tactical_fit`, `evidence`).
- "Clearly distinguish OVR from INTELLIGENCE SCORE. Never imply the intelligence score is an EA rating." OVR is labelled **EA OVR** and is descriptive only.
- Near ties are communicated, never hidden: when `near_tie_with_next` exists the UI says the order is not meaningful and shows `why_ahead`. "Do not invent arbitrary confidence labels": show the engine's `confidence.level` as-is.
- "Do not silently choose a division": for FC27 the user must pick **Men's / Women's / Both** before the request can be sent; FC26 shows that it has no division label.
- UT-card scope stays disabled: no card UI. No new npm dependency. v2 pages are not modified (except adding the nav link and route).

## Review Focus

1. FC27 with no division choice must not be sendable; "Both" sends no `division` and the response banner states the mixed pool (Task 4).
2. A fully published player has a zero-width interval — show "complete evidence", never a fake range (Task 2).
3. Hidden re-sorting — tested with a fixture whose scores are deliberately not monotonic (Task 3) and by a source guard (Task 5).
4. Structured server errors (503 research opt-in, 422 `DIVISION_NOT_APPLICABLE`) must surface the server's message, not "Request failed" (Task 1).
5. Compare is capped at 3 and describes differences with backend `why` text only; what-if only offers presets that apply to the current request (Tasks 6–7).

## File Structure

- Modify `frontend/src/api/client.ts` — structured v3 error detail. Modify `frontend/src/App.tsx` (+ nav) — route `/intelligence`. Modify `frontend/src/styles.css` — `.ix-*` classes only.
- Create `frontend/src/intelligence/{types.ts, api.ts, Card.tsx, Ladder.tsx, Intelligence.tsx, ComparePanel.tsx, WhatIfPanel.tsx}` and one `*.test.ts(x)` per file, plus `noRanking.test.ts`.

---

### Task 1: Types, thin API wrappers, structured errors

**Files:** Create `intelligence/types.ts`, `intelligence/api.ts`; Modify `api/client.ts`; Test `intelligence/api.test.ts`.

**Interfaces:**
- Produces: `RecommendRequest` (`game_version`, `position`, `tactical_profile`, `secondary_tactical_profile?`, `lam?`, `division?`, `include_research_data?`, `limit`), `Entry`, `RecommendResponse`, `CompareResponse`, `WhatIfResponse` mirroring `docs/API_V3.md` field-for-field; `recommend(req)`, `compare(req, entityIds)`, `whatIf(base, variants, trackTop)` — each exactly one `api.post` and **no transformation of the response**. `ApiError` gains optional `code` and `requires`, filled when `detail` is an object `{error, detail, requires?}`; `message` = that `detail` text.

- [ ] **Step 1: Write the failing tests** (fetch mocked with `vi.stubGlobal`):
  - `recommend posts the request unchanged and returns the response untouched` (URL `/api/v3/recommendations`, body deep-equals input; result `toBe`-equal in content to the mocked JSON).
  - `a 503 research opt-in error exposes the server message, code and requires` (`message` contains the server text; `code === "REFERENCE_DISTRIBUTION_UNAVAILABLE"`; `requires === "include_research_data"`).
  - `a 422 DIVISION_NOT_APPLICABLE error passes the server text through`.
- [ ] **Step 2: Run** `npx vitest run src/intelligence/api.test.ts` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** In `client.ts` where `detail` is built, add: if `data.detail` is an object with a string `detail`, use it as the message and attach `code = data.detail.error`, `requires = data.detail.requires`.
- [ ] **Step 4: Run** the test plus `npx vitest run src/api/client.test.ts` — Expected: pass (existing client tests unchanged). **Step 5: Commit** `feat(ui): v3 types, thin api wrappers, structured server errors`.

### Task 2: `RecommendationCard`

**Files:** Create `intelligence/Card.tsx`; Test `intelligence/Card.test.tsx` (fixture: one real-shaped `Entry`).

**Interfaces:** `Card({ entry, selected?, onToggle? })`. Shows: name, `Pos`, **EA OVR** (value from `player.overall_rating`, label says descriptive), **Intelligence Score** (4 dp, `aria-label="Intelligence Score <value>"`), interval (`score_interval.low === high` → text "Complete evidence — no interval", else "<low>–<high>"), coverage %, `confidence.level` (title "reporting only"), key attributes (`key_strengths`: name + value), PlayStyles (`player.playstyles`), tactical fit (`demand_stages[].stage` + `top_demanded` rows), the first `explanation.reasons` item as the concise line with a `<details>` holding all `reasons`, `trade_offs`, `unknowns`, and — when `near_tie_with_next` exists — a note listing `why_ahead`.

- [ ] **Step 1: Write the failing tests:** `labels EA OVR and Intelligence Score separately` (both labels present; no text matching /rating/i attached to the score); `shows "Complete evidence" for a zero-width interval and a range for a partial one`; `renders the backend explanation text verbatim` (each `reasons` string appears exactly); `near-tie note says the order is not meaningful and lists why_ahead when within_noise_threshold`; `an entry without near_tie_with_next shows no tie note`.
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement** (reuse `Ovr`/`Pos`; no logic beyond formatting). **Step 4: Run** — pass. **Step 5: Commit** `feat(ui): recommendation card (EA OVR vs Intelligence Score, honest intervals)`.

### Task 3: `Ladder` — server order, tie brackets

**Files:** Create `intelligence/Ladder.tsx`; Test `intelligence/Ladder.test.tsx`.

**Interfaces:** `Ladder({ ranked, selected, onToggle })`. Renders cards in array order. Consecutive entries linked by `near_tie_with_next?.within_noise_threshold` are wrapped in one `<section class="ix-tie-run" aria-label="Effectively tied">` with the label "Effectively tied — scores within noise"; a link with only `intervals_overlap` shows "intervals overlap" between the two cards. Grouping uses the backend flags only.

- [ ] **Step 1: Write the failing tests:** `renders in server order even when scores are not monotonic` (fixture scores 0.80, 0.90, 0.85 → DOM order equals array order); `groups a run of noise-tied neighbours in one bracket` (3 entries linked → one `Effectively tied` section containing 3 cards); `shows an overlap note when only intervals overlap`; `no bracket when nothing is tied`.
- [ ] **Step 2–5:** run (FAIL) → implement → run (pass) → commit `feat(ui): results ladder with tie brackets, server order preserved`.

### Task 4: `Intelligence` page — explicit flow and division gate

**Files:** Create `intelligence/Intelligence.tsx` (exports page and pure `buildRequest(state)`); Test `intelligence/Intelligence.test.tsx` (mock `./api`).

**Interfaces:** `buildRequest(s: {gameVersion, position, division: "MEN"|"WOMEN"|"BOTH"|null, tactical, secondary?, lam?}) -> RecommendRequest | null` — `null` when FC27 and `division === null`; FC27 adds `include_research_data: true`; `division` only for MEN/WOMEN; FC26 never sends `division`. Page order: game version (FC27 default) → position → division (FC27 only; **no preselected option**; FC26 shows "FC26 has no division label") → tactical style (`BALANCED`, `POSSESSION`, `HIGH_PRESS`, `LOW_BLOCK`, `COUNTER_ATTACK`, `DIRECT_PLAY`) → optional secondary style and emphasis → "Find players". After a response it shows a scope banner built from `division` (`ALL_DIVISIONS` → "Mixed pool: N men's and M women's players were scored together"; `FILTERED` → "<division> only") and the `Ladder`. Errors render through `ErrorBox` with the server message.

- [ ] **Step 1: Write the failing tests:** `buildRequest returns null for FC27 until a division is chosen`; `BOTH sends no division and MEN sends "Men's Football"`; `FC26 never sends a division`; `the Find players button is disabled until FC27 division is chosen`; `submitting calls recommend with exactly the built request`; `mixed-pool banner shows the backend candidate_counts`; `a rejected request shows the server message`.
- [ ] **Step 2–5:** run (FAIL) → implement → run (pass) → commit `feat(ui): intelligence page with explicit division choice`.

### Task 5: Wiring, styles, no-ranking guard, build (working slice complete)

**Files:** Modify `App.tsx`, nav component, `styles.css`; Test `intelligence/noRanking.test.ts`.

- [ ] **Step 1: Write the failing test:** `no intelligence source file sorts, reverses or re-scores` — reads every non-test `.ts/.tsx` under `src/intelligence/` with `fs` and asserts none matches `/\.(sort|toSorted|reverse)\(/`; and `the route /intelligence renders the page` (render `<App>` at that path, expect the first step heading).
- [ ] **Step 2: Run** — Expected: FAIL (route missing). **Step 3: Implement** route + nav link ("Intelligence") + `.ix-*` CSS (tie bracket using `--warn`, interval bar using existing accent/info tokens, tabular numerals for scores). **Step 4: Run** `npx vitest run` (whole frontend suite) and `npm run build` — Expected: all pass, build succeeds. **Step 5: Commit** `feat(ui): route, styles and no-ranking guard`.

### Task 6: Compare mode (2–3 players)

**Files:** Create `intelligence/ComparePanel.tsx`; Modify `Intelligence.tsx`; Test `intelligence/ComparePanel.test.tsx`.

**Interfaces:** `ComparePanel({ response })`: a table (columns = players): Intelligence Score + interval text, coverage, confidence level, key attributes; below it one sentence per `pairwise` item built only from backend fields: within noise → "<A> and <B> are effectively tied (gap <score_gap>)"; otherwise "For this tactical context, <higher> scores higher than <lower> because <why joined by '; '>". Names come from `players` by `entity_id`. In `Ladder` selection is capped at 3 (further toggles are ignored and a hint is shown); "Compare" calls `compare(request, ids)`.

- [ ] **Step 1: Write the failing tests:** `uses backend why text and never a generic "is better"`; `a noise-tied pair is described as effectively tied`; `selection is capped at 3`. **Step 2–5:** run → implement → run → commit `feat(ui): compare mode with backend-derived explanations`.

### Task 7: What-if presets

**Files:** Create `intelligence/WhatIfPanel.tsx`; Modify `Intelligence.tsx`; Test `intelligence/WhatIfPanel.test.tsx`.

**Interfaces:** `presetsFor(request) -> {label, change}[]`: tactical presets (`High press`, `Low block`, `Possession`) excluding the current style; `CM → CAM` / `CAM → CM` only for those positions; for FC27 with MEN/WOMEN the opposite division; emphasis `λ 0.5` / `λ 0.9`. Clicking one calls `whatIf(base, [{label, ...change}], 10)` and renders each `tracked_from_base` row exactly as returned (`base_rank` → `new_rank`) plus `entered_top` names. The UI computes nothing.

- [ ] **Step 1: Write the failing tests:** `offers only presets that apply` (CM shows `CM → CAM`, GK does not; FC26 has no division preset); `a preset posts the right variant`; `renders server ranks verbatim` (fixture `base_rank 2 → new_rank 5`). **Step 2–5:** run → implement → run (then full `npx vitest run` and `npm run build`) → commit `feat(ui): what-if presets rendering backend results verbatim`.
