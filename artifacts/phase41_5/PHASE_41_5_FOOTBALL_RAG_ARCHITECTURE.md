# Phase 41.5 Football Knowledge Retrieval Architecture (Specialized RAG)

**Module:** [football_knowledge_service.py](../../backend/services/football_knowledge_service.py) (`FootballKnowledgeService`)

---

## 1. Retrieval Design & Rationale

Instead of uploading the 16K+ player catalogue or installing ungrounded third-party embeddings, Phase 41.5 implements:
1. **Okapi BM25 Lexical Index** (`k1 = 1.4`, `b = 0.75`) weighted across `topic`, `mechanic`, `tags`, `source_title`, `applicability`, and `factual_summary`.
2. **Metadata & Edition Filtering**:
   - Strict `game_version` boundary (`FC26` requests never retrieve `FC27`-exclusive mechanics like FC27's 3-PlayStyle+ cap, while `BOTH`/`GENERAL` remain accessible).
   - `game_patch`, `topic`, and `official_only` boolean facets.
3. **Hierarchical Source Authority Boosts**:
   - `OFFICIAL_FACT`: `1.35x` (EA Sports FC26/FC27 Pitch Notes, Accessibility docs, User Agreement & FC Rules)
   - `OBSERVED_USER_EVIDENCE`: `1.25x`
   - `RESEARCH_METHODOLOGY`: `1.05x` (EPV `PMC8570314`, Karun Singh xT, ML-KULeuven SoccerAction VAEP/SPADL, Friends of Tracking Pitch Control, Temporal Occlusion / BKT `PMC9686440`)
   - `TACTICAL_HYPOTHESIS`: `0.75x`
   - `COMMUNITY_OBSERVATION`: `0.70x`

---

## 2. Corpus Coverage Categories

- **FC IQ & Player Roles:** 37 outfield roles (`Falseback`, `Wingback`, `Holding`, `Deep-Lying Playmaker`, `Box-to-Box`, `Playmaker`, `Shadow Striker`) and Familiarity tiers (`Base`, `Role+`, `Role++`).
- **PlayStyles & Caps:** 36 PlayStyles across 6 groups + FC27 Ultimate Team 3-PlayStyle+ cap (`KB-EA-PLAYSTYLES-002`) vs FC26 responsive passing mechanics (`KB-EA-PLAYSTYLES-FC26-002B`).
- **Passing, Shooting & Defending Mechanics:** Manual jockeying vs reduced AI auto-intercept (`KB-EA-DEFENDING-003`), Finesse/Driven passes & Composure under pressure (`KB-EA-SHOOTING-PASSING-004B`).
- **Squad Building & Chemistry:** Position/GK/uniqueness constraints and verified Club/League/Nation chemistry link provenance rules (`KB-EA-CHEMISTRY-SQUAD-004C`).
- **Formations & Rest Defense:** Double-pivot stability vs single-pivot shapes (`4-2-3-1`, `4-3-3`, `4-4-2`, `4-2-2-2`, `4-1-2-1-2`, `3-5-2`).
- **Modes, Controls & Compliance:** Competitive vs Authentic gameplay tuning (`KB-EA-PRESETS-004`), Practice Arena & camera height effects (`KB-EA-TRAINING-005`), and post-match-only anti-automation compliance (`KB-EA-RULES-006`).

**Free Embedding Consideration:** OpenRouter free-model catalog discovery confirmed no dedicated free zero-price Nemotron embedding/reranker endpoint is currently listed in `/api/v1/models`; calibrated Okapi BM25 delivers deterministic sub-2ms retrieval with `$0.0` inference overhead and exact source citations.
