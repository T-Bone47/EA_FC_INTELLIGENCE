# CLAUDE.md — EA FC Player Intelligence (handoff)

## Current data budget and local card intelligence

External data and API budget is ₹0. Use the owner's pinned FC27 archives, established research releases and permitted free resources. Market observations remain optional. Squad optimization uses deterministic V3.2 slot scores and works without price inputs. The local FC27 card research release is isolated from the public catalogue. See `artifacts/phase29/ZERO_BUDGET_STATUS.md` for the active setup and verification. The phase notes below record historical development.

Read this first. It is the state of the project as of the end of the Claude.ai sessions.

## What this project is
A contextual recommendation engine: "which player/card is best for THIS user, tactic, formation, position?" — not "highest OVR". Deterministic engine (V3.1) does the ranking; an LLM may later only *explain* the ranking. Player-scope only in production. UT-card scope is deliberately disabled.

## Non-negotiable rules (carried from every phase)
1. **Zero fabrication.** Unknown stays `NULL`/UNKNOWN. Never invent cards, PlayStyle effects, Roles, prices, chemistry, IDs.
2. **Version wall.** FC26 and FC27 never mix (records, distributions, licences, prices, PlayStyles).
3. **Player != card.** Player-level data must never be presented as UT-card data.
4. **Public != licensed.** UNKNOWN legal status behaves as RED. No scraping of sites whose ToS prohibit it; no CAPTCHA/anti-bot/proxy circumvention.
5. **Fail closed.** `allow_unverified=True` may never work with `environment=PRODUCTION`.
6. **Never weaken/adjust a test or threshold to turn it green.** Report failures classified.
7. **Do not change V3.1 scoring defaults** (lambda=0.7, PlayStyle Model A, interaction modifier disabled, confidence reporting-only) without evidence.

## Current state (measured 2026-09-30)
- Engine: **V3.1** unchanged defaults, now version-aware. Entry: `backend/services/recommendation_engine_v3.py` (refuses a reference distribution of another version/universe: `ReferenceDistributionMismatch`). API: `POST /api/v3/recommendations`, `POST /api/v3/compare`, `POST /api/v3/what-if` (`entity_scope` is `Literal["game_player"]`).
- Data (local Postgres, Docker container `eafc-intelligence-pg`, use `DATABASE_URL=postgresql://eafc:eafc_dev_only@127.0.0.1:5432/eafc_intelligence` — NOT localhost: it resolves to ::1 and psycopg_pool hangs on Windows; run with `PYTHONUTF8=1`):
  - FC26: 16,228 `game_player` CANONICAL (licence chain UNVERIFIED, G-10), 585,560 `field_provenance`.
  - FC27: 19,789 `game_player` **RESEARCH_ONLY** (Kaggle mikedpad v4, snapshot 2026-09-12; 17,849 men / 1,940 women / 2,204 GK), 1,059,594 `field_provenance`, 36 RESEARCH_ONLY PlayStyle definitions (identical names to FC26). Reverse completeness check: 0 published values dropped (2,204 GK x 6 GK face stats deliberately unmapped). Raw file local-only (`data/fc27_research/raw/`, gitignored; hashes in `data/fc27_research/MANIFEST.json`).
  - 60 synthetic `ut_card` (SYNTHETIC_TEST), 0 real UT cards, 20 real_player.
- Reference distributions: FC26 `data/reference_distributions/fc26-players-2026-09-r1.json` (frozen, rebuild verified identical); FC27 `data/reference_distributions/research/fc27-players-2026-09-r1.json` (RESEARCH_ONLY, only via `load_reference_for(..., allow_research_only=True)`).
- Research firewall: production reads serve `data_status='CANONICAL'` only (candidate/player repositories, health, meta, v2 provenance); FC27 served only when the request sets `include_research_data=true` AND the deployment is not production (licence gate `RESEARCH_ONLY` status + `ProductionOverrideForbidden`); migration 008 trigger forbids non-RESEARCH_ONLY rows from a RESEARCH_ONLY source.
- **Test baseline: 662 passed / 24 failed / 1 skipped** (`artifacts/phase23/run_after_intelligence.txt`). The 24 are the same classified IDs as before: 9 `test_engine_adversarial_phase7.py` (v2 history), 11 `test_integration_production.py` (pre-existing), 4 policy (RD-3 x3, RD-4 CB). Diff failing IDs against `artifacts/phase23/baseline_pytest.txt`.
- Intelligence lab: `scripts/run_intelligence_lab.py` → `artifacts/phase23/lab/`; results in `docs/PHASE_23_ENGINE_RESULTS.md`. Open owner decisions: adopt `missing_value_charge="ZERO"` (fixes measured missing-data invariant violation; 6 synthetic goldens move), GK signed two-pole demand H-GK-1 (fixes tactically inert GK ranking; fails pre-registered near-tie rule on FC26).
- NOT done yet (Phase 23 remainder): frontend still calls v2 `/api/recommendations`; v3 UI (recommend/compare/what-if), PHASE_23 API/UI/E2E reports, Phase 22 artifact set (source_registry_v2, schema/PlayStyle diff docs, HANDOFF_TO_GLM.md), official EA cross-check script (evidence page saved: `artifacts/phase22/ea_official_ratings_page1_2026-09-29.json`).

