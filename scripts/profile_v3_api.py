"""Where does a /api/v3/recommendations request spend its time?  (measure only; no optimisation)

    python scripts/profile_v3_api.py --out artifacts/phase24/PHASE_24_API_RESULTS.json
"""
import argparse
import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api.schemas_v3 import RecommendationRequestV3
from backend.services.recommendation_engine_v3 import ENGINE_VERSION
from backend.services.recommendation_service_v3 import (
    RecommendationServiceV3,
    _to_user_requirements,
)
from backend.services.v3_config import DEFAULT_V3_CONFIG


def profile(game_version: str, position: str, repeats: int = 3, tactical_profile: str = "BALANCED") -> dict:
    """Median ms per stage, using the same service calls recommend() makes."""
    svc = RecommendationServiceV3()
    body = RecommendationRequestV3(game_version=game_version, position=position, tactical_profile=tactical_profile,
                                   limit=10, include_research_data=(game_version == "FC27"))
    runs = []
    for _ in range(repeats):
        t0 = time.perf_counter(); ref, research = svc._resolve(body); pool = svc._pool(body, research)
        t1 = time.perf_counter(); result = svc._engine(body, ref).recommend(pool, _to_user_requirements(body))
        t2 = time.perf_counter(); svc._serialise(result, body, pool, ref, research, uuid.uuid4(), time.monotonic())
        t3 = time.perf_counter(); runs.append((t1 - t0, t2 - t1, t3 - t2, t3 - t0))
    med = lambda i: round(statistics.median(r[i] for r in runs) * 1000, 1)
    return {"db_load_ms": med(0), "engine_ms": med(1), "serialise_ms": med(2), "total_ms": med(3),
            "n_candidates": len(pool), "repeats": repeats}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out"); a = ap.parse_args()
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "engine_version": ENGINE_VERSION,
           "config_version": DEFAULT_V3_CONFIG.config_version, "load_avg_1m": os.getloadavg()[0],
           "note": "single shared CPU sandbox; relative stage shares matter, absolute ms do not transfer",
           "profiles": {f"{gv}:{pos}": profile(gv, pos) for gv in ("FC26", "FC27") for pos in ("CM", "GK")}}
    text = json.dumps(out, indent=2)
    Path(a.out).write_text(text, encoding="utf-8") if a.out else print(text)
