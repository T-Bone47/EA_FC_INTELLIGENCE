# Phase 44 System Prompt & Free-Tier Router Updates

## 1. New `TaskIntent.GAMER_DNA` & Token-Budget Preserved Schema Selection
- Added `TaskIntent.GAMER_DNA` in `backend/services/llm/router.py` while keeping Gemini Free -> OpenRouter Free -> Deterministic Coach failover unchanged.
- Added `TaskIntent.GAMER_DNA` to `INTENT_TO_TOOLS` in `backend/services/coach_tools_extended.py` with **exactly 7** tool schemas (`get_gamer_style_profile`, `get_style_archetypes`, `get_professional_style_matches`, `get_elite_skill_gap`, `get_style_evolution`, `recommend_style_compatible_players`, `recommend_elite_training_plan`), preserving the Phase 42 `3..7` tool schema ceiling across **all 13 intents**.

## 2. Context-Aware Co-Pilot Routing (`/gamer-dna`)
Inside `PersonalCoachOrchestrator` (`backend/services/personal_coach_orchestrator.py`):
- Routes queries mentioning `"pro player"`, `"play like"`, `"style match"`, `"archetype"`, `"skill gap"`, `"style evolution"`, `"playing style"`, `"style sandbox"`, OR originating from `source_route in ("GAMER_DNA", "/GAMER-DNA")` to `TaskIntent.GAMER_DNA`.
- Deterministic payload assembly (`_assemble_deterministic_payload`) cites `GAMER_DNA_V2_ENGINE`, explicitly surfaces `ABSTAINED_NO_AUTHORIZED_REFERENCES` whenever pro matching abstains, and attaches Group G execution gap actions separately from playing-style descriptors.
