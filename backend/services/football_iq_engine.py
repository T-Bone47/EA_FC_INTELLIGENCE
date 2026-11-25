"""Phase 41M: Multi-Dimensional Football IQ Profiling Engine.

Enforces Phase 41 core separation principles:
  - Strictly excludes SYNTHETIC_FIXTURE windows from persistent Football IQ estimation.
  - Separates Preference (tendency) vs Execution Error vs Pre-Action Decision Quality vs Outcomes.
  - Deduplicates cluster exposures (cluster_id aggregation) so slow adjacent frames never inflate regret.
  - Reports explicit cold-start / sparse-evidence caveats across 10 gameplay decision dimensions.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from backend.domain.phase41_models import (
    FootballIQDimensionScore,
    FootballIQProfile,
)

FOOTBALL_IQ_DIMENSIONS: List[Tuple[str, str]] = [
    ("passing_risk_balance", "Passing Risk & Progression Balance"),
    ("line_breaking_awareness", "Line-Breaking Pass Recognition"),
    ("pressing_resistance_choices", "Pressing Resistance & Retention"),
    ("switching_play_timing", "Switching Play & Width Timing"),
    ("final_third_chance_selection", "Final-Third Shot vs Pass Selection"),
    ("defensive_patience_vs_diving", "Defensive Patience vs Diving In"),
    ("central_channel_protection", "Central Channel Protection"),
    ("transition_recovery_decisions", "Transition Recovery Decisions"),
    ("rest_defense_discipline", "Rest-Defense Discipline"),
    ("off_ball_spacing_and_runs", "Off-Ball Spacing & Run Timing"),
]


class FootballIQEngine:
    """Computes cluster-deduplicated Football IQ profiles from stored Phase 41 decision opportunities."""

    def compute_profile(
        self,
        user_id: str,
        opportunities: List[Dict[str, Any]],
    ) -> FootballIQProfile:
        eligible = [
            op for op in opportunities
            if op.get("provenance") != "SYNTHETIC_FIXTURE"
            and op.get("status") == "EVALUATED"
        ]
        synthetic_excluded = sum(1 for op in opportunities if op.get("provenance") == "SYNTHETIC_FIXTURE")
        match_ids = {op.get("match_id") for op in eligible if op.get("match_id")}

        if not eligible:
            dims = [
                FootballIQDimensionScore(
                    dimension=code,
                    label=label,
                    score_0_100=None,
                    confidence="INSUFFICIENT",
                    sample_windows=0,
                    cluster_count=0,
                    caveat="No non-synthetic evaluated decision windows available yet.",
                )
                for code, label in FOOTBALL_IQ_DIMENSIONS
            ]
            return FootballIQProfile(
                user_id=user_id,
                eligible_match_count=0,
                eligible_decision_windows=0,
                synthetic_excluded_count=synthetic_excluded,
                overall_football_iq=None,
                confidence="INSUFFICIENT",
                dimensions=dims,
                top_regret_clusters=[],
            )

        # Group windows cleanly by dimension & deduplicate by cluster_id
        by_dim_cluster: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for op in eligible:
            dim = self._map_window_to_dimension(op)
            cid = str(op.get("cluster_id") or op.get("window_id"))
            by_dim_cluster[dim][cid].append(op)

        dim_scores: List[FootballIQDimensionScore] = []
        valid_scores: List[float] = []
        regret_clusters_flat: List[Dict[str, Any]] = []

        for code, label in FOOTBALL_IQ_DIMENSIONS:
            clusters = by_dim_cluster.get(code, {})
            if not clusters:
                dim_scores.append(
                    FootballIQDimensionScore(
                        dimension=code,
                        label=label,
                        score_0_100=None,
                        confidence="INSUFFICIENT",
                        sample_windows=0,
                        cluster_count=0,
                        caveat="Insufficient non-synthetic decision windows for this dimension.",
                    )
                )
                continue

            cluster_regrets: List[float] = []
            cluster_norm_regrets: List[float] = []
            outcome_retained_flags: List[float] = []
            execution_errors: List[float] = []
            total_windows = 0

            for cid, rows in clusters.items():
                total_windows += len(rows)
                mean_r = sum(float(r.get("regret_estimate") or 0.0) for r in rows) / len(rows)
                mean_nr = sum(float(r.get("normalized_regret") or 0.0) for r in rows) / len(rows)
                cluster_regrets.append(mean_r)
                cluster_norm_regrets.append(mean_nr)

                for r in rows:
                    post = r.get("post_action_outcome") or {}
                    ret = post.get("possession_retained_after_3s")
                    if ret is not None:
                        outcome_retained_flags.append(1.0 if ret else 0.0)
                        # Execution error = good pre-action choice (regret <= 0.035) that still lost the ball
                        if float(r.get("regret_estimate") or 0.0) <= 0.035:
                            execution_errors.append(0.0 if ret else 1.0)

                if mean_r >= 0.05:
                    rep = rows[0]
                    regret_clusters_flat.append({
                        "cluster_id": cid,
                        "window_id": rep.get("window_id"),
                        "match_id": rep.get("match_id"),
                        "dimension": code,
                        "mean_regret": round(mean_r, 4),
                        "timestamp_sec": rep.get("action_timestamp_sec"),
                    })

            avg_norm_r = sum(cluster_norm_regrets) / len(cluster_norm_regrets)
            avg_r = sum(cluster_regrets) / len(cluster_regrets)
            quality_score = round(max(12.0, min(98.0, 96.0 - avg_norm_r * 115.0)), 1)
            pref_val = round(min(1.0, total_windows / max(1.0, float(len(eligible)) * 0.45)), 3)
            exec_err = round(sum(execution_errors) / len(execution_errors), 3) if execution_errors else None
            out_rate = round(sum(outcome_retained_flags) / len(outcome_retained_flags), 3) if outcome_retained_flags else None
            conf = "HIGH" if len(clusters) >= 8 else ("MODERATE" if len(clusters) >= 3 else "LOW")

            valid_scores.append(quality_score)
            dim_scores.append(
                FootballIQDimensionScore(
                    dimension=code,
                    label=label,
                    score_0_100=quality_score,
                    confidence=conf,
                    sample_windows=total_windows,
                    cluster_count=len(clusters),
                    preference_value=pref_val,
                    execution_error_rate=exec_err,
                    decision_quality_score=quality_score,
                    outcome_success_rate=out_rate,
                    mean_regret=round(avg_r, 4),
                    caveat=(
                        f"Computed from {len(clusters)} independent decision cluster(s) ({total_windows} windows). "
                        + ("Low cluster count — interpret as directional." if conf == "LOW" else "Cluster-weighted.")
                    ),
                )
            )

        regret_clusters_flat.sort(key=lambda c: c["mean_regret"], reverse=True)
        overall = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None
        overall_conf = "HIGH" if len(match_ids) >= 5 else ("MODERATE" if len(match_ids) >= 2 else "LOW")

        return FootballIQProfile(
            user_id=user_id,
            eligible_match_count=len(match_ids),
            eligible_decision_windows=len(eligible),
            synthetic_excluded_count=synthetic_excluded,
            overall_football_iq=overall,
            confidence=overall_conf,
            dimensions=dim_scores,
            top_regret_clusters=regret_clusters_flat[:6],
        )

    def _map_window_to_dimension(self, op: Dict[str, Any]) -> str:
        dt = str(op.get("decision_type", "ATTACKING_PASS"))
        if dt == "DEFENSIVE_ACTION":
            comp = op.get("counterfactual_comparison") or {}
            best_lbl = str(comp.get("best_alternative_label", "")).upper()
            if "CENTRAL" in best_lbl or "ZONE 14" in best_lbl:
                return "central_channel_protection"
            if "CM/CDM" in best_lbl or "RECOVER" in best_lbl:
                return "transition_recovery_decisions"
            return "defensive_patience_vs_diving"
        pre = op.get("pre_action_state") or {}
        home_rest = int((pre.get("home_structure") or {}).get("rest_defense_count") or 3)
        if dt in ("ATTACKING_PASS", "THROUGH_BALL") and home_rest <= 2:
            return "rest_defense_discipline"
        mapping = {
            "ATTACKING_PASS": "line_breaking_awareness",
            "POSSESSION_RETENTION": "pressing_resistance_choices",
            "THROUGH_BALL": "passing_risk_balance",
            "SWITCH_OR_CROSS": "switching_play_timing",
            "SHOT": "final_third_chance_selection",
            "CARRY_OR_DRIBBLE": "passing_risk_balance",
            "OFF_BALL_RUN": "off_ball_spacing_and_runs",
        }
        return mapping.get(dt, "passing_risk_balance")
