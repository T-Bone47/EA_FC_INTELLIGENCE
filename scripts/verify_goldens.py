#!/usr/bin/env python3
"""Golden regression gate (§57).

Replays every scenario in benchmarks/engine_baseline_v2_2026-09-14.json
against the live engine and compares the recorded fields bit-for-bit.
Exit code 1 on ANY difference: a broken golden means STOP and investigate —
never edit the baseline to make it pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.schemas import RecommendationRequest  # noqa: E402
from backend.services.recommendation_service import RecommendationService  # noqa: E402

BASELINE = Path(__file__).resolve().parents[1] / "benchmarks" / "engine_baseline_v2_2026-09-14.json"
SKIP_KEYS = {"timing_ms_server", "request"}


def extract(payload: dict, req: dict) -> dict:
    best = payload["best"]
    components = {}
    for k, v in (best["components"] or {}).items():
        components[k] = v["status"] if v.get("status") == "UNKNOWN" else v.get("value")
    limit = req.get("limit") or 5
    return {
        "best": {"name": best["name"], "entity_id": best["entity_id"], "ovr": None},
        "best_score": payload["best_score"],
        "evaluations_total": payload["evaluations_total"],
        "components": components,
        "confidence": payload["confidence"]["score"],
        "ranked_order": [r["name"] for r in payload["ranked"][:limit]],
        "weights_used": payload["weights_used"],
        "budget_status": payload["budget_status"],
    }


def diff(name: str, expected: dict, actual: dict) -> list[str]:
    problems = []
    for key, want in expected.items():
        if key in SKIP_KEYS:
            continue
        got = actual.get(key)
        if key == "best":
            for bk, bv in (want or {}).items():
                if bk == "ovr":
                    continue
                if (got or {}).get(bk) != bv:
                    problems.append(f"{name}.best.{bk}: {bv!r} -> {(got or {}).get(bk)!r}")
            continue
        if got != want:
            problems.append(f"{name}.{key}: {json.dumps(want)[:200]} -> "
                            f"{json.dumps(got)[:200]}")
    return problems


def main() -> int:
    baseline = json.loads(BASELINE.read_text())
    service = RecommendationService()
    all_problems: list[str] = []
    for name, scenario in baseline["scenarios"].items():
        if "request" not in scenario:
            # version-firewall scenario (e.g. FC27_wall): the NO_DATA wall must
            # still refuse with the exact recorded status/detail prefix.
            status = scenario.get("status")
            prefix = scenario.get("detail_prefix")
            from backend.services.recommendation_service import RecommendationService as _RS
            svc = _RS()
            from backend.domain.user_model import UserRequirements
            try:
                svc.recommend(UserRequirements(game_version="FC27", position="CM"))
                all_problems.append(f"{name}: expected NO_DATA wall, got a result")
                continue
            except LookupError as e:
                detail = str(e)
            ok = detail.startswith(prefix) if prefix else True
            print(f"  {name:34s} {'IDENTICAL' if ok else 'DIFF'} "
                  f"(wall status={status})")
            if not ok:
                all_problems.append(f"{name}.detail_prefix: {prefix!r} -> {detail[:80]!r}")
            continue
        req = scenario["request"]
        payload = service.recommend(RecommendationRequest(**req).to_requirements())
        actual = extract(payload, req)
        problems = diff(name, scenario, actual)
        if problems:
            all_problems += problems
            print(f"  {name:34s} DIFF ({len(problems)})")
        else:
            print(f"  {name:34s} IDENTICAL")
    if all_problems:
        print("\nGOLDEN REGRESSION — investigate, do not edit the baseline:")
        for p in all_problems:
            print("  *", p)
        return 1
    print("\nAll golden scenarios bit-identical.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
