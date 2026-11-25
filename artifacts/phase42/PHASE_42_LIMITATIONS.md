# Phase 42 Honest Limitations & Known Gaps

1. **No Offline Annotated EA FC Dataset or Trained ONNX Weights (`backend/models/fc_detector.onnx`):**
   - `backend/models/fc_detector.onnx` is absent offline (`weights_present=[]`, `status="NO_TRAINED_WEIGHTS_PRESENT"`) because neither human-annotated EA FC broadcast player/ball datasets nor offline PyTorch/CUDA training dependencies (`torch`, `torchvision`, `onnxruntime`, `ultralytics`) are installed in the runtime environment. Active video ingestion runs `CV_CLASSICAL_HSV_CONTOUR`, and proxy metrics (`player_ap50=0.8758`, `ball_recall=0.6667`, `IDF1=0.9339`, `HOTA=0.9360`) come from a calibrated synthetic geometric pitch sequence (`SYNTHETIC_CALIBRATED_GEOMETRY_PROXY`), not labeled real EA FC footage.
2. **Upstream Free-Tier Provider Capacity Variance:**
   - During live `FC_COACH_BENCH_V2` testing on 2026-11-25, Google's `gemini-4-hydrogen` and `gemini-3.8-flash` endpoints returned intermittent `HTTP 503 UNAVAILABLE` high-demand errors and OpenRouter's `openrouter/free` returned `HTTP 429` before failing over cleanly to `nvidia/nemotron-3.5-lightning:free` (`11.77s–17.20s` total, `8.29s–9.36s` TTFT) or tripping circuit breakers to `deterministic-coach`.
3. **Deterministic Intent Nuance on Unmatched Search Context:**
   - When external LLMs are disabled or unavailable on cold-start accounts with zero matches, `PersonalCoachOrchestrator` uses keyword matching (`recommend`, `find`) and falls back to honest cold-start Gamer DNA guidance on generic phrasing inside `Search` (`543ms` in Playwright QA) unless explicit filter parameters are explicitly bound.
4. **Local Staging Table Debt (`test_zero_budget_research.py`):**
   - One pre-existing check (`test_pinned_card_items_end_to_end`) remains failing (`HTTP 503` vs `422`) because `fc27_staging.observation` from Migration `012` is absent in the local PostgreSQL schema (`fc27_staging.source_row` holds `9,962` rows from `009`).
5. **Single-Process Quota Default & Non-Causal Observational Deltas:**
   - `QuotaManager` uses in-process locks unless `REDIS_URL` points to an active Redis instance (`RedisQuotaBackend`). Practice BKT accuracy (`practice_only=True`) and closed-loop `weakness_loop_tracking` remain observational hypotheses subject to patch, formation, and opponent-strength confounding (`causal_disclaimer` enforced).
