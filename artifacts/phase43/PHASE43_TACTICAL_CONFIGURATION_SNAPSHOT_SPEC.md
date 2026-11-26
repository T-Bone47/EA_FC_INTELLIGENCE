# Phase 43B Tactical Configuration Snapshot Specification

## 1. Purpose & Design Invariants
`backend/services/tactical_snapshot_service.py` (`TacticalSnapshotService`) creates immutable, SHA-256 hashed, versioned `TacticalConfigurationSnapshot` records scoped strictly to `(user_id, game_version, game_patch)`. Once persisted, snapshots are immutable (`is_immutable=True`) so historical experiments never mutate underneath match links.

## 2. Schema & Captured Dimensions (`TacticalSnapshotCreate` / `TacticalConfigurationSnapshot`)
- **Identity & Edition Context:** `snapshot_id` (`TSNP-<8hex>`), `user_id`, `label`, `game_version` (`FC26` or `FC27`), `game_patch` (default `PATCH_1.04`), `gameplay_mode` (default `COMPETITIVE_RIVALS`), `source_squad_id`.
- **System & Slider Settings:** `formation`, `tactical_profile`, `build_up_style`, `defensive_approach`, `line_height` (`1..100`), `width_setting` (`1..100`), `tactical_instructions` (`Dict[str, Any]`).
- **11-Slot Tactical Roster (`TacticalSlotConfig`):** `slot_index` (`0..10`), `slot_position`, `entity_id`, `entity_type` (`ut_card`, `game_player`, `custom`, `UNKNOWN`), `player_name`, `overall_rating`, `assigned_role`, `role_focus`, `role_familiarity` (`BASE`, `ROLE_PLUS`, `ROLE_PLUS_PLUS`, `UNKNOWN`), `playstyles`, `attributes`.
- **Hydrated Structural Summaries:**
  - `cohesion_summary`: Computed via `compute_whole_xi_synergy(formation, tactical_profile, slots_data, cards_by_id)` using `SimpleNamespace` card proxies.
  - `partnership_summary`: Evaluated via `PartnershipIntelligenceEngine.evaluate_partnership(...)` across central pivot slots (`CDM`/`CM`) or first two filled slots.
  - `gamer_style_preferences`: Attached from `Phase40Repository.get_cold_start_preferences(uid)` strictly as preference metadata (never promoted to empirical evidence).
- **Versioning & Provenance:** Canonical SHA-256 `config_hash` (`compute_config_hash`), sequential `version_number` linked via `parent_snapshot_id`, and `market_price_status = "MARKET_PRICE_UNAVAILABLE"`.

## 3. Explicit Unknown Handling & Cross-Edition Firewall
- Rather than guessing defaults, `create_snapshot` explicitly populates `unknown_fields` whenever fields are absent:
  - Missing `build_up_style`, `defensive_approach`, `line_height`, `width_setting`, `squad_slots`
  - Partial slot gaps: `some_slot_roles`, `some_role_familiarities`, `some_player_attributes`
  - Edition disclosure: `chemistry_verified_rules_partial` (FC27) or `market_price_coins` (FC26)
- **Edition Wall:** Attempting to fork a snapshot (`parent_snapshot_id`) across `FC26` and `FC27` raises `ValueError("Cannot fork snapshot across FC26 and FC27 edition boundary.")` (verified in `test_phase43b_to_e_snapshots_fingerprints_and_experiment_statistics`).
- **Saved Squad Hydration:** Passing `source_squad_id` without explicit `slots` automatically hydrates saved squad assignments owned by `user.id` cleanly with explicit `role_familiarity="UNKNOWN"`.
