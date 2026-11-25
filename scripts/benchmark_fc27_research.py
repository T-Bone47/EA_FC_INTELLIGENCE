"""Repeatable isolated V3.2 timing sample against the 19,789-row FC27 universe."""
import argparse
import json
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.schemas_v3 import RecommendationRequestV3
from backend.core.db import close_pool, get_catalogue_conn
from backend.services.recommendation_service_v3 import RecommendationServiceV3, _to_user_requirements


def milliseconds(start):
    return (time.perf_counter() - start) * 1000


def stats(data):
    sorted_values = sorted(data)
    return {"n": len(data), "p50_ms": round(statistics.median(data), 2),
            "p95_ms": round(sorted_values[-1], 2)} if len(data) < 20 else {
                "n": len(data), "p50_ms": round(statistics.median(data), 2),
                "p95_ms": round(statistics.quantiles(data, n=100, method="inclusive")[94], 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    service = RecommendationServiceV3()
    body = RecommendationRequestV3(game_version="FC27", position="CM", formation="4-3-3",
                                  slot="CDM", tactical_profile="HIGH_PRESS", include_research_data=True)
    db_times = []
    for _ in range(20):
        start = time.perf_counter()
        with get_catalogue_conn(local_fc27_research=True) as conn:
            population = conn.execute("SELECT count(*) n FROM game_player WHERE data_status='RESEARCH_ONLY'").fetchone()["n"]
        db_times.append(milliseconds(start))
    if population != 19789:
        raise ValueError("Benchmark requires the complete pinned FC27 release")
    phases = []
    pool_sizes = []
    for i in range(20):
        start = time.perf_counter()
        ref, research = service._resolve(body)
        resolve = milliseconds(start)
        start = time.perf_counter()
        pool = service._pool(body, research)
        load = milliseconds(start)
        cache = service.repository.last_load_stats["cache_hit"]
        start = time.perf_counter()
        result = service._engine(body, ref).recommend(pool, _to_user_requirements(body))
        score = milliseconds(start)
        start = time.perf_counter()
        output = service._serialise(result, body, pool, ref, research, uuid.uuid4(), time.monotonic())
        explain = milliseconds(start)
        start = time.perf_counter()
        data = json.dumps(output, separators=(",", ":")).encode()
        phases.append((resolve, load, score, explain, milliseconds(start), len(data), cache))
        pool_sizes.append(len(pool))

    def concurrent_call(_):
        start = time.perf_counter()
        output = service.recommend(body)
        if "error" in output or not output["ranked"]:
            raise RuntimeError("Concurrent recommendation failed")
        return milliseconds(start)

    with ThreadPoolExecutor(max_workers=4) as threads:
        concurrent = list(threads.map(concurrent_call, range(12)))
    report = {"population": population, "workload": "FC27 4-3-3 CDM high press, both published divisions",
              "position_candidates": sorted(set(pool_sizes)), "cache_hits": sum(row[6] for row in phases),
              "response_size_bytes": max(row[5] for row in phases),
              "first_candidate_load_ms": round(phases[0][1], 2),
              "scope_count": stats(db_times), "concurrent_four_workers": stats(concurrent),
              "warm_timings": {key: stats([row[i] for row in phases[1:]])
                               for i, key in enumerate(("reference", "candidates", "engine",
                                                       "explanation_and_api_assembly", "json_encoding"))},
              "percentiles": "p95 for fewer than 20 samples uses the sample maximum. p99 omitted.",
              "environment": "Isolated loopback PostgreSQL. Timings exclude browser rendering and WAN transfer."}
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
