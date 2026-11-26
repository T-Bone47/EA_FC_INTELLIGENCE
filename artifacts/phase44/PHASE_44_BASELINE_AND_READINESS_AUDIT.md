# Phase 44 Baseline & Readiness Audit

## 1. Repository & Service Checkpoint
- **GitHub Sync State:** `origin/main` at commit `014d8d4` (`docs: update architecture, benchmarks, changelog and Phase 42 release documentation`); local uncommitted Phase 43 complete build cleanly integrated in workspace.
- **Database State:** PostgreSQL 16.16 running on `127.0.0.1:5432`, migrations `001` through `020_phase43_complete_experiment_lab.sql` applied.
- **Local Web Stack:** FastAPI/Uvicorn (`127.0.0.1:8010`) + Vite (`http://localhost:5173`, proxying `/api` to `:8010` cleanly avoiding local port `8000` conflict with external service).

## 2. Live Database & Asset Counts (Observed Before Phase 44)
- `public.phase40_match_record`: `73` rows (`73` non-synthetic, `0` synthetic stored)
- `public.phase41_decision_opportunity`: `168` non-synthetic rows
- `public.phase43_tactical_fingerprint`: `3` rows
- `public.phase43_experiment`: `2` rows
- `public.game_player`: `36,017` canonical footballers (`FC26` + `FC27`)
- `public.ut_card`: `60` UT cards
- `data/video_research/uploads/`: `31` `.mp4` files scanned; Phase 43 CV benchmark verified `2` valid playable clips (`~79.5%–80.3%` coverage via `CV_CLASSICAL_HSV_CONTOUR`) and `27` corrupt/test stubs.
- `backend/models/`: `MISSING` (no trained ONNX neural detector weights present).

## 3. Offline Python ML Runtime Inventory (Observed)
- **Installed:** `numpy`, `scipy`, `scikit-learn`, `pandas`, `opencv` (`cv2`), `pyav` (`av`).
- **Not Installed:** `umap`, `hdbscan`, `metric_learn`, `torch`, `onnxruntime`.
- *Engineering Implication:* All PCA, K-Means, GMM, Hierarchical clustering, Ledoit-Wolf shrinkage Mahalanobis, Weighted Euclidean, Cosine, Jensen-Shannon, Wasserstein, and GroupKFold evaluation run cleanly using `numpy`, `scipy`, and `scikit-learn` without unverified optional dependencies.

## 4. Prerequisite Blockers Assessed (Honest Status)
1. **No Authorized External Pro Reference Gameplay Dataset:** `0` authorized external FC Pro match telemetry/video datasets exist locally. All candidate pro profiles must enter strict `METADATA_ONLY` / `AWAITING_PERMISSION` governance (`Fail Closed` on unknown rights); engine abstains from named pro ranking rather than fabricating pro stats.
2. **Missing Domain-Trained Neural CV Weights:** `backend/models/fc_detector.onnx` does not exist; runtime remains `NO_TRAINED_WEIGHTS_PRESENT` with classical `CV_CLASSICAL_HSV_CONTOUR` + ByteTrack active fallback.
3. **Human-Annotated Broadcast vs Minimap Footage Shortage:** Insufficient labeled human match frames to train commercial ONNX detector weights locally on 4GB RTX 3050.
4. **Frozen V3.2.1 & Edition Walls:** Preserved untouched (`13` known legacy Phase 7 / empirical V3 threshold failures remain unmodified baseline).
