"""ENGINE EXPERIMENT FRAMEWORK (§48).

Runs scoring-config variants against the deterministic evaluation suite
(engine_evaluation.SCENARIOS) WITHOUT ever touching production behavior:

  * every engine instance is constructed locally from an explicit ScoringConfig;
  * production module-level config is never mutated;
  * results are persisted to the existing `experiment` / `experiment_result`
    tables (schema §22-23) with the exact config, scenario fingerprint and
    engine version, so any experiment is reproducible;
  * an experiment never silently becomes production: adopting a config change
    requires editing scoring_config/engine_config in code + full regression +
    golden-baseline validation (BASELINE V1 weights policy).

Usage (script or API-less tooling — NOT wired into request handling):
    from backend.services.engine_experiments import run_experiment
    run_experiment("exp-attr-0.35", "attribute_fit 0.35 vs tactical 0.10",
                   {"component_weights": {...}})
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from backend.services import engine_evaluation
from backend.services.engine_config import ENGINE_VERSION
from backend.services.recommendation_engine_v2 import RecommendationEngineV2
from backend.services.scoring_config import COMPONENT_WEIGHTS, ScoringConfig

ALLOWED_OVERRIDE_KEYS = {"component_weights", "tactical_floor"}


def validate_overrides(overrides: dict) -> list[str]:
    """Config overrides must be explicit, bounded and sane before an
    experiment runs. Returns a list of problems (empty = valid)."""
    problems: list[str] = []
    for k in overrides:
        if k not in ALLOWED_OVERRIDE_KEYS:
            problems.append(f"unknown override key {k!r} "
                            f"(allowed: {sorted(ALLOWED_OVERRIDE_KEYS)})")
    cw = overrides.get("component_weights")
    if cw is not None:
        if set(cw) != set(COMPONENT_WEIGHTS):
            problems.append("component_weights must cover exactly "
                            f"{sorted(COMPONENT_WEIGHTS)}")
        else:
            total = sum(cw.values())
            if abs(total - 1.0) > 1e-6:
                problems.append(f"component_weights must sum to 1.0 (got {total:.6f})")
            if any(v < 0 for v in cw.values()):
                problems.append("component_weights must be non-negative")
    tf = overrides.get("tactical_floor")
    if tf is not None and not (0.0 <= float(tf) <= 1.0):
        problems.append("tactical_floor must be within [0, 1]")
    return problems


def _build_config(overrides: dict) -> ScoringConfig:
    kw = {}
    if "component_weights" in overrides:
        kw["component_weights"] = dict(overrides["component_weights"])
    if "tactical_floor" in overrides:
        kw["tactical_floor"] = float(overrides["tactical_floor"])
    return ScoringConfig(**kw)


def _fingerprint(scenario_names: list[str], overrides: dict) -> str:
    payload = json.dumps({"scenarios": scenario_names, "overrides": overrides,
                          "engine_version": ENGINE_VERSION,
                          "baseline_weights": COMPONENT_WEIGHTS},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _run_variant(overrides: dict, scenario_names: list[str]) -> dict:
    engine = RecommendationEngineV2(_build_config(overrides))
    out: dict[str, dict] = {}
    for name in scenario_names:
        spec = engine_evaluation.SCENARIOS[name]()
        result = engine.recommend(spec["pool"], spec["req"],
                                  squad_ctx=spec.get("squad_ctx"),
                                  squad_members=spec.get("squad_members"))
        best = result.best_evaluation
        out[name] = {
            "best": best.candidate.name if best else None,
            "best_score": round(best.weighted_score, 6) if best and best.weighted_score is not None else None,
            "best_confidence": round(result.confidence.score, 6) if best else None,
            "ranked_order": [e.candidate.name for e in result.ranked],
            "excluded_hard": [x["name"] for x in result.excluded_hard],
        }
    return out


def run_experiment(name: str, hypothesis: str, overrides: dict,
                   scenario_names: Optional[list[str]] = None,
                   persist: bool = True) -> dict:
    """Run baseline vs variant across scenarios; persist both result rows.

    Returns a summary dict: fingerprint, per-scenario comparison, aggregate
    metrics (winner_change_rate, mean_abs_score_delta, top3_overlap). No
    production state is modified.
    """
    problems = validate_overrides(overrides)
    if problems:
        raise ValueError("invalid experiment config: " + "; ".join(problems))
    scenario_names = list(scenario_names or sorted(engine_evaluation.SCENARIOS))
    unknown = [n for n in scenario_names if n not in engine_evaluation.SCENARIOS]
    if unknown:
        raise ValueError(f"unknown scenarios: {unknown}")

    baseline = _run_variant({}, scenario_names)
    variant = _run_variant(overrides, scenario_names)

    per_scenario = {}
    changed = 0
    deltas = []
    overlaps = []
    for s in scenario_names:
        b, v = baseline[s], variant[s]
        winner_changed = b["best"] != v["best"]
        changed += int(winner_changed)
        delta = (abs(v["best_score"] - b["best_score"])
                 if b["best_score"] is not None and v["best_score"] is not None else None)
        if delta is not None:
            deltas.append(delta)
        top3_b, top3_v = set(b["ranked_order"][:3]), set(v["ranked_order"][:3])
        overlap = (len(top3_b & top3_v) / max(1, len(top3_b | top3_v)))
        overlaps.append(overlap)
        per_scenario[s] = {
            "baseline": b, "variant": v,
            "winner_changed": winner_changed,
            "best_score_delta": round(delta, 6) if delta is not None else None,
            "top3_overlap": round(overlap, 4),
        }

    summary = {
        "experiment": name,
        "hypothesis": hypothesis,
        "engine_version": ENGINE_VERSION,
        "fingerprint": _fingerprint(scenario_names, overrides),
        "overrides": overrides,
        "scenarios_run": len(scenario_names),
        "metrics": {
            "winner_change_rate": round(changed / len(scenario_names), 4),
            "winners_changed": changed,
            "mean_abs_score_delta": round(sum(deltas) / len(deltas), 6) if deltas else None,
            "mean_top3_overlap": round(sum(overlaps) / len(overlaps), 4) if overlaps else None,
            "constraint_behavior_identical": all(
                per_scenario[s]["baseline"]["excluded_hard"] == per_scenario[s]["variant"]["excluded_hard"]
                for s in scenario_names),
        },
        "per_scenario": per_scenario,
    }

    if persist:
        try:
            from backend.core.db import execute, query_one
            row = query_one(
                """INSERT INTO experiment (name, hypothesis, engine_config, status)
                   VALUES (%s, %s, %s::jsonb, 'COMPLETED')
                   ON CONFLICT (name) DO UPDATE
                     SET hypothesis = EXCLUDED.hypothesis,
                         engine_config = EXCLUDED.engine_config,
                         status = 'COMPLETED'
                   RETURNING id""",
                (name, hypothesis, json.dumps({
                    "overrides": overrides, "fingerprint": summary["fingerprint"],
                    "engine_version": ENGINE_VERSION,
                    "scenarios": scenario_names})))
            exp_id = row["id"]
            execute("DELETE FROM experiment_result WHERE experiment_id = %s", (exp_id,))
            for variant_name, results in (("baseline", baseline), ("variant", variant)):
                metrics = dict(summary["metrics"]) if variant_name == "variant" else {}
                execute(
                    """INSERT INTO experiment_result (experiment_id, variant, metrics)
                       VALUES (%s, %s, %s::jsonb)""",
                    (exp_id, variant_name,
                     json.dumps({"metrics": metrics, "results": results}, default=str)))
            summary["persisted"] = {"experiment_id": str(exp_id)}
        except Exception as exc:                     # DB down: results still returned
            summary["persisted"] = {"error": f"could not persist: {exc}"}
    return summary
