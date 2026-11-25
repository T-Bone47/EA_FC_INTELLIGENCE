# PHASE 20 LEGAL REVIEW

Not a legal opinion. An engineering-level classification separating accessibility, permission, and redistribution rights, per source, with evidence.

## Summary table

| Source | Accessible | Automated access | Storage | Derived data | Redistribution | Commercial use | legal_status |
|---|---|---|---|---|---|---|---|
| EA Community API | No (closed) | No | Unknown | Unknown | No | N/A | **RED** |
| EA Ratings website | Yes (human) | No | Unknown | Unknown | Unknown | Unknown | **RED** (automation) |
| FUTBIN | Yes (human) | **No** — explicit prohibition | No | No | No | **Explicitly prohibited without a license** | **RED** |
| FUT.GG | Yes (human) | **No** — explicit prohibition ("for any purpose") | No | No | No | Not reached (moot) | **RED** |
| FUTWIZ | Yes (human) | Unknown | Unknown | Unknown | Unknown | Unknown | **UNKNOWN → RED** |
| FutDB (futdb.app) | Yes (API key) | Yes, within rate limits | **Not addressed anywhere** | **Not addressed anywhere** | **Not addressed anywhere** | Implied by pricing tiers, never stated | **UNKNOWN → RED** |
| FUT-DB.com | Yes (API key, paid) | Yes, per paid terms | Not addressed | Not addressed | Not addressed | **Explicitly stated: individuals and companies** | **UNKNOWN → RED** |

## Why "accessible" and "commercial use permitted" do not add up to GREEN

Both FutDB.app and FUT-DB.com allow a paying customer to **query** their API. Neither publishes a document granting the three additional rights a production recommendation product actually needs:

1. **Storage** — may we persist the returned data in our own database?
2. **Derivation** — may we compute new values (demand-weighted scores, aggregate statistics) from it?
3. **Redistribution / serving** — may we show derived results to our own end users as part of our product?

A REST API's existence answers none of these. FUT-DB.com's explicit "individuals and companies may use this" is the most permissive language found across all seven sources, but it describes who may **call the API**, not what they may **do with the response** afterward. Absent an explicit answer to 1–3, both remain UNKNOWN, which this project's own stated rule (Phase 20 §5, §6, §15) requires to be treated as RED for production ingestion.

## Attribution and licence findings

No candidate source offers a licence broad enough to redistribute derived card data commercially without a direct written agreement. FUTBIN's narrow carve-out (pricing data, with attribution, for students/content-creators) does not cover a commercial product ingesting the full card universe, and does not apply here regardless.

## Legal-review queue (unchanged priority order, one item resolved)

1. **Can we obtain a written commercial agreement with FutDB.app or FUT-DB.com** clarifying storage/derivative/redistribution rights? — **Still open; this is the single highest-value next step**, now correctly targeting two candidate services rather than one, since the naming collision was not previously identified.
2. Can the current player-foundation licence chain (GPL-3 collision) be resolved? — Still open, unrelated to card data, tracked separately (`FC26_DATA_GAPS.md` G-10).
3. Is EA's IP position on a derived FC26 recommendation product acceptable at all? — Still open, strategic, upstream of everything else.
4. Would a written agreement with FUTBIN, FUT.GG, or FUTWIZ be obtainable? — Still open, alternative route.
5. **RESOLVED this session (partially)**: FUTWIZ's terms remain genuinely unlocatable after two search attempts; this is now a confirmed dead end for passive research — the only remaining path for FUTWIZ is direct outreach, not more searching.

## Decision

**No source in this review clears GREEN or actionable YELLOW.** Production card ingestion is not legally supported by current evidence.