## Setup (a fresh machine)
```bash
pip install pytest pytest-cov fastapi bcrypt pyjwt pydantic-settings httpx "psycopg[binary]" psycopg-pool email-validator python-multipart
# Postgres 16, role eafc / eafc_dev_only, db eafc_intelligence, extensions pgcrypto pg_trgm
export DATABASE_URL="postgresql://eafc:eafc_dev_only@localhost:5432/eafc_intelligence"
psql ... -f db/DATABASE_SCHEMA_V1.sql
for f in db/migrations/00{2,3,4,5,6,7}_*.sql; do psql ... -f $f; done
psql ... -f db/seed_reference_data.sql
python scripts/register_card_sources.py
python scripts/ingest_fc26_foundation.py
python scripts/ingest_real_identities.py
python scripts/ingest_synthetic_cards.py
python scripts/build_reference_distribution_v3.py
python scripts/build_field_provenance_v3.py
python scripts/build_golden_fixtures_v3_1.py   # only regenerates artifacts; do NOT overwrite goldens silently
python -m pytest backend/tests -q -p no:cacheprovider
```
Gotchas: `backend.core.db.query()` returns **dict rows** (`dict_row`), not tuples. Postgres in the sandbox kept dying; `service postgresql start`. Data is dynamic: `scripts/` ingestion is idempotent (deterministic UUIDs).

## V3.1 architecture (files in `backend/services/`)
`v3_config.py` (versioned config, each constant tagged MEASURED/POLICY/PLACEHOLDER) -> `demand_composition.py` (position x signed two-pole tactical demand, lambda blend) -> `eligibility_gate.py` (G1 version, G2 synthetic, G3 GK, G4 position; position is a gate, never a score) -> `capability_model.py` (saturation, C_lo/C_hi from frozen P10/P90, coverage kappa; ranking on C_lo) -> `recommendation_engine_v3.py` (bounded PlayStyle modifier, tie-break `(-R, -kappa, entity_id)`; no OVR channel) -> `scoring_context.py` + `explanation_service_v3.py` (explanations reconstructed from the same context, 1e-9) -> `recommendation_service_v3.py` (telemetry, diagnostics). v2 (`recommendation_engine_v2.py`) is frozen as history.
Key measured facts: rho(R,OVR) is 0.75-0.95 (structural; OVR *dependence* is exactly 0 — shuffle test); lambda safe range [0.3,0.8]; interaction modifier stays disabled (self-relative cohesion measures violate monotonicity); Model B PlayStyle rejected (needs invented mapping).

## Licence / release gates
- `backend/services/data_license_gate.py`: `DataLicenseStatus` VERIFIED|PARTIAL|UNVERIFIED|BLOCKED; `check_license_gate`, `gate_or_raise(environment=...)`, `evaluate_dataset_release`. Unregistered dataset = BLOCKED.
- `backend/services/card_publication_gate.py`: PUBLISHABLE/REVIEW_REQUIRED/NOT_PUBLISHABLE per card.
- `backend/services/provider_license_evaluator.py`: SILENT/AMBIGUOUS never become ALLOWED.
- Provider status (Phase 20/21): FUTBIN BLOCKED, FUT.GG RED, FUTWIZ UNKNOWN, FutDB.app UNKNOWN (no terms/contact found), FUT-DB.com BLOCKED-ish (ToS s.7 prohibits reproduction/distribution; contact service@chilledcoins.com via imprint). No outreach was sent. See `docs/` and `artifacts/phase20|21/`.

