# Frontend — Player intelligence (`/intelligence`)

Phase 24 / Plan B. A page where a user states a football problem and sees *why each player fits it*.
The UI renders backend facts only (`docs/API_V3.md`); it never ranks, scores or explains on its own.

## Flow
Game (FC27 default) → Position → **Division** (FC27: choose Men's / Women's / Both — nothing is preselected and the
button stays disabled until chosen; FC26 shows that it has no division label) → Tactical style (the six styles the
Phase 23 lab measured) → optional secondary style and emphasis → *Find players*.
Results: a scope banner built from `division.candidate_counts`, then the ladder. Select 2–3 players to compare, or run a
what-if preset. Compare and what-if always use the request the **shown results** came from, not the live form.

## Rules (each has a test)
- Server order, always: no `sort`/`reverse` anywhere in `src/intelligence` (`noRanking.test.ts`; a non-monotonic fixture proves order).
- **EA OVR** is labelled descriptive; the **Intelligence Score** is never called a rating. Confidence is the engine's `confidence.level`, verbatim.
- Near ties: consecutive neighbours the backend marks `within_noise_threshold` are bracketed ("Effectively tied"); the card says the
  order is not meaningful and lists `why_ahead`. Zero-width intervals read "Complete evidence", never a fake range.
- Explanations, comparison sentences and what-if ranks/deltas are backend text and numbers.
- Server errors surface their own message (503 research opt-in, 422 `DIVISION_NOT_APPLICABLE`).

## Files (`frontend/src/intelligence/`)
`types.ts`, `api.ts` (3 thin wrappers) · `Card.tsx` · `Ladder.tsx` · `Intelligence.tsx` (page + `buildRequest`) ·
`ComparePanel.tsx` · `WhatIfPanel.tsx` (+ `presetsFor`) · `fixtures/` (recorded FC26 API responses) · `*.test.ts(x)`.
Shared files touched: `App.tsx` (route), `Nav.tsx` (link), `styles.css` (`.ix-*`), `api/client.ts` (structured error detail).

## Tests
- `cd frontend && npx vitest run` — 76 tests + 3 live tests that skip offline. `npm run build` type-checks (tests included) and builds.
- Fixtures are real FC26 responses. **FC27 is RESEARCH_ONLY and must never be committed into frontend source.**
- Live end-to-end (jsdom, not a browser): start the API, then
  `E2E_API_URL=http://127.0.0.1:8011 npx vitest run src/intelligence/e2e.live.test.tsx`.

## Not verified
Real-browser rendering and visual layout, mobile layout, an accessibility audit beyond role/label queries, and the FC27 path in the UI.
Interval *bars* are not implemented (every real player currently has complete evidence, so the interval is a point); only text is shown.
