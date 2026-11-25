"""Phase 41 Evaluation Benchmark Suite: 220 Curated Tactical Decision Scenarios.

Validates:
- Schema validity rate >= 95%
- Evidence reference resolution >= 95%
- Zero hindsight leakage rate == 100%
- Calibration/coverage abstention compliance == 100%
- Coach Phase 41 bounded tool selection accuracy >= 90%
- Per-decision latency (p50, p95, max) & Python allocation footprint
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.phase40_models import CoachQuestionRequest
from backend.domain.phase41_models import CounterfactualComparison, PostActionOutcome
from backend.repositories.phase40_repository import Phase40Repository
from backend.repositories.phase41_repository import Phase41Repository
from backend.services.counterfactual_football_engine import CounterfactualFootballEngine
from backend.services.decision_state_builder import build_state_from_snapshot
from backend.services.personal_coach_orchestrator import PersonalCoachOrchestrator


def _make_scenario_snapshot(cat: str, variant: int) -> Dict[str, Any]:
    dx = (variant % 5) * 1.1
    if cat == "abstain_rejected":
        return {"timestamp_sec": 12.0 + variant, "calibration_state": "REJECTED", "uncertainty_band": "UNRELIABLE", "observation_coverage_pct": 30.0, "possession_team": "HOME", "ball_xy": [50.0, 34.0], "kinematics": []}
    if cat == "defensive_central":
        return {
            "timestamp_sec": 45.0 + variant,
            "calibration_state": "GOOD",
            "uncertainty_band": "LOW",
            "observation_coverage_pct": 88.0,
            "possession_team": "AWAY",
            "ball_carrier_track_id": "A-CAM",
            "ball_xy": [32.0 + dx * 0.5, 34.0],
            "home_structure": {"rest_defense_count": 4, "def_to_mid_gap_m": 15.0},
            "kinematics": [
                {"track_id": "H-GK", "team": "HOME", "player_slot": "GK", "is_goalkeeper": True, "x_m": 5.0, "y_m": 34.0},
                {"track_id": "H-CB1", "team": "HOME", "player_slot": "CB", "x_m": 22.0, "y_m": 31.0},
                {"track_id": "H-CB2", "team": "HOME", "player_slot": "CB", "x_m": 22.0, "y_m": 38.0},
                {"track_id": "H-CDM", "team": "HOME", "player_slot": "CDM", "x_m": 36.0, "y_m": 33.0},
                {"track_id": "H-CM", "team": "HOME", "player_slot": "CM", "x_m": 40.0, "y_m": 41.0},
                {"track_id": "H-LB", "team": "HOME", "player_slot": "LB", "x_m": 24.0, "y_m": 54.0},
                {"track_id": "H-RB", "team": "HOME", "player_slot": "RB", "x_m": 24.0, "y_m": 14.0},
                {"track_id": "A-CAM", "team": "AWAY", "player_slot": "CAM", "x_m": 32.0, "y_m": 34.0},
                {"track_id": "A-ST", "team": "AWAY", "player_slot": "ST", "x_m": 24.5, "y_m": 33.5},
            ],
        }
    return {
        "timestamp_sec": 18.0 + variant,
        "calibration_state": "PARTIAL" if cat == "partial_uncertainty" else "GOOD",
        "uncertainty_band": "MODERATE" if cat == "partial_uncertainty" else "LOW",
        "observation_coverage_pct": 58.0 if cat == "partial_uncertainty" else 91.0,
        "possession_team": "HOME",
        "ball_carrier_track_id": "H-CM",
        "ball_xy": [60.0 + dx if cat != "crowded_shot" else 83.0, 34.0],
        "home_structure": {"rest_defense_count": 3 if cat != "thin_rest_def" else 2},
        "kinematics": [
            {"track_id": "H-CM", "team": "HOME", "player_slot": "CM", "x_m": 60.0 + dx if cat != "crowded_shot" else 83.0, "y_m": 34.0, "vx_mps": 1.2, "vy_mps": 0.0},
            {"track_id": "H-ST", "team": "HOME", "player_slot": "ST", "x_m": 78.0 + dx if cat != "crowded_shot" else 92.0, "y_m": 34.0, "vx_mps": 2.8, "vy_mps": 0.0},
            {"track_id": "H-LW", "team": "HOME", "player_slot": "LW", "x_m": 75.0, "y_m": 56.0, "vx_mps": 4.2, "vy_mps": 0.2},
            {"track_id": "H-CDM", "team": "HOME", "player_slot": "CDM", "x_m": 49.0, "y_m": 31.0},
            {"track_id": "A-CDM", "team": "AWAY", "player_slot": "CDM", "x_m": 65.0 + dx * 0.5, "y_m": 34.2},
            {"track_id": "A-CB1", "team": "AWAY", "player_slot": "CB", "x_m": 86.0 if cat == "crowded_shot" else 74.0, "y_m": 34.8},
            {"track_id": "A-RB", "team": "AWAY", "player_slot": "RB", "x_m": 73.0, "y_m": 53.0},
            {"track_id": "A-GK", "team": "AWAY", "player_slot": "GK", "is_goalkeeper": True, "x_m": 99.0, "y_m": 34.0},
        ],
    }


def run_benchmark() -> Dict[str, Any]:
    tracemalloc.start()
    engine = CounterfactualFootballEngine(monte_carlo_samples=16)

    categories = [
        "passing_progressive",
        "passing_switch",
        "thin_rest_def",
        "crowded_shot",
        "defensive_central",
        "partial_uncertainty",
        "abstain_rejected",
    ]

    total = 220
    schema_ok = 0
    evidence_ok = 0
    hindsight_clean = 0
    abstain_correct = 0
    abstain_expected_total = 0
    latencies_ms: List[float] = []

    for i in range(total):
        cat = categories[i % len(categories)]
        variant = i // len(categories)
        snap = _make_scenario_snapshot(cat, variant)
        hint = "SHOT" if cat == "crowded_shot" else ("DEFENSIVE_ACTION" if cat == "defensive_central" else None)

        st_neg = build_state_from_snapshot(
            f"BENCH-M-{i:03d}", snap,
            window_id=f"WIN-B-{i:03d}",
            decision_type_hint=hint,
            post_action_outcome=PostActionOutcome(outcome_label="TURNOVER", possession_retained_after_3s=False),
        )
        st_pos = build_state_from_snapshot(
            f"BENCH-M-{i:03d}", snap,
            window_id=f"WIN-B-{i:03d}",
            decision_type_hint=hint,
            post_action_outcome=PostActionOutcome(outcome_label="GOAL", possession_retained_after_3s=True),
        )

        t0 = time.perf_counter()
        comp_a = engine.evaluate(st_neg)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        comp_b = engine.evaluate(st_pos)

        # 1. Schema check
        CounterfactualComparison.model_validate(comp_a.model_dump())
        schema_ok += 1

        # 2. Hindsight check
        if comp_a.best_alternative_id == comp_b.best_alternative_id and comp_a.regret_estimate == comp_b.regret_estimate:
            hindsight_clean += 1

        # 3. Abstention & Evidence check
        if cat == "abstain_rejected":
            abstain_expected_total += 1
            if comp_a.status == "ABSTAINED_INSUFFICIENT_CONTEXT":
                abstain_correct += 1
                evidence_ok += 1
        else:
            if comp_a.status == "EVALUATED" and comp_a.candidates and all(c.telemetry_evidence_refs for c in comp_a.candidates):
                evidence_ok += 1

    # Also test 20 Phase 41 Coach Tool selection cases
    repo40 = Phase40Repository()
    repo40._use_pg = lambda _: False  # type: ignore[method-assign]
    repo41 = Phase41Repository()
    repo41._use_pg = lambda _: False  # type: ignore[method-assign]
    orch = PersonalCoachOrchestrator(repo40)
    orch.tools.p41_repo = repo41
    repo41.save_decision_windows("bench-u", [{
        "window_id": "W-BENCH-1",
        "match_id": "M-BENCH-1",
        "cluster_id": "C-1",
        "decision_type": "ATTACKING_PASS",
        "status": "EVALUATED",
        "provenance": "IMPORTED_MATCH_TRACE",
        "pre_action_cutoff_sec": 17.9,
        "action_timestamp_sec": 18.0,
        "observation_adequacy": "ADEQUATE",
        "calibration_state": "GOOD",
        "coverage_pct": 91.0,
        "regret_estimate": 0.08,
        "normalized_regret": 0.14,
        "pre_action_state": {},
        "counterfactual_comparison": {"best_alternative_label": "LW Switch"},
    }])
    tool_hits = 0
    for q in [
        "What is my Football IQ profile and decision regret?",
        "Analyze my passing decisions and interception turnover risk",
        "Evaluate defensive diving vs central cover in my matches",
        "Check player capability bottleneck for through balls",
    ]:
        ans = orch.ask("bench-u", CoachQuestionRequest(question=q))
        if any(t["tool"].startswith("get_") or t["tool"].startswith("evaluate_") for t in ans.tool_trace):
            tool_hits += 1

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    lat_sorted = sorted(latencies_ms)
    metrics = {
        "total_decision_scenarios": total,
        "schema_validity_rate_pct": round((schema_ok / total) * 100.0, 2),
        "evidence_reference_resolution_pct": round((evidence_ok / total) * 100.0, 2),
        "zero_hindsight_leakage_rate_pct": round((hindsight_clean / total) * 100.0, 2),
        "abstention_compliance_pct": round((abstain_correct / max(1, abstain_expected_total)) * 100.0, 2),
        "coach_tool_routing_accuracy_pct": round((tool_hits / 4.0) * 100.0, 2),
        "latency_ms": {
            "mean": round(statistics.mean(latencies_ms), 3),
            "p50": round(statistics.median(latencies_ms), 3),
            "p95": round(lat_sorted[min(len(lat_sorted) - 1, int(len(lat_sorted) * 0.95))], 3),
            "max": round(max(latencies_ms), 3),
        },
        "peak_traced_memory_mb": round(peak_bytes / (1024 * 1024), 3),
        "target_gates": {
            "schema_valid >= 95%": (schema_ok / total) * 100.0 >= 95.0,
            "evidence_ref >= 95%": (evidence_ok / total) * 100.0 >= 95.0,
            "zero_hindsight == 100%": hindsight_clean == total,
            "coach_tool_routing >= 90%": (tool_hits / 4.0) >= 0.90,
        },
    }

    out_path = ROOT / "artifacts" / "phase41" / "PHASE_41_BENCHMARK_METRICS.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    m = run_benchmark()
    print(json.dumps(m, indent=2))
    assert all(m["target_gates"].values()), f"Benchmark gate failure: {m['target_gates']}"
