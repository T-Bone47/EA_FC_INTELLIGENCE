#!/usr/bin/env python3
"""ENGINE v2.1 PERFORMANCE BENCHMARK (§57).

Measures cold/warm latency and pool-size scaling for the upgraded engine,
legacy mode vs full intelligence mode. Results -> benchmarks/engine_v21_perf.json.
Correctness first: this script never changes scoring, only measures it.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.data_access.candidate_repository import CandidateRepository
from backend.domain.user_model import AttributeBand, UserRequirements
from backend.services.recommendation_engine_v2 import RecommendationEngineV2


def bench(engine, pool, req, runs=3, label=""):
    times = []
    out = None
    for i in range(runs):
        t0 = time.perf_counter()
        out = engine.recommend(pool, req)
        times.append(round((time.perf_counter() - t0) * 1000, 1))
    return {"label": label, "evaluations": out.evaluations_total,
            "cold_ms": times[0], "warm_ms": min(times[1:]),
            "all_ms": times, "best": out.best_evaluation.candidate.name
            if out.best_evaluation else None}


def main():
    repo = CandidateRepository()
    engine = RecommendationEngineV2()
    results = {"timestamp": datetime.now(timezone.utc).isoformat(),
               "engine_version": engine.engine_version, "runs": {}}

    full = repo.load_candidates("FC26")
    cm = repo.load_for_position("FC26", "CM", include_adjacent=True)
    st = repo.load_for_position("FC26", "ST", include_adjacent=True)
    gk = repo.load_for_position("FC26", "GK", include_adjacent=True)
    results["pool_sizes"] = {"full": len(full), "cm": len(cm),
                             "st": len(st), "gk": len(gk)}

    # --- legacy regression scenarios (same shapes as the 2026-09-14 baseline) --
    results["runs"]["legacy_cm_pressing"] = bench(engine, cm, UserRequirements(
        game_version="FC26", position="CM", tactical_profile="PRESSING", limit=10),
        label="CM PRESSING (legacy path)")
    results["runs"]["legacy_st_counter"] = bench(engine, st, UserRequirements(
        game_version="FC26", position="ST", tactical_profile="COUNTER_ATTACK", limit=10),
        label="ST COUNTER_ATTACK (legacy path)")
    results["runs"]["legacy_gk"] = bench(engine, gk, UserRequirements(
        game_version="FC26", position="GK", tactical_profile="LOW_BLOCK", limit=10),
        label="GK LOW_BLOCK (legacy path)")
    results["runs"]["legacy_full_pool"] = bench(engine, full, UserRequirements(
        game_version="FC26", position=None, limit=10), label="full pool (legacy path)",
        runs=2)

    # --- full intelligence mode (every v2.1 layer on) ---------------------------
    intel_req = UserRequirements(
        game_version="FC26", position="CM", formation="4-2-3-1", slot=None,
        tactical_profile="HIGH_PRESS", secondary_tactical_profile="FAST_BUILD_UP",
        archetype="BOX_TO_BOX", required_playstyles=["Intercept"],
        attribute_bands=[AttributeBand("stamina", "excellent"),
                         AttributeBand("short_passing", "very_good")],
        enable_interactions=True, enable_saturation=True,
        enable_playstyle_context=True, overall_quality_bias="normal",
        complement_hint={"position": "CM", "bias": "ATTACKING"}, limit=10)
    results["runs"]["intelligence_cm"] = bench(engine, cm, intel_req,
                                               label="CM full intelligence (all layers)")
    intel_full = UserRequirements(**{**intel_req.__dict__, "position": None,
                                     "required_playstyles": []})
    results["runs"]["intelligence_full_pool"] = bench(
        engine, full, intel_full, label="full pool intelligence", runs=2)
    no_cf = UserRequirements(**{**intel_req.__dict__, "disable_counterfactuals": True})
    results["runs"]["intelligence_cm_no_cf"] = bench(
        engine, cm, no_cf, label="CM intelligence, counterfactuals off")

    # --- pool scaling (§57: 1K / 5K / 10K / 16K) --------------------------------
    scaling = {}
    for size in (1000, 5000, 10000, len(full)):
        sub = full[:size]
        r = bench(engine, sub, UserRequirements(
            game_version="FC26", position=None, tactical_profile="PRESSING",
            limit=10), runs=2, label=f"scaling {size}")
        scaling[size] = r
    results["scaling"] = scaling

    # --- intent parse timing ----------------------------------------------------
    from backend.services.intent_parser import parse
    text = ("Looking for a box-to-box CM for my 4-2-3-1, high press with fast "
            "build-up, good stamina, must have Intercept, under 500000 coins")
    t0 = time.perf_counter()
    for _ in range(100):
        parse(text, "FC26")
    results["intent_parse_ms_per_call"] = round((time.perf_counter() - t0) * 10, 3)

    out_path = ROOT / "benchmarks" / "engine_v21_perf.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
