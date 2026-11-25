# FC26 DATA GAPS

Every gap, its status, its blocker, and whether engineering can close it.

**Status:** `VERIFIED` · `ACCESSIBLE` · `PARTIALLY VERIFIED` · `UNKNOWN` · `BLOCKED` · `LEGALLY UNCLEAR`

---

## 1. Gap register

| # | Gap | Status | Blocker | Closable by engineering |
|---|---|---|---|---|
| G-01 | **No FC26 UT card data of any kind** | **BLOCKED** | No permitted source | **No** — legal/commercial |
| G-02 | No card identities (EA/FUT item ids) | BLOCKED | Same as G-01 | No |
| G-03 | No card-level attributes | BLOCKED | Same as G-01 | No |
| G-04 | No card-level PlayStyles | BLOCKED | Same as G-01 | No |
| G-05 | No Roles or familiarity, any level | BLOCKED | No source identified anywhere | No |
| G-06 | No market prices | BLOCKED / LEGALLY UNCLEAR | FutDB is metered with no bulk endpoint; others RED | No |
| G-07 | No verified chemistry rules | UNKNOWN | No source; FC26 mechanics unverified | No |
| G-08 | No Evolution lineage | BLOCKED | Same as G-01 | No |
| G-09 | No card types (base/TOTW/promo/Icon/Hero) | BLOCKED | Same as G-01 | No |
| G-10 | **Foundation licence chain unverified** | LEGALLY UNCLEAR | Raw CC0 files absent; exact ID match to GPL-3 dataset | **Partly** — re-retrieve and hash |
| G-11 | **Synthetic firewall not enforced in production SQL** | VERIFIED defect | — | **Yes — P0** |
| G-12 | **Conflict resolver cannot emit `UNRESOLVED`** | VERIFIED defect | — | **Yes — P0** |
| G-13 | **No `field_provenance` table** | VERIFIED gap | — | **Yes — P0** |
| G-14 | `real_player` layer effectively empty (20 / 16,228) | PARTIALLY VERIFIED | No permitted identity source | Partly |
| G-15 | PlayStyle coverage 45.2% with ambiguous absence semantics | PARTIALLY VERIFIED | Source publishes nothing for 54.8% | **Partly** — record publication explicitly |
| G-16 | **Foundation is a ~6-month-old snapshot; values diverge from live by up to 11 OVR** | VERIFIED | No refresh path | Partly — needs a permitted refresh |
| G-17 | No multi-release history — drift monitors impossible | VERIFIED | Single release | **Yes**, over time |
| G-18 | κ coverage gate inert (κ ≡ 1.00) | VERIFIED | Needs card data to exercise | No |
| G-19 | Reference distribution describes the ratings universe, not FUT | VERIFIED | Same as G-01 | **Yes** — tag `universe` |
| G-20 | `canonical_card_id` collides when type and rarity are both UNKNOWN | VERIFIED defect | — | **Yes — P0** |
| G-21 | No remote/API ingestion adapter | VERIFIED | Nothing permitted to connect to | Yes, once a source exists |
| G-22 | No labelled preference data for ML | VERIFIED | Needs traffic | No |
| G-23 | `team_fit` league comparison is a no-op | VERIFIED defect | — | **Yes — one line** |
| G-24 | Card-scope PlayStyle+ cap has no evidence | VERIFIED | Cap measured on players | **Yes** — keep UNKNOWN |
| G-25 | No women's universe in the foundation | VERIFIED | Source scope is men's only | Partly — 1,645 rows exist in a GPL-3 dataset |

---

## 2. The five that actually matter

**G-01 — no card data.** Everything card-shaped in the product is blocked by this one fact. It is not an engineering problem and no amount of pipeline work moves it. It is a legal/commercial question with exactly one identified candidate answer (FutDB, YELLOW) and one alternative (a written agreement with FUT.GG, FUTBIN or FUTWIZ).

**G-10 — licence chain.** The production foundation may be fine. It may also be a GPL-3 dataset wearing a CC0 manifest. `[MEASURED]` The evidence is a 16,228/16,228 ID-set match, 4,000/4,000 OVR agreement, and three missing raw files whose hashes were supposed to prove independence. This is closable in an afternoon by re-retrieving the CC0 files and verifying the hashes — and it should be done before anything ships.

**G-11, G-12, G-13 — three safety mechanisms that do not work.** The synthetic firewall does not filter, the conflict resolver cannot say "I don't know", and no attribute can be traced to an observation. All three are believed to be working. All three are cheap to fix. All three are the kind of defect that is harmless until the day it is catastrophic.

**G-16 — staleness.** `[MEASURED]` Foundation OVRs differ from reported in-season FC26 values by up to 11 points. The data is not wrong so much as **describing a different moment, and possibly a different universe**. There is currently no mechanism that would notice.

**G-05 — Roles.** The v3 architecture has a `role_modifier` slot. No source for Role data was identified anywhere in this investigation — not official, not community, not commercial. This may be a permanent gap, and the engine correctly returns `role_demand: UNAVAILABLE` rather than inventing one.

---

## 3. What is NOT a gap

Worth stating so the red-team session does not spend time here:

- Attribute coverage for players is **complete** — 14,412/14,412 outfield, 1,816/1,816 GK.
- Reference distributions are **fully computable** — every position group has n ≥ 1,816 per attribute, 36× the minimum.
- The canonical schema **models everything the product needs**, including cards, versions, evolutions, roles, prices and chemistry.
- UNKNOWN discipline is **genuinely enforced** end to end.
- The FC26/FC27 firewall is **sound**.
- Identity resolution logic is **correct** — it is starved, not wrong.

The architecture is ahead of the evidence. That is the right way round, but it means progress is now gated on permission, not on code.
