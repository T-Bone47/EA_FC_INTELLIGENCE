# EA FC Intelligence Roadmap

## Completed Through Phase 42 (Verified Release Checkpoint)
- **Phases 1–7:** Canonical schema, player identity resolution, recommendation engine baseline, API & security hardening.
- **Phases 8–23:** V3.2.1 scoring engine freeze, golden regression contract, data freshness & version wall guards.
- **Phases 24–35:** FC27 quarantined local research layer, Interactive 11-Player Squad Lab, Partnership Intelligence, Whole-XI Cohesion, Stadium 3.0 UI transformation.
- **Phases 36–39:** Gameplay Studio with real `PyAV` decoding, scene classification, DLT/RANSAC homography, ByteTrack tracking, minimap fusion, and evidence review audit logs.
- **Phase 40:** Gamer DNA profiling (Style vs Execution), Recurring Mistake Analyzer, Training Academy (BKT), and deterministic Personal Coach.
- **Phase 41:** Pre-action Decision State Builder, Counterfactual Football Engine, Markov xT & dynamic lane margins, Football IQ, Decision Replay Lab.
- **Phase 41.5:** Hybrid Free-Only Agentic Coach integrating Gemini Free + OpenRouter Free, 77+ typed football tools, Okapi BM25 RAG, SSE streaming/cancellation, confirmation-gated squad edits.
- **Phase 42:** Universal Context-Aware Co-Pilot Drawer, server-authorized `CoachContextEnvelope`, persistent user preferences & rolling summaries, per-model circuit breakers & TTFT telemetry, opt-in Redis quota backend, domain CV training/eval/ONNX harness + contour detection bug fix, local `<canvas>` PII screenshot redactor, 8-category Decision-Window-linked training, closed-loop progression tracking, and authenticated Chrome E2E verification.

---

## Experimental / Calibration Stage
- **Practice BKT Mastery (`practice_only=True`):** Empirically updated on freeze-frame responses with bounded slip/guess priors and Brier evaluation; requires large multi-match longitudinal samples before correlating practice scores to competitive skill ratings.
- **Within-Person Closed-Loop Trends:** Reports covariate strata (patch, formation, mode, squad upgrades, opponent proxy) with mandatory non-causal disclaimers.
- **Pro Archetype Foundation (`FEATURE_GATED_AWAITING_VERIFIED_PRO_DATASET`):** Returns generic tactical archetype similarity until verified esports telemetry is licensed.

---

## Planned Next Work (Phase 43+ — Not Yet Started)
1. **Annotated Broadcast Dataset & Domain `fc_detector.onnx` Weights:** Annotate multi-camera EA FC gameplay footage under `EA_FC_CLASSES`, train Apache-2.0 YOLOX-S on GPU hardware, export opset 12 ONNX into `backend/models/fc_detector.onnx`, and measure real broadcast mAP@50, ball recall, IDF1, and HOTA.
2. **Route Filter Binding for Deterministic Search Co-Pilot:** Pass `active_filters` from `PLAYER_DISCOVERY` directly into `search_player_cards` when running offline without keyword triggers.
3. **Reconcile Local Staging Migration `012`:** Ensure existing local databases cleanly hold `fc27_staging.observation` without conflicting with prior `fc27_staging` schemas.
4. **Live Multimodal VLM Benchmarking:** Evaluate redacted screenshot interpretation precision against human-verified tactical states across free-tier vision models.
5. **Production Multi-Worker Redis & Secret Provisioning:** Deploy managed PostgreSQL 16 + Redis (`REDIS_URL`) + static `JWT_SECRET` in staging/production.
