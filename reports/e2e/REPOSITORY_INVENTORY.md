# Repository inventory (Phase 1)

Generated from the code, the OpenAPI schema and the live database by `scripts/e2e/write_inventory.py`; component statuses reflect only what was executed in this session.

## Actual v3 request-to-recommendation path
```
Browser (React SPA, /intelligence) --POST /api/v3/recommendations--> [nginx example in deploy/ — not exercised]
  -> FastAPI app (backend/api/main.py): CORS allow-list, request-id middleware, GZip(>=1 KB), unhandled-exception handler (logs request_id, returns 500)
  -> router backend/api/routes/recommendations.py  (pydantic RecommendationRequestV3: extra fields forbidden, limits)  [auth: optional]
  -> RecommendationServiceV3.recommend
       check_division -> _resolve (game version, RESEARCH_ONLY gate, reference distribution; FC27 never falls back to FC26)
       -> CandidateRepository.load_candidates   (SQL; cache key "version|synthetic|research"; TTL 120 s validated by a game_player watermark)
       -> RecommendationEngineV3.recommend
            eligibility gates -> demand composition (position + tactical blend) -> capability C_lo/C_hi (reference distribution, evidence interval)
            -> bounded modifiers (PlayStyle; interaction DISABLED) -> deterministic ranking -> ScoringContext per candidate
       -> explanation_service_v3 (derived from ScoringContext) -> v3_response_blocks (confidence, tactical_fit, evidence, near_tie, division)
       -> JSON response (+ eafc.v3.telemetry log record)
  <- gzip response  <- React renders the backend order (no sorting; tested)
```

## Components
| Component | Responsibility | Entry point | Tests in this baseline | Runtime verification (this session) | Known limitations |
|---|---|---|---|---|---|
| API application | routing, CORS, request id, gzip, error handler | `backend/api/main.py` | test_security*, test_v3_api_contract | exercised live (uvicorn) and via real browser | OpenAPI docs are served at `/api/docs` in dev; no CI |
| v3 routes | recommend / compare / what-if | `routes/recommendations.py` | test_v3_api_contract, test_recommendations_v3_api, test_phase23_version_wall_api | live + real-browser QA (34/34 checks) | no rate limiter on v3 routes (to be confirmed in Phase 8/9) |
| v2 routes | legacy recommend / compare / cards / squads | `routes/*.py` | test_integration_production etc. | partially | **still mounted**; 15 of the 24 baseline failures concern the v2 engine/features |
| Auth | register, login, JWT, sessions | `routes/auth.py`, `deps.py` | test_auth* | login throttling reproduced (10/min -> 429) | in-process limiter: per worker, not shared |
| RecommendationServiceV3 | orchestration, gates, response blocks, telemetry | `services/recommendation_service_v3.py` | v3 contract/api tests | live | - |
| Engine V3.2 | eligibility, demand, capability, modifiers, ranking, ScoringContext | `services/recommendation_engine_v3.py` (+ modules below) | test_engine_v3_*, test_v3_2_*, golden tests | executed; V3.2 lab NOT rerun in this session yet | GK model tactically inert (documented); interaction disabled |
| Versioned config | V3.1 frozen, V3.2 default | `services/v3_config.py` | test_v3_2_config | executed | - |
| Reference distributions | frozen per game version | `services/reference_distribution.py`, `data/reference_distributions/` | test_reference_*, version wall | rebuilt DB reproduced the frozen hashes earlier | FC27 distribution is research-only |
| CandidateRepository | candidate SQL + cache | `data_access/candidate_repository.py` | test_postgres_integration | executed | watermark covers only `game_player`; see Phase 7 |
| PostgreSQL | 51 tables, triggers (version wall, research firewall) | `db/*.sql`, `scripts/setup_database.py` | test_postgres_integration, test_fc27_card_identity_research | rebuilt from scratch this session | tests write to the shared dev DB |
| Ingestion | idempotent loaders + provenance builders | `scripts/ingest_*.py`, `build_*.py` | ingest tests | re-run this session (FC26 16,228; FC27 19,789; provenance 1,645,154) | - |
| FC27 card-identity layer | research-only isolated tables | migration 009, `scripts/ingest_fc27_card_identity.py` | test_fc27_card_identity_research (16) | ingested: 20,175 identities | `futgg` registry = NOT_PERMITTED; owner decision pending |
| Frontend | React SPA, `/intelligence` | `frontend/src` | vitest 82 + 3 live (skipped offline) | real Chromium QA 34/34, axe 0 violations in 3 states | no real-device or screen-reader testing |
| Intelligence lab | invariants + discrimination research | `services/intelligence_lab.py`, `scripts/run_intelligence_lab.py` | test_lab_resume | NOT rerun in this session | ~10 min; sandbox restarts interrupt it |
| Observability | loggers `eafc.api`, `eafc.v3.telemetry`; `X-Request-ID`; telemetry record | `main.py`, service | test_security (header) | read + exercised | no metrics endpoint; no tracing |
| Deployment | Dockerfile, docker-compose, systemd unit, nginx example | `deploy/` | none | **NOT exercised** | - |
| **Real-time propagation** | **NOT_IMPLEMENTED** | - | - | strict code search: no WebSocket/SSE/queue/scheduler/polling/background task | request/response only; see Phase 7 |

