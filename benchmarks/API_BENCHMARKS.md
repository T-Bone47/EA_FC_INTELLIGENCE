# API Benchmarks — POST /api/recommendations

Measured 2026-09-13 against the running dev server (uvicorn, 1 worker, same host),
PostgreSQL 17 local, 16,228 FC26 game_players. Client: python urllib, 7 sequential
requests per scenario (first = cold candidate cache, rest = warm, TTL cache hit).

| Scenario | Evaluated | Cold (ms) | Warm p50 (ms) | Warm min | Warm max | Best result |
|---|---|---|---|---|---|---|
| CM / 4-2-3-1 / PRESSING / stamina≥85 / budget 100k / limit 10 | 10,275 | 1483.9 | 674.5 | 562.8 | 682.8 | Federico Valverde 0.95789 |
| ST plain, limit 10 | 5,241 | 315.6 | 318.5 | 312.1 | 440.5 | Kylian Mbappé 0.9486 |
| GK plain, limit 10 | 1,816 | 100.8 | 107.1 | 104.3 | 199.9 | Alisson 0.9213 |
| No position (full pool), limit 10 | 16,228 | 938.9 | 982.0 | 919.9 | 1074.3 | Kylian Mbappé 0.93146 |

Notes:
- Cold vs warm: the first CM-scenario request pays candidate-pool load + playstyle
  joins (~1.48s). Subsequent requests reuse the CandidateRepository TTL cache
  (watermark-invalidated), settling ~0.56–0.68s for 10k evaluations.
- Scoring is fully deterministic: repeated identical requests returned identical
  rankings and scores (asserted in `test_recommendation_deterministic`).
- No-position full-pool evaluation of all 16,228 players completes in ~1s warm —
  acceptable for an on-demand API; if traffic grows, the ranking loop is the
  obvious target (numpy vectorization), not the SQL.
- Earlier cold-start measurement (first ever request, empty pool): 1370ms for the
  same CM scenario — consistent with the cold figure above.

## Endpoint sanity (same run)
- GET /api/health: 200, <5ms (no DB).
- GET /api/health/ready: 200, reports real counts (16,228 players / 15,032 playstyle links).
- GET /api/players?q=…: paginated, index-backed; p50 <30ms warm.

## Method
Reproduce with the server running on :8000 (see `deploy/`):

    python3 - <<'EOF'  # or re-run the scenario block from the session log
    # posts each scenario 7×, drops the first sample as cold, reports p50/min/max
    EOF

Baseline preserved: engine V2 micro-benchmarks live in
`backend/tests/test_recommendation_engine_v2_evaluation.py` (32 deterministic
regression tests, no timing assertions — timing belongs here, correctness there).

## Re-audit 2026-09-14 (post-build verification, live)

Re-measured against the running production server (ENVIRONMENT=production, uvicorn
1 worker, PostgreSQL 17, same host). Full machine-readable results:
`benchmarks/reaudit_2026-09-14.json`.

| Scenario | Evaluated | Cold/first-hit (ms) | Warm p50 (ms) | Best result (identical to baseline) |
|---|---|---|---|---|
| CM / 4-2-3-1 / PRESSING / stamina≥85 / budget 100k | 10,275 | 1256.9 (true cold, fresh process) | 494.4–581.1 | Federico Valverde 0.95789 |
| ST plain | 5,241 | 375.6 (first hit) / 236.7 (warm-cache run) | 264.5 | Kylian Mbappé 0.9486 |
| GK plain | 1,816 | 78.8–85.3 | 83.0 | Alisson 0.9213 |
| Full pool (no position) | 16,228 | 766.7–728.9 | 748.8 | Kylian Mbappé 0.93146 |

Memory (RSS of uvicorn process): 65.0 MB idle at boot → 186.1 MB after cold CM
request → 574.5 MB after the full 4×7 benchmark sweep (pool + caches fully warm).
All winners, scores and evaluated counts reproduce the original baseline exactly —
determinism claim re-verified. Warm p50s came in at or better than baseline.
