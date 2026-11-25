# PHASE 40: Unified System Architecture

## 1. End-to-End Closed-Loop Pipeline

```mermaid
flowchart LR
    V["MP4/MOV/WebM or Imported Trace (Phase 39)"] --> Repo["MatchIntelligenceRepository (40B · PG + Snapshot)"]
    Repo --> Firewall{"Epistemic Provenance Gate"}
    Firewall -- "SYNTHETIC_FIXTURE" --> PreviewOnly["UI / Test Preview Only (Quarantined)"]
    Firewall -- "REAL_VIDEO / IMPORTED_TRACE / MANUAL" --> DNA["Gamer DNA Engine (40C)"]
    Firewall -- "REAL_VIDEO / IMPORTED_TRACE / MANUAL" --> Mistakes["Recurring Mistake Analyzer (40D)"]
    Repo --> Decision["Pre-Action Decision Review (40I)"]
    DNA & Mistakes --> Train["Training Academy + BKT (40J)"]
    DNA & Mistakes --> Fit["PersonalGameplayFit & Squad Lab (40G/H)"]
    V321["Frozen V3.2.1 Suitability Baseline"] --> Fit
    KB["Versioned EA FC Knowledge Base (40F)"] --> Tools
    DNA & Mistakes & Repo & Fit & Train & Decision --> Tools["22 Bounded Coach Tools (40E)"]
    Tools --> Coach["PersonalCoachOrchestrator (OWASP Guardrails + Deterministic/Optional LLM)"]
    Coach --> UI["/coach & /cards/squad-lab & /research/gameplay-studio"]
```

## 2. Persistence Schema (`db/migrations/015_phase40_coaching_intelligence.sql`)

Nine PostgreSQL tables in `public` schema strictly foreign-keyed to `public.user_profile(id) ON DELETE CASCADE`, reversible via `db/migrations/rollback/015_phase40_coaching_intelligence_down.sql`:
- `phase40_match_squad_snapshot`: Immutable point-in-time XI snapshots (formation, roles, attributes, SHA-256).
- `phase40_match_record`: Versioned match storage supporting duplicate SHA-256 guards, partial matches, telemetry metrics, events, coaching findings, and clip deep-links.
- `phase40_gamer_profile`: Persistent self-reported cold-start preferences + observed Gamer DNA cache.
- `phase40_recurring_mistake`: Normalized longitudinal mistake patterns & hypotheses.
- `phase40_training_plan` & `phase40_training_attempt`: Temporal-occlusion challenges & BKT mastery history.
- `phase40_coach_session` & `phase40_coach_message`: Structured auditable Q&A logs.
- `phase40_knowledge_entry`: Official facts & methodology registry schema.

## 3. Core API Surface (`/api/phase40/*`)

Mounted cleanly in `backend/api/main.py` via `backend/api/routes/phase40_coach.py`:
- `GET /api/phase40/health` & `GET /api/phase40/knowledge`
- `POST /api/phase40/matches`, `POST /api/phase40/matches/from-video/{video_id}`, `GET/DELETE /api/phase40/matches/{id}`, `GET /api/phase40/matches/compare/{a}/{b}`
- `GET /api/phase40/gamer-dna`, `POST /api/phase40/gamer-dna/cold-start`, `GET /api/phase40/recurring-mistakes`
- `POST /api/phase40/coach/ask`, `GET /api/phase40/coach/messages`
- `GET /api/phase40/recommendations/personal-fit`, `POST /api/phase40/squad-intelligence/analyze`
- `POST /api/phase40/decision-review`, `GET /api/phase40/training/plan`, `POST /api/phase40/training/attempt`, `GET /api/phase40/progression`
- `DELETE /api/phase40/privacy/reset` (full user-scoped wipe)
