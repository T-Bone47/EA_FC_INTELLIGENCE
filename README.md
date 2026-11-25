# EA FC Intelligence

> **PLAYER QUALITY ≠ PLAYER SUITABILITY**
>
> **Our engine calculates. The LLM retrieves, reasons and explains. Validated evidence remains the source of truth.**

EA FC Intelligence is a full-stack tactical analysis, squad optimization, gameplay computer vision, and evidence-grounded AI coaching platform built for **EA SPORTS FC** (`FC26` and `FC27`). Rather than ranking players by surface OVR or delegating match math to unconstrained generative models, deterministic football engines evaluate role fit, tactical geometry, whole-XI cohesion, counterfactual regret, and longitudinal gamer habits—using free-tier LLMs strictly for verified tool synthesis and explanation.

---

## Implemented vs Experimental vs Planned

| Capability | Status | Truthful Scope & Notes |
| :--- | :--- | :--- |
| **Frozen V3.2.1 Player Recommendation Engine** | **Implemented & Frozen** | Deterministic multi-factor scoring (`overall_quality`, `position_fit`, `attribute_fit`, `tactical_fit`, `playstyle_fit`, `team_fit`), FC26/FC27 strict isolation, Pareto trade-offs, verified via `test_golden_fixtures_v3_2.py`. |
| **Player Discovery, Compare & Squad Lab** | **Implemented** | Multi-slot 11-player lineup solver, Partnership Intelligence, Whole-XI channel cohesion, tactical friction rules, confirmation-gated edits (`Confirm` / `Rollback`). |
| **Hybrid Agentic AI Coach (Gemini + OpenRouter Free)** | **Implemented** | 77+ registered typed football tool handlers, Okapi BM25 knowledge RAG, fail-fast timeouts (`14s`/`16s`), per-`(provider, model)` circuit breakers, streaming SSE & cancellation, deterministic offline fallback. |
| **Universal Context-Aware Co-Pilot & Memory** | **Implemented** | Cross-route slide-over drawer (`Ctrl+Shift+C`) passing server-authorized `CoachContextEnvelope`, persistent `/coach/preferences`, rolling summaries, live DB freshness markers, opt-in `REDIS_URL` shared quota. |
| **Decision Intelligence & Counterfactual Replay Lab** | **Implemented** | Pre-action state construction with strict hindsight stripping, Karun Singh expected threat (xT), dynamic interception margins, bounded Monte Carlo uncertainty, Football IQ scoring. |
| **Adaptive 8-Category Training & Closed-Loop Progression** | **Implemented (Practice Experimental)** | Blind-review freeze-frame challenges linked to Phase 41 Decision Windows (`hide_outcome_by_default=True`), bounded BKT practice estimates (`practice_only=True`), covariate-stratified observational progression. |
| **Multimodal Screenshot Redaction & Opt-In Gate** | **Implemented (Candidate Unverified)** | In-browser `<canvas>` PII black-box masking + EXIF stripping, separate media consent gate, hard server isolation (`CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED`). |
| **Gameplay Video Ingestion & Classical CV Pipeline** | **Implemented (Baseline)** | PyAV container decoding, scene filtering, DLT/RANSAC pitch homography, ByteTrack association, **currently running `CV_CLASSICAL_HSV_CONTOUR`** with `RETR_EXTERNAL` filled turf contours (`79.5%–80.3%` coverage on 960×540 test clips). |
| **Domain YOLOX / ONNX Gameplay Object Detector** | **Scaffolded / Awaiting Training** | Reproducible dataset manifest, leakage-free match splitter, commercial-safe Apache-2.0 YOLOX recipe, HOTA/IDF1/AP@50 evaluator, OpenCV DNN inference hook (`_detect_with_onnx`). **Trained `backend/models/fc_detector.onnx` weights are NOT bundled offline.** |
| **Pro Gamer Telemetry Benchmarking (`build_pro_dna_preview`)** | **Feature-Gated / Planned** | Uses generic tactical archetypes only; named pro comparisons remain blocked pending licensed esports telemetry. |

---

## Core Architecture

```
+-----------------------------------------------------------------------------+
|                    Frontend Workspace — React 18 / Vite / Stadium 3.0        |
|  Discover (/search) · Players (/players/:id) · Compare · Squad Lab          |
|  Gameplay Studio · Decision Replay Lab · Personal Coach & Academy           |
|  Global Co-Pilot Drawer (Ctrl+Shift+C) + Local <canvas> PII Redactor        |
+---------------------------------------+-------------------------------------+
                                        | Relative API + SSE (/api/phase40/*)
                                        v
+-----------------------------------------------------------------------------+
|                        FastAPI Application (Python)                         |
|  Auth (JWT/bcrypt) · Rate Limits · Context Envelope Ownership Validator     |
+-----------------------+-------------------------------+---------------------+
                        |                               |
          +-------------v-------------+     +-----------v------------+
          | Deterministic Engines     |     | Hybrid Coach Router    |
          | - Frozen V3.2.1 Suitab.   |     | - Gemini Free (14s)    |
          | - Squad & Partnership     |     | - OpenRouter Free (16s)|
          | - Counterfactual & xT     |     | - Per-Model Breakers   |
          | - Gamer DNA & Football IQ |     | - 77+ Typed Tools      |
          | - 8-Cat Training & BKT    |     | - Okapi BM25 RAG       |
          | - PyAV / OpenCV / DLT CV  |     | - Deterministic Fallback|
          +-------------+-------------+     +-----------+------------+
                        |                               |
          +-------------v-------------------------------v------------+
          | PostgreSQL 16 (Migrations 002–018) + Optional Redis Quota |
          +-----------------------------------------------------------+
```

