# Phase 41.5A — Baseline Audit & Provider Readiness Report

**Date:** 2026-11-25  
**Scope:** Existing AI Coach, LLM Integrations, Tool Contracts, Knowledge Service, Persistence, Security, Environment Configuration & Live Provider Verification  
**Baseline Test Run:** `74 passed` in `14.82s` across V3.2.1 golden fixtures (`test_golden_fixtures_v3_2.py`, `test_golden_fixtures.py`), Phase 40 (`test_phase40_*.py`), Phase 41 (`test_phase41_*.py`), `test_security.py`, and `test_no_fabrication_firewall.py`.

---

## 1. Current AI Coach Audit

| Subsystem | Observed Implementation | Phase 41.5 Gap / Action |
| :--- | :--- | :--- |
| **Orchestrator** ([personal_coach_orchestrator.py](../../backend/services/personal_coach_orchestrator.py)) | Deterministic keyword router (`_select_tools`, capped at 7 tools) building fixed prose templates (`DETERMINISTIC_COACH`). `_try_optional_llm()` only rewrites the finished deterministic summary via legacy `OLLAMA_HOST` (`/api/generate`) or paid `OPENAI_API_KEY` (`gpt-4o-mini`), with zero tool-calling, zero Gemini/OpenRouter support, zero streaming, zero failover loop, and zero structured Pydantic repair. | Replace legacy Ollama/OpenAI hook with bounded multi-turn agentic loop (`GeminiProvider` + `OpenRouterProvider` + `FootballModelRouter` + `FreeUsageGuard` + `QuotaManager`), keeping deterministic engine calculation + strict fallback as guaranteed baseline. |
| **Tool Registry** ([coach_tools.py](../../backend/services/coach_tools.py)) | 34 typed, user-scoped tools (`22` Phase 40 + `12` Phase 41) enforcing caller `user_id` isolation and regex prompt-injection detection (`detect_prompt_injection`). `search_player_cards` queries `PlayerRepository`; `recommend_squad_changes` uses `PersonalGameplayFitService`. **Missing:** direct V3.2.1 `recommend_players` bridge, detailed `get_player_attributes` / `get_player_playstyles` / `find_similar_players`, confirmation-gated `optimize_squad` / `preview_player_replacement` / `preview_formation_change` / `find_squad_weaknesses`, Phase 39 pitch control & transition analytics tools, and Training history/progress tools. | Keep all 34 tools intact and add missing grounded tools backed exclusively by existing `RecommendationServiceV3`, `PlayerRepository`, `SquadRepository`, `ComparisonService`, `card_squad_lab`, `SpatialIntelligenceEngine`, `DecisionReviewService`, `CounterfactualFootballEngine`, and `FootballKnowledgeService`. |
| **Knowledge / RAG** ([football_knowledge_service.py](../../backend/services/football_knowledge_service.py)) | Static 9-entry `KNOWLEDGE_ENTRIES` list queried with unnormalized substring weights and `game_version` / `topic` / `official_only` filters. Missing formations taxonomy, PlayStyles+, chemistry rules, passing/shooting/defensive mechanics, patch diffs (FC26 vs FC27), controls/camera impact, Friends of Tracking, SoccerAction, and BM25 length normalization. | Upgrade to calibrated Okapi **BM25** + hierarchical source authority scoring (`OFFICIAL_FACT` > `OBSERVED_USER_EVIDENCE` > `RESEARCH_METHODOLOGY` > `COMMUNITY_OBSERVATION`) over an expanded curated & cited corpus. |
| **Database & Persistence** ([015_phase40_coaching_intelligence.sql](../../db/migrations/015_phase40_coaching_intelligence.sql), [phase40_repository.py](../../backend/repositories/phase40_repository.py)) | `phase40_coach_session` + `phase40_coach_message` exist with PostgreSQL + thread-safe in-memory dual fallback, strictly scoped by `user_id`. No list/rename/delete session routes exposed yet, no session context metadata (`active_squad_id`, `active_match_id`, `conversation_summary`), no provider usage ledger, and no pending squad-proposal confirmation table. | Add migration `017_phase41_5_agentic_coach.sql` (+ down migration) with session context columns, secret-free `phase41_5_provider_usage_log`, and `phase41_5_squad_proposal` with undo snapshots. |
| **Environment & Secrets** ([config.py](../../backend/core/config.py), `.env`) | Project `.env` originally held `DATABASE_URL` and `ENVIRONMENT` only. User supplied credentials (`.env` attachment) contain `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `AI_COACH_ENABLED=true`, `AI_COACH_PROVIDER=gemini`, `AI_COACH_FALLBACK_PROVIDER=openrouter`, `GEMINI_MODEL=gemini-4-hydrogen`, `OPENROUTER_MODEL=openrouter/free`, `AI_COACH_FREE_ONLY=true`, `AI_COACH_ALLOW_PAID_USAGE=false`, `AI_COACH_DETERMINISTIC_FALLBACK=true`, `AI_COACH_VIDEO_UPLOAD_TO_LLM=false`. `.gitignore` already excludes `.env` and `.env.*`. | Merged keys cleanly without overwriting existing DB config; added backward-compatible alias mapping (`AI_COACH_VIDEO_UPLOAD_TO_LLM` and `AI_COACH_ALLOW_EXTERNAL_VIDEO`); added `.env.example` with empty placeholders; added secret redaction across logs, errors, and public endpoints. |
| **Frontend Coach UI** ([PersonalCoach.tsx](../../frontend/src/pages/PersonalCoach.tsx)) | Single-session Q&A stack with `consentExternal` checkbox, deterministic badge, and evidence clip links. Missing multi-conversation history/switcher/deletion, SSE streaming activity states, interactive player recommendation cards, comparison/Squad Lab links, confirmation-gated squad change previews, provider selector/visibility, and stop/retry controls. | Upgrade within Stadium 3.0 tokens (`#0B1018`, `#121B27`, `#B6F279`, `#67C8F2`) while preserving existing `PersonalCoach.test.tsx` contracts. |

