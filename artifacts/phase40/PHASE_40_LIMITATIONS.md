# PHASE 40: Known Limitations & Epistemic Boundaries

1. **No Pre-Trained EA FC YOLOX Detector Weights (`backend/models/fc_detector.onnx`):** Player/ball detection currently executes classical HSV turf subtraction + morphological silhouettes + `KMeans` jersey clustering (`onnx_weights_loaded = false`), which degrades on heavy stadium shadows or pitchside color clashes relative to a fine-tuned detector.
2. **Absence of Unedited Owner Retail Captures:** While PyAV decoding and `IMPORTED_MATCH_TRACE` ingestion work end-to-end, live empirical model accuracy on multi-match retail FC26/FC27 Division Rivals/Champions uploads has not yet been measured.
3. **Uncalibrated Heuristic Coefficients (`PersonalGameplayFit` & `DecisionReviewService`):** Weighting (`0.50/0.18/0.17/0.15`) and pre-action `Q_heuristic` values are explicitly disclosed heuristics rather than empirically fitted scoring/conceding probabilities.
4. **Live Market Prices & Chemistry Unavailability:** `market_price_status` explicitly returns `MARKET_PRICE_UNAVAILABLE` when verified transfer market observations are missing; unverified squad chemistry stays `INSUFFICIENT_EVIDENCE` rather than fabricating numeric scores.
5. **Experimental BKT Mastery:** Training Academy exercises update `ExperimentalBKTState` locally, but longitudinal transfer to actual competitive match win rates requires Phase 41+ follow-up testing.
6. **Gated Pro Gamer Matching (40L):** Named pro-player comparison percentages remain disabled until licensed reference telemetry exists.