## FC27 base-player foundation — history (items 1-5 and 7 DONE 2026-09-29/30; see "Current state"; item 6 docs still to write)
Input: Kaggle "EA SPORTS FC 27 Player Ratings" `players.csv` (19,789 rows, 60 cols, `edition=fc27`, snapshot 2026-09-12; user's `archive.zip`; **not included in this repo**). Verified against its README (17,849 men / 1,940 women / 2,204 GK / 40.7% with PlayStyles / height,weight blank / OVR in range).
**Licence: the dataset's own text says "unofficial, non-commercial snapshot for analysis and education".** => must be ingested as `data_status='RESEARCH_ONLY'`, never `CANONICAL`, never given VERIFIED. It is good for engineering/validation/version-wall tests; it cannot ship commercially or fine-tune a commercial model unless the terms change or a licence is obtained. Do not silently promote it.

Done so far:
- `db/migrations/007_research_only_status.sql` (applied): `RESEARCH_ONLY` allowed on `game_player` and `real_player`.
- `DataStatus.RESEARCH_ONLY` added in `backend/domain/card_model.py`.
- FC27 `game_version` row already exists in DB.

TODO (in order):
1. Register source `kaggle_fc27_player_ratings` (usage_status research-only, legal_gate NOT cleared) in `source_registry`; add an entry to `artifacts/phase22/` source registry v2 as RESEARCH_ONLY / non-commercial.
2. Write `scripts/ingest_fc27_research.py` mirroring `scripts/ingest_fc26_foundation.py` (adapter -> normalize -> validate -> repo) with `game_version="FC27"`, data_status RESEARCH_ONLY. Column map (CSV -> canonical): `attacking_crossing->crossing, attacking_finishing->finishing, attacking_heading_accuracy->heading_accuracy, attacking_short_passing->short_passing, attacking_volleys->volleys, skill_dribbling->dribbling_detail, skill_curve->curve, skill_fk_accuracy->free_kick_accuracy, skill_long_passing->long_passing, skill_ball_control->ball_control, movement_acceleration->acceleration, movement_sprint_speed->sprint_speed, movement_agility->agility, movement_reactions->reactions, movement_balance->balance, power_shot_power->shot_power, power_jumping->jumping, power_stamina->stamina, power_strength->strength, power_long_shots->long_shots, mentality_aggression->aggression, mentality_interceptions->interceptions, mentality_positioning->positioning, mentality_vision->vision, mentality_penalties->penalties, mentality_composure->composure, defending_awareness->defensive_awareness, defending_standing_tackle->standing_tackle, defending_sliding_tackle->sliding_tackle, goalkeeping_{diving,handling,kicking,positioning,reflexes}->gk_*`; facets pace..physicality map 1:1; `position->position_primary`; `alternate_positions` is space-separated; `playstyles` comma-separated, trailing `+` = PlayStyle+; `player_id` is EA's id (SOURCE id, still needs `game_version` in the identity preimage so FC26:123 != FC27:123). Filter/partition Men's vs Women's via `gender`; women's are NOT in the FC26 foundation, so keep them flagged, do not mix silently. Check PlayStyle names against FC26 vocabulary — FC27 may have new ones: do not map, record as observed.
3. Make `data_license_gate.py` version- and scope-aware: key `(dataset_version, game_version, scope)`; FC26/FC27 x player/card independent; unregistered = BLOCKED. (A `str_replace` attempt failed in the last session — the edit was **not applied**; do it fresh against the current file, then update `backend/tests/test_data_license_gate.py` for the new keyword args and keep the 575/24/1 baseline.) Register FC27 player research dataset as UNVERIFIED-for-production/RESEARCH_ONLY.
4. Version-wall tests (Phase 22 list): FC26<->FC27 pool/reference/price/PlayStyle/Role/provenance isolation; reference distributions must carry `game_version` + `universe` and be refused on mismatch. Build `fc27-players-<date>-r1` reference distribution **from RESEARCH_ONLY data only for validation**, mark it research-only and unusable by the production engine path.
5. Run the V3 engine against FC27 RESEARCH_ONLY data (engine currently requires `DEFAULT_REFERENCE_VERSION` fc26; make version-aware without changing scoring), confirm no FC26/FC27 contamination, add golden fixtures only from this real data (never fabricated).
6. Schema diff FC26 vs FC27 from real columns (34 detailed attrs vs FC26's 29+5 GK; note FC27 PlayStyle vocabulary) -> `FC26_FC27_ATTRIBUTE_SCHEMA_DIFF.md`. Do not assume renamed == same semantics.
7. Update `field_provenance` build for FC27, re-run the full suite, classify failures, write `PHASE_22_*` docs (see `docs/`).

## Explicitly NOT done / blocked
- **UT-card scope: disabled.** No permitted source has legitimately granted storage/derivation/display rights. Do not enable, do not map players to fake cards.
- **Fine-tuning (Augmentoolkit/Unsloth/QLoRA): not started.** The sandbox had no GPU/torch, 3.9GB RAM, 1 CPU. Do this on a GPU box. Even then: the FC27 dataset is non-commercial => any fine-tune on it is research-only. Generated training examples must be fact-checked against canonical data (drop any with FC26 values, unknown-as-known, invented PlayStyles/Roles/prices), and the LLM must never rank — only explain the deterministic `ScoringContext`.
- FC26 player licence G-10 unresolved: re-retrieve the three original raw CC0 files named in `data/fc26_real_foundation/MANIFEST.json` and verify hashes; the foundation is an exact ID match to a GPL-3 research dataset. `DataLicenseStatus` stays UNVERIFIED until then.
- Policy decisions needing an owner: RD-3 OVR-correlation ceiling (0.85 unreachable at any lambda), RD-4 CB spread (0.094 vs 0.10), kappa_min (placeholder; inert on player data), lambda safe range.
- Context: FC27 launches 2026-09-25 (early access from 09-18); FC26 UT is winding down. Treat FC27 as the forward target, FC26 as historical/supported.

## Where things are
- `docs/` — all architecture/audit/report markdown from every phase (V3 architecture+spec+test matrix, FC26 data audit specs, Phase 20/21 reports, V3.1 calibration report, baselines, test results, the two FC27/dataset master plans).
- `artifacts/v3_1/` (baseline, lambda sweep, golden fixtures), `artifacts/phase20/`, `artifacts/phase21/` (source registry, rights matrix, outreach registry, outreach packages), `artifacts/phase22/`.
- `tools/scratch_probes/` — throwaway calibration scripts used for the measurements (reference only).
- Tests added: `test_engine_v3_{invariants,adversarial,real_data}.py`, `test_v3_production_safety.py`, `test_recommendations_v3_api.py`, `test_v3_1_calibration_hardening.py`, `test_golden_fixtures.py`, `test_data_license_gate.py`, `test_no_fabrication_firewall.py`, `test_phase21_provider_evidence.py`.
- Fixes made to v2-era code (each proven with a live adversarial case): synthetic-firewall SQL precedence bug (`candidate_repository`), conflict resolver can now emit `UNRESOLVED` (`conflict_resolver`), `compute_canonical_id` returns None when card_type and rarity are both unknown, `team_fit` league self-comparison bug.

## Working style that worked
Baseline first (run the suite, record counts) -> change small -> re-run -> diff failure IDs -> report exact numbers. When a result contradicts your earlier claim, say so (a Spearman tie-handling bug once flipped the CM finding). Ask a human for anything involving third-party permission or contacts.

---
## Phase 24 status (in progress) — 2026-10-06 (branch `phase24-v32-api-ui`; sandbox rebuild, not yet run on the owner's machine)
- **V3.2** (engine 3.2.0, config `v3.2-2026-09-30-r1`): `missing_value_charge` P10 -> ZERO. V3.1 is frozen and reproducible (`V3_1_CONFIG`, unmodified V3.1 golden test). 7 named golden fixtures / 8 fingerprints changed (6 guarded + `same_player_two_tactics`); no ranking changed. GK experiment and interactions untouched.
- **API v3** (`docs/API_V3.md`, drift-guarded): unified request id, explicit division policy (FC26+division -> 422; FC27 `division.scope`), reporting-only `confidence`, `tactical_fit` + `evidence` blocks, shared near-tie logic in compare, what-if division variants + depth-50 tracking, gzip. Measured: engine is 86-93% of a CM request; response 786 KB raw / 145 KB gzip.
- **Frontend** `/intelligence` (`docs/FRONTEND_INTELLIGENCE.md`): 79 vitest tests incl. 3 live UI<->API tests (jsdom, not a browser); `noRanking` guard.
- **FC27 card identity layer** (migration 009, gated ingest): research-only, isolated tables; `futgg` registry entry stays NOT_PERMITTED (owner decision pending).
- Backend suite: 24 known failures unchanged (same IDs as Phase 23). Plans: `docs/superpowers/plans/`.
- NOT done: V3.2 lab run, frontend visual/browser verification, Plan C (security audit, rate limiting decision, latency budget, final report). Pending owner decisions: card-package registry policy; cap on the response `excluded` list (3,856 entries/request).