For full architectural details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Visual Tour (Stadium 3.0 UI)

| Personal Coach & Sessions | Universal Contextual Co-Pilot Drawer |
| :---: | :---: |
| ![Personal Coach Workspace](docs/assets/coach-workspace.png) | ![Co-Pilot Drawer](docs/assets/copilot-drawer.png) |
| **8-Category Adaptive Training Academy** | **In-Browser Screenshot PII Redactor** |
| ![Training Academy](docs/assets/training-academy.png) | ![Screenshot Redactor](docs/assets/screenshot-redactor.png) |

---

## Technology Stack

- **Backend:** Python, FastAPI, Uvicorn, Pydantic v2, PostgreSQL 16 (`psycopg[binary]`, `psycopg_pool`), PyJWT, bcrypt, `httpx`, `google-genai`, optional `redis`.
- **Recommendation & Analytics:** NumPy, Pandas, SciPy (`linear_sum_assignment`), scikit-learn (`KMeans`), custom deterministic V3.2.1 math, Karun Singh xT grids, Experimental Bayesian Knowledge Tracing (BKT).
- **Computer Vision:** OpenCV (`cv2`), PyAV (`av`), optical-flow camera compensation, DLT/RANSAC homography, ByteTrack two-stage IoU/Kalman association, `backend/cv_training/` evaluation & YOLOX Apache-2.0 export harness.
- **Frontend:** React 18, TypeScript, Vite 5, React Router, Stadium 3.0 Obsidian/Lime CSS design system ([DESIGN.md](DESIGN.md)).
- **Quality & Browser QA:** `pytest`, `vitest`, Testing Library, `tsc`, Playwright (headless Chrome/Chromium), `puppeteer-core` + `axe-core` CI suite.

---

## Core Modules & Methodology

### 1. Frozen V3.2.1 Player Recommendation Engine & Squad Intelligence
- Scores players using explicit component decomposition rather than black-box neural weights:
  `overall_quality (0.15)`, `attribute_fit (0.30)`, `position_fit (0.15)`, `tactical_fit (0.15)`, `playstyle_fit (0.15)`, `team_fit (0.10)`.
- Preserves strict **FC26 vs FC27 data separation** (version wall + opt-in local research flags).
- Evaluates 11-player formations, partnership chemistry/style balance, whole-XI channel balance (`LEFT_FLANK`, `CENTRAL_SPINE`, `RIGHT_FLANK`), and confirmation-gated squad swaps.

### 2. Gameplay Computer Vision & Spatial Intelligence
- Decodes local match clips (`.mp4`, `.mov`, `.mkv`) via `PyAV` and classifies active gameplay vs menus/replays before running pitch homography (`GOOD` / `COARSE` / `REJECTED`).
- Runs `CV_CLASSICAL_HSV_CONTOUR` (`cv2.RETR_EXTERNAL` filled turf contours + `KMeans` jersey clustering + ball velocity gating + ByteTrack) with automatic ONNX DNN dispatch when `backend/models/fc_detector.onnx` is supplied.
- **Honest Metrics Caveat:** Real clip benchmark coverage reaches `79.5%–80.3%` on `960x540` test MP4s (`6.98–14.25 FPS`); quantitative proxy accuracy (`player_ap50=0.8758`, `ball_recall=0.6667`, `IDF1=0.9339`, `HOTA=0.9360`, pitch `RMSE=0.331 m`) comes from a calibrated synthetic geometry sequence (`SYNTHETIC_CALIBRATED_GEOMETRY_PROXY`), **not** human-annotated EA FC broadcast ground truth.

### 3. Decision Intelligence, Gamer DNA & Adaptive Training
- Extracts pre-action Decision Windows (`strip_hindsight` enforced) scoring available pass/carry/shoot/defend options using dynamic passing corridor clearance, interception timing margins, Markov xT deltas, and defensive cover before outcomes happen.
- Connects top-regret Decision Windows directly into blind-review challenges across **8 tactical categories** (`PASSING_SELECTION`, `PRESSING_TIMING`, `CB_SWITCHING_DISCIPLINE`, `REST_DEFENSE`, `TRANSITION_REACTION`, `FINISHING_SHOT_SELECTION`, `WING_OVERLOAD_VS_SWITCH`, `CONSERVATIVE_BALL_RETENTION`), updating `practice_only=True` BKT mastery and covariate-stratified closed-loop progression tables (`weakness -> drill -> subsequent matches`).