Database facts: 51 base tables; key row counts {'game_player': 36017, 'field_provenance': 1645154, 'fc27_card_identity': 20175, 'ut_card': 60, 'card_price': 60, 'fc27_card_open_flag': 68}. Non-internal triggers: 7.
Applied migrations: `db/migrations/*.sql` (002-009) on top of `DATABASE_SCHEMA_V1.sql`.

## API surface (42 operations, from OpenAPI)
| Method | Path | Summary | Auth |
|---|---|---|---|
| GET | `/api` | Api Root | - |
| POST | `/api/auth/login` | Login | - |
| POST | `/api/auth/logout` | Logout | - |
| POST | `/api/auth/logout-all` | Logout All | - |
| GET | `/api/auth/me` | Me | - |
| PATCH | `/api/auth/me` | Update Me | - |
| POST | `/api/auth/signup` | Signup | - |
| GET | `/api/card-data-status` | Card Data Status | - |
| GET | `/api/cards` | Search Cards | - |
| GET | `/api/cards/{card_id}` | Card Page | - |
| GET | `/api/cards/{card_id}/prices` | Card Prices | - |
| GET | `/api/cards/{card_id}/value` | Card Value | - |
| GET | `/api/cards/{card_id}/versions` | Card Versions | - |
| POST | `/api/compare` | Compare | - |
| POST | `/api/feedback` | Record Feedback | - |
| GET | `/api/feedback/stats` | Feedback Stats | - |
| GET | `/api/health` | Health | - |
| GET | `/api/health/ready` | Ready | - |
| GET | `/api/meta/game-versions` | Game Versions | - |
| GET | `/api/meta/reference` | Reference | - |
| GET | `/api/players` | Search Players | - |
| GET | `/api/players/facets` | Facets | - |
| GET | `/api/players/{player_id}` | Player Page | - |
| POST | `/api/recommendations` | Recommendations | - |
| GET | `/api/recommendations/feedback/analytics` | Feedback Analytics | - |
| POST | `/api/recommendations/parse-intent` | Parse Intent Endpoint | - |
| GET | `/api/saved-players` | List Saved | - |
| POST | `/api/saved-players` | Save Player | - |
| DELETE | `/api/saved-players/{entity_id}` | Unsave Player | - |
| POST | `/api/squads` | Create Squad | - |
| GET | `/api/squads` | List Squads | - |
| GET | `/api/squads/{squad_id}` | Get Squad | - |
| PATCH | `/api/squads/{squad_id}` | Update Squad | - |
| DELETE | `/api/squads/{squad_id}` | Delete Squad | - |
| GET | `/api/squads/{squad_id}/evaluation` | Evaluate Squad | - |
| POST | `/api/squads/{squad_id}/recommend-replacement` | Recommend Replacement | - |
| PUT | `/api/squads/{squad_id}/slots/{slot_index}` | Assign Slot | - |
| DELETE | `/api/squads/{squad_id}/slots/{slot_index}` | Clear Slot | - |
| GET | `/api/v1/health` | Health | - |
| POST | `/api/v3/compare` | Compare V3 | - |
| POST | `/api/v3/recommendations` | Recommendations V3 | - |
| POST | `/api/v3/what-if` | What If V3 | - |

