# Phase 4 Design Decisions

**Status:** Approved by user on 2026-09-14

## Understanding summary

- The FC26 real-player foundation is the primary product layer; player quality is not player suitability.
- The single canonical scoring system remains `backend/services/recommendation_engine_v2.py`.
- Player intelligence must work without Ultimate Team cards, prices, chemistry, Roles, or Evolutions.
- FC26 and FC27 remain absolutely separated; FC27 is `NO_DATA` until real data is acquired.
- Unknown information is explicitly represented and never fabricated or treated as negative evidence.
- Every recommendation remains deterministic, decomposable, and source-aware.

## Approved source-governance approach

| Source classification | Production player foundation | Research/validation layer |
| --- | --- | --- |
| Cleared (for example, CC0) | Eligible after normal validation and provenance checks | Yes |
| GPL, research-only, restricted, or unclear | Not authoritative canonical input | Yes, when permitted and isolated |

The field-level authority and conflict-resolution path decides among values from eligible sources; no source may blindly overwrite a canonical value. Restricted-source observations retain provenance so a later clearance can be evaluated without redoing forensic work.

## Architecture decisions

1. **One engine, additive evolution.** Extend V2 in place and preserve its legacy request contract. A parallel engine would split truth and make regressions harder to detect.
2. **Dataset adapters before canonical writes.** Every acquired dataset receives a forensic manifest, schema comparison, and source classification before it can enter candidate ingestion.
3. **Evidence before claims.** Detailed fields, GK attributes, positions, PlayStyles, and any card field are only surfaced when records prove the field exists and its authority is known.
4. **Player layer first.** Dataset/card investigations are optional extensions and cannot gate player ingestion, scoring, API, UI, or test work.
5. **Measured rollout.** Baseline tests and golden scenarios run before changes; focused regressions, integrity checks, and benchmarks run afterward.

## Non-functional assumptions

- The local workspace may not include Git metadata, so file-level evidence and live tests are the baseline record when Git commands are unavailable.
- Public Kaggle downloads use only normal authenticated/public tooling; no access-control bypasses are permitted.
- Existing production contracts, synthetic firewall, and version walls are compatibility constraints.
- The current data scale is roughly 16k players; full-pool latency and memory remain benchmarked rather than guessed.

## Decision log

| Decision | Alternatives considered | Reason |
| --- | --- | --- |
| Cleared data only for canonical production foundation | Admit all available sources | Maintains redistribution and provenance honesty without discarding research value. |
| Isolate restricted data for research and validation | Ignore restricted data entirely | Supports schema analysis, conflict detection, and engineering value without claiming production authority. |
| Retain V2 as the one engine | Add a V3/parallel engine | Preserves a single deterministic scoring authority and existing compatibility guarantees. |
| UT cards remain optional | Make cards/prices a prerequisite | The product's core is contextual real-player intelligence. |