### 4. Hybrid Free-Only AI Coach & Context-Aware Co-Pilot
- Uses **only free-tier Gemini (`GEMINI_API_KEY`) and OpenRouter (`OPENROUTER_API_KEY`) APIs** (`AI_COACH_FREE_ONLY=true`, `AI_COACH_ALLOW_PAID_USAGE=false`) backed by deterministic offline fallbacks.
- Injects validated route context (`CoachContextEnvelope`) from whichever workspace the user is viewing without trusting client-supplied IDs without ownership verification.

---

## Quick Start & Installation

### Prerequisites
- Python `3.12+` (verified locally on `3.15.1` and CI on `3.12`)
- Node.js `20+` / `22+`
- PostgreSQL `16`
- Optional: Redis (for shared multi-worker rate limiting)

### 1. Environment Configuration
```bash
cp .env.example .env
# Edit .env locally: set JWT_SECRET, DATABASE_URL, and optional free Gemini/OpenRouter keys.
```
Never commit `.env` or expose keys in client configuration.

### 2. Backend Setup & Database Migrations (`002`–`018`)
```bash
pip install -r backend/requirements.txt

# Create schema, run all migrations 002..018 cleanly & idempotently, and seed reference data
DATABASE_URL=postgresql://eafc:eafc_dev_only@localhost:5432/eafc_intelligence \
  python scripts/setup_database.py
```

*(Optional FC26 foundation / FC27 research ingestion scripts reside under `scripts/ingest_*.py`.)*

### 3. Run Backend & Frontend
```bash
# Terminal 1 — FastAPI API server on :8000
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — React + Vite frontend on :5173 (proxies /api -> :8000)
cd frontend
npm install
npm run dev
```

---

## Testing & Verification Commands

```bash
# Backend Phase 40–42, Golden V3.2.1 & Security regression suite
pytest -p no:cacheprovider -q \
  backend/tests/test_phase42_copilot_cv_training.py \
  backend/tests/test_phase41_5_agentic_coach.py \
  backend/tests/test_phase41_e2e_coach_squad.py \
  backend/tests/test_phase40_coach_and_knowledge.py \
  backend/tests/test_phase40_fit_squad_decision_training.py \
  backend/tests/test_golden_fixtures_v3_2.py \
  backend/tests/test_security.py

# Production integration checks
pytest -p no:cacheprovider -q backend/tests/test_integration_production.py

# Frontend TypeScript check, production bundle & Vitest unit suite
cd frontend
npx tsc --noEmit
npm run build
npx vitest run --run

# CV harness benchmark (hardware probe, local MP4 test clips, calibrated geometry proxy)
python -m backend.cv_training.benchmark_cv

# Hybrid AI Coach live/offline provider benchmark (reads .env securely, never prints keys)
python verification/benchmark_fc_coach_v2.py
```

---

## Fair Play, Privacy & Known Limitations
- **Privacy & Security (`docs/SECURITY.md`):** Strict multi-user IDOR enforcement on squads, matches, decision windows, and conversations; EXIF-stripped local screenshot masking with separate opt-in checkboxes; prompt/SQL injection guards.
- **No Anti-Cheat / Client Injection:** Does not hook live EA FC memory/processes or bypass anti-cheat/DRM protections; gameplay analysis operates strictly on user-uploaded recordings or traces.
- **Known Limitations (`docs/KNOWN_LIMITATIONS.md`):** No offline trained `fc_detector.onnx` weights bundled yet; upstream free-tier Gemini (`503`) / OpenRouter (`429`) capacity fluctuations; one pre-existing `test_zero_budget_research.py` (`test_pinned_card_items_end_to_end`) failure on DBs lacking `fc27_staging.observation`; and intentionally preserved legacy V2/diagnostic tests (`test_engine_adversarial_phase7.py`, `test_engine_v3_real_data.py`).

---

## Research References & Further Documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — System topology, frozen V3.2.1 math, CV & Agentic Co-Pilot pipeline.
- [CHANGELOG.md](CHANGELOG.md) — Release history from Phase 7 through Phase 42.
- [ROADMAP.md](docs/ROADMAP.md) — Completed phases, active boundaries, and Phase 43 planned next steps.
- [SECURITY.md](docs/SECURITY.md) — Privacy controls, redaction boundary, and secret hygiene.
- [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) — Full inventory of documented engineering and data constraints.
- Phase 42 detailed engineering reports & raw benchmarks in [artifacts/phase42/](artifacts/phase42/PHASE_42_IMPLEMENTATION_REPORT.md) and the 23-entry curated research source catalog in `backend/services/football_knowledge_service.py` (`RESEARCH_SOURCE_REGISTRY`).