## Engine/service modules (first docstring line)
| Module | Responsibility |
|---|---|
| `archetypes.py` | ARCHETYPES + GAMEPLAY PROFILE + VERSATILITY (§15, §16, §17). |
| `attribute_model.py` | ATTRIBUTE MODEL v2.1 (§8, §9, §10, §11) — the opt-in intelligence path for |
| `budget_provider.py` | Budget / market price providers. |
| `capability_model.py` | V3 capability and evidence interval. |
| `card_publication_gate.py` | No-fabrication firewall and card publication gate (Phase 20 S11, S12, S18). |
| `card_value_service.py` | Card VALUE + PRICE services (§13/§14/§48). |
| `chemistry_service.py` | Chemistry architecture (§15/§16) — honest by construction. |
| `comparison_service.py` | Comparison service (§32): why is A better for THIS user — not just "+2 OVR". |
| `confidence_service.py` | Data-level confidence: how trustworthy is what we know about an entity? |
| `confidence_v2.py` | CONFIDENCE 2.0 (§24, §26, §27) — ADDITIVE enrichment. |
| `conflict_resolver.py` | Source conflict resolution (§11). |
| `counterfactual.py` | COUNTERFACTUALS + SENSITIVITY (§37, §38). |
| `data_license_gate.py` | Data license release gate (V3_1_CALIBRATION_REPORT.md Phase 19, extended |
| `demand_composition.py` | V3 demand vector composition. |
| `eligibility_gate.py` | V3 eligibility gate. |
| `engine_config.py` | ENGINE CONFIG — explicit, tunable configuration for Intelligence Engine v2.1. |
| `engine_evaluation.py` | ENGINE EVALUATION SUITE (§49, §50, §51). |
| `engine_experiments.py` | ENGINE EXPERIMENT FRAMEWORK (§48). |
| `explanation_service.py` | Deterministic explanation generation. |
| `explanation_service_v3.py` | V3 explanation service. |
| `feature_extraction.py` | Feature extraction: candidate + requirements -> structured feature views. |
| `feedback_analytics.py` | FEEDBACK ANALYTICS (§33) — deterministic, label-counting only. |
| `fit_components.py` | Fit components for Recommendation Engine V2. |
| `fit_value.py` | FitValue — the missing-data-aware score primitive of engine V2. |
| `formations.py` | FORMATION + TACTICAL-DIMENSION intelligence (§6, §7). |
| `intelligence_lab.py` | Intelligence Evaluation Lab (Phase 23). |
| `intent.py` | STRUCTURED INTENT (§2, §3). |
| `intent_parser.py` | DETERMINISTIC intent parser (§3, §4) — natural language -> ParsedIntent. |
| `playstyle_context.py` | CONTEXTUAL PLAYSTYLE INTELLIGENCE (§12, §13). |
| `provider_license_evaluator.py` | Provider license evidence evaluator (Phase 21 S9). |
| `recommendation_confidence.py` | Recommendation-level confidence. |
| `recommendation_engine_v2.py` | RECOMMENDATION ENGINE V2 (v2.1 intelligence upgrade) — deterministic, |
| `recommendation_engine_v3.py` | V3 recommendation engine. |
| `recommendation_service.py` | RecommendationService — production orchestration for /api/recommendations. |
| `recommendation_service_v3.py` | V3 recommendation service. Player-scope only. |
| `reference_distribution.py` | Frozen reference distributions for the v3 evidence interval (C_lo/C_hi). |
| `role_fit_service.py` | Role fit service. |
| `scoring_config.py` | Deterministic scoring configuration for Recommendation Engine V2. |
| `scoring_context.py` | V3 ScoringContext. |
| `squad_intelligence.py` | SQUAD INTELLIGENCE (§18, §19, §20). |
| `team_context.py` | Team/squad context assembly. |
| `v3_config.py` | V3 intelligence engine configuration. |
| `v3_response_blocks.py` | Pure response-block builders for the v3 API (Phase 24 / Plan A). |

## Test modules and baseline outcome
| Module | Outcome |
|---|---|
| `test_api` | 17 passed |
| `test_auth` | 18 passed |
| `test_card_api` | 9 passed |
| `test_card_ingestion_phase3` | 9 passed |
| `test_card_model` | 18 passed |
| `test_card_scenarios` | 22 passed 1 skipped |
| `test_card_value_chemistry` | 18 passed |
| `test_confidence_service` | 5 passed |
| `test_conflict_resolver` | 5 passed |
| `test_data_license_gate` | 13 passed |
| `test_data_quality` | 15 passed |
| `test_e2e_journey` | 4 passed |
| `test_engine_adversarial_phase7` | 9 failed 41 passed |
| `test_engine_intelligence` | 51 passed |
| `test_engine_ovr_trap` | 7 passed |
| `test_engine_robustness` | 20 passed |
| `test_engine_scenarios` | 14 passed |
| `test_engine_unknown_data` | 10 passed |
| `test_engine_v3_adversarial` | 14 passed |
| `test_engine_v3_invariants` | 21 passed |
| `test_engine_v3_real_data` | 4 failed 10 passed |
| `test_fc27_adapter` | 29 passed |
| `test_fc27_card_identity_research` | 16 passed |
| `test_golden_fixtures` | 13 passed |
| `test_golden_fixtures_v3_2` | 6 passed |
| `test_identity_resolver` | 8 passed |
| `test_ingestion_pipeline_integration` | 6 passed |
| `test_integration_production` | 11 failed 30 passed |
| `test_no_fabrication_firewall` | 22 passed |
| `test_normalizer` | 7 passed |
| `test_phase21_provider_evidence` | 30 passed |
| `test_phase23_version_wall_api` | 58 passed |
| `test_postgres_integration` | 7 passed |
| `test_production_boundary` | 3 passed |
| `test_recommendation_engine_v2_evaluation` | 32 passed |
| `test_recommendations_api` | 21 passed |
| `test_recommendations_v3_api` | 5 passed |
| `test_security` | 13 passed |
| `test_v3_1_calibration_hardening` | 30 passed |
| `test_v3_2_config` | 11 passed |
| `test_v3_2_missing_data` | 19 passed |
| `test_v3_api_contract` | 29 passed |
| `test_v3_production_safety` | 7 passed |
| `test_v3_response_blocks` | 5 passed |
