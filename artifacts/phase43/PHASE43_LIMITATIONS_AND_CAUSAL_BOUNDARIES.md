# Phase 43 Limitations & Causal Boundaries

## 1. Epistemic & Causal Inference Boundaries
- **N-of-1 Observational Confounders:** Match-clustered experiments reduce frame-level autocorrelation error, but amateur gameplay trials remain exposed to opponent skill variance, controller input delay, dynamic matchmaking ELO shifts, and mid-session fatigue. A statistically supported ABBA delta establishes intra-user performance association under controlled alternating arms, **never** universal deterministic proof across all opponents.
- **Theoretical vs Empirical Tagging:** Pre-match counterfactual deltas (`TacticalCounterfactualService`) and cold-start formation rankings remain strictly tagged `THEORETICAL_SUITABILITY`. Predicted rest-defense or progression shifts do not guarantee improved match outcomes.
- **No Global Meta Extrapolation:** `PersonalMetaProfile` describes one user's observed matches on one `game_version` and one `game_patch`. It never alters frozen V3.2.1 player evaluation weights and cannot be generalized across gameplay patches.

## 2. Telemetry, Vision & Environment Boundaries
- **Absence of Trained Broadcast Detector (`fc_detector.onnx`):** Neither `torch`, `onnxruntime`, nor trained detector weights (`backend/models/fc_detector.onnx`) exist in the local environment. Live video processing runs via `CV_CLASSICAL_HSV_CONTOUR` (`79.5%–80.3%` coverage on verified `960x540` test clips), while quantitative AP/IDF1/HOTA/ECE numbers (`mAP50=0.7712`, `ECE=0.0817`) are strictly `SYNTHETIC_CALIBRATED_GEOMETRY_PROXY` values rather than human-labeled broadcast benchmarks.
- **Market Pricing Unavailable:** Live EA FC transfer market pricing is absent (`MARKET_PRICE_UNAVAILABLE`), preventing automated coin-per-performance ROI calculations in `ReplacementExperimentService`.
- **Role Familiarity Metadata:** Saved squad imports default missing FC IQ familiarity tiers to `UNKNOWN` unless supplied explicitly by the gamer.
- **Pre-Existing Infrastructure Items:**
  - `JWT_SECRET` and `REDIS_URL` remain unset in the local development shell (producing ephemeral JWT secret warnings and per-process quota tracking).
  - External free-tier LLMs (`gemini-*`, `openrouter/free`) remain subject to upstream `503`/`429` volatility, mitigated via bounded deadlines and deterministic fallback rather than guaranteed upstream availability.
  - Queries containing `"Compare ..."` inside `TACTICAL_LAB` currently classify as `PLAYER_COMPARISON` before tactical-experiment comparison; explicitly prioritizing `TACTICAL_LAB` route hints when `experiment_id` is present will tighten Co-Pilot focus further in a future iteration.