---

## 2. Live API & SDK Verification Findings (2026-11-25)

1. **Google Gemini SDK (`google-genai 3.6.1`)**:
   - Installed official `google-genai` package (replacing deprecated `google-generativeai`).
   - Verified `GET https://generativelanguage.googleapis.com/v1beta/models` returned **HTTP 200** with **65 models**.
   - Confirmed present & `generateContent`-capable: `gemini-4-hydrogen` (1,048,576 input / 65,536 output), `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemma-4-26b-a4b-it`, `gemma-4-31b-it`.
   - Paid/specialized models also appear in catalog (`gemini-4-argon`, `gemini-4-carbon`, `gemini-2.5-pro`, `gemini-3.1-pro-preview`, image/TTS models) and MUST be explicitly blocked by `FreeUsageGuard` when `AI_COACH_FREE_ONLY=true`.
2. **Gemini Skills Evaluation (`google-gemini/gemini-skills` -> `gemini-api-dev`)**:
   - Evaluated `gemini-api-dev` skill patterns: enforces modern `from google import genai` client, `types.GenerateContentConfig`, Pydantic `response_schema` with `response_mime_type="application/json"`, `generate_content_stream`, and blocks deprecated `google-generativeai` and legacy 1.5 models. All SDK guidance applied directly in `GeminiProvider`; Antigravity plugin `antigravity-plugins-official/plugin/gemini-api` can also be optionally enabled by the user.
3. **OpenRouter Free Catalog (`https://openrouter.ai/api/v1`)**:
   - Authenticated key check `GET /api/v1/key` returned **HTTP 200** (`is_free_tier: true`, `usage: 0`, `limit: null`).
   - Public catalog `GET /api/v1/models` returned **HTTP 200** across **472 models**, with **14 zero-priced endpoints** (`prompt="0"`, `completion="0"`):
     - `openrouter/free` (200K ctx; `text, image`; `tools`, `response_format`, `structured_outputs`, `reasoning`)
     - `nvidia/nemotron-3.5-super-vl:free` (1M ctx; `text, image, video`; `tools`, `response_format`, `structured_outputs`, `reasoning`)
     - `nvidia/nemotron-3-ultra-550b-a55b:free` (1M ctx; `text`; `tools`, `reasoning`)
     - `nvidia/nemotron-3.5-lightning:free` (1M ctx; `text`; `tools`, `reasoning`)
     - `google/gemma-4-26b-a4b-it:free` (262K ctx; `image, text, video`; `tools`, `response_format`)
     - `google/gemma-4-31b-it:free` (262K ctx; `image, text, video`; `tools`, `response_format`)
     - `baidu/ernie-5.5-flash-preview:free` (1.024M ctx; `text`; `tools`, `response_format`, `structured_outputs`)
     - `inclusionai/ling-3.2-flash:free`, `particle-ai/particle-1:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `recursive/flint-v1.0:free`, `liquid/lfm-3-1.7b:free`.
     - Filtered OUT from tool-calling chat: `google/lyria-3-pro-preview`, `google/lyria-3-clip-preview` (no `tools` support; specialized audio/media preview).
4. **Terms, Privacy & Free-Tier Governance Notes**:
   - **Gemini Unpaid Tier**: Google may inspect/use prompts and responses to train/improve products outside EEA/UK/CH; minimum age 18+; prohibited on apps directed at users under 18 or un-billed EEA/UK public deployments. Local adult development only; prompts minimize/strip raw PII and videos/images default to disabled.
   - **OpenRouter Free Endpoints**: Zero-cost endpoints may log or train on prompts depending on upstream host; request payloads enforce `provider: {"allow_fallbacks": false, "require_parameters": true, "max_price": {"prompt": 0, "completion": 0}}` and support `data_collection="deny"` for strict-privacy mode.

---

## 3. Target Phase 41.5 Architecture Checklist

1. **Free-Only & Quota Core (`backend/services/llm/free_guard.py`)**: Strict pre-flight allowlist + zero-price verification + RPM/daily/per-user/turn request counters + HTTP 429 cooldown.
2. **Dynamic Capability Registry (`backend/services/llm/registry.py`)**: TTL-cached discovery for both Gemini and OpenRouter free catalogs + health monitor.
3. **Providers (`gemini_provider.py`, `openrouter_provider.py`)**: `FootballLLMProvider` implementations with native function calling, streaming, structured JSON schema, bounded retry, timeout, cancellation, and secret redaction.
4. **Intelligent Router (`router.py`)**: `Gemini -> OpenRouter Free -> DeterministicCoachFallback`, task-aware model choice, lossless cross-provider normalized history rebuilding.
5. **Expanded Tool Registry & BM25 Football RAG (`coach_tools.py`, `football_knowledge_service.py`)**: V3.2.1 player recommendations + Squad Lab optimization/preview + confirmation-gated squad edits + BM25 cited retrieval.
6. **Agentic Orchestrator & SSE API (`personal_coach_orchestrator.py`, `phase40_coach.py`)**: Bounded ReAct tool loop, anti-hallucination verification, session CRUD, squad proposal confirmation/rollback, SSE streaming.
7. **Stadium 3.0 Coach Workspace (`PersonalCoach.tsx`)**: Multi-conversation history, streaming status indicators, player cards + squad proposal UI, provider controls, error recovery.
8. **Benchmark & Tests (`FC_COACH_BENCH_V1`)**: >= 100 curated evaluation cases + comprehensive mocked/security/regression tests + tiny verified live API smoke test.
