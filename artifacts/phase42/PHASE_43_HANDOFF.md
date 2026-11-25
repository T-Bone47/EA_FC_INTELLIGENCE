# Phase 43 Engineering Handoff

## Recommended Next Priorities
1. **Curate & Train Annotated EA FC CV Dataset -> `backend/models/fc_detector.onnx`:**
   - Collect diverse broadcast frames across EA FC cameras (`TELE_BROADCAST`, `COOP`, `TACTICAL`), annotate with `EA_FC_CLASSES` (`player`, `goalkeeper`, `referee`, `ball`, `minimap_roi`), verify via `backend/cv_training/manifest.py` + `split_by_match_group()`, train YOLOX-S (`Apache-2.0`, `batch=4`, `--fp16` on RTX 3050 4GB), export opset 12 ONNX into `backend/models/fc_detector.onnx` + `.meta.json`, and run `python -m backend.cv_training.benchmark_cv` to measure genuine broadcast `AP@50`, ball recall, IDF1, HOTA, and OpenCL DNN FPS.
2. **Route-Aware Deterministic Search Binding in Co-Pilot:**
   - When `verified_ctx['source_route'] == 'PLAYER_DISCOVERY'` and `active_filters` are populated inside `CoachContextEnvelope`, pass those active filters automatically into `search_player_cards` even in deterministic offline mode.
3. **Reconcile Migration `012` (`fc27_staging.observation`):**
   - Guard `CREATE SCHEMA IF NOT EXISTS fc27_staging` in `012_fc27_evidence_staging.sql` and apply cleanly to resolve the final `503` failure in `test_zero_budget_research.py`.
4. **External Redacted Screenshot VLM Live Evaluation:**
   - Once real EA FC formation/tactical screenshots are approved for opt-in free-tier vision evaluation, extend `verification/benchmark_fc_coach_v2.py` with live vision precision/refusal tests (`CANDIDATE_MULTIMODAL_OBSERVATION_UNVERIFIED` vs hallucinated player names).
5. **Provision Shared Redis (`REDIS_URL`) & Production `JWT_SECRET`:**
   - Configure both environment variables in staging/production so uvicorn workers share `QuotaManager` windows cleanly and ephem-secret warnings disappear.
