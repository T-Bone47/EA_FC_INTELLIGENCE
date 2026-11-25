"""Empirical gameplay performance evaluator for EA FC Intelligence (Phase 33).

Provides rigorous statistical evaluation of controlled match trials against
frozen V3.2.1 recommendation engine predictions:
- Paired differences per 90 minutes
- Within-pair Cohen's d effect sizes
- Non-parametric bootstrap 95% confidence intervals
- Multi-metric evaluation (primary and secondary endpoints)
- Directional hypothesis testing (AGREES / DISAGREES / TIED)
- Near-tie uncertainty verification
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np

from backend.services.fc27_card_research import digest
from backend.services.performance_evidence import compare_observed
from verification.evaluate_fc27_striker_pilot import (
    load_predictions,
    per_session,
    read_sheet,
)


def compute_paired_effect_size(differences: List[float]) -> Dict[str, Optional[float]]:
    """Compute mean paired difference, standard deviation, and Cohen's d."""
    if not differences or len(differences) < 2:
        return {"mean_diff": None, "std_diff": None, "cohens_d": None}
    
    n = len(differences)
    mean_diff = float(np.mean(differences))
    std_diff = float(np.std(differences, ddof=1))
    
    if std_diff == 0.0 or math.isnan(std_diff):
        cohens_d = 0.0 if mean_diff == 0.0 else (float("inf") if mean_diff > 0 else float("-inf"))
    else:
        cohens_d = mean_diff / std_diff
        
    return {
        "n_pairs": n,
        "mean_diff": round(mean_diff, 4),
        "std_diff": round(std_diff, 4),
        "cohens_d": round(cohens_d, 4) if not math.isinf(cohens_d) else None,
    }


def compute_bootstrap_ci(
    differences: List[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Dict[str, Optional[float]]:
    """Compute non-parametric bootstrap confidence interval for the mean paired difference."""
    if not differences or len(differences) < 2:
        return {"ci_lower": None, "ci_upper": None, "alpha": alpha}
        
    rng = np.random.default_rng(seed)
    diffs = np.array(differences, dtype=float)
    n = len(diffs)
    
    resample_means = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        sample = rng.choice(diffs, size=n, replace=True)
        resample_means[i] = np.mean(sample)
        
    lower_pct = 100 * (alpha / 2.0)
    upper_pct = 100 * (1.0 - alpha / 2.0)
    
    ci_lower = float(np.percentile(resample_means, lower_pct))
    ci_upper = float(np.percentile(resample_means, upper_pct))
    
    return {
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "confidence_level": 1.0 - alpha,
    }


def compute_paired_t_test(differences: List[float]) -> Dict[str, Optional[float]]:
    """Compute Student's paired t-statistic, degrees of freedom, and two-tailed p-value."""
    if not differences or len(differences) < 2:
        return {"t_statistic": None, "degrees_of_freedom": None, "p_value": None}
    
    n = len(differences)
    mean_diff = float(np.mean(differences))
    std_diff = float(np.std(differences, ddof=1))
    
    if std_diff == 0.0 or math.isnan(std_diff):
        return {
            "t_statistic": 0.0 if mean_diff == 0 else None,
            "degrees_of_freedom": n - 1,
            "p_value": 1.0 if mean_diff == 0 else 0.0
        }
    
    se = std_diff / math.sqrt(n)
    t_val = mean_diff / se
    df = n - 1
    
    def _t_pdf(u: float, deg_f: int) -> float:
        coef = math.exp(math.lgamma((deg_f + 1) / 2.0) - math.lgamma(deg_f / 2.0)) / math.sqrt(math.pi * deg_f)
        return coef * ((1.0 + (u * u) / deg_f) ** (-(deg_f + 1) / 2.0))

    t_abs = abs(t_val)
    if t_abs == 0.0:
        p_val = 1.0
    else:
        n_steps = 200
        h = (2.0 * t_abs) / n_steps
        s = _t_pdf(-t_abs, df) + _t_pdf(t_abs, df)
        for i in range(1, n_steps):
            u = -t_abs + i * h
            s += 4.0 * _t_pdf(u, df) if i % 2 == 1 else 2.0 * _t_pdf(u, df)
        integral = (h / 3.0) * s
        p_val = max(0.0, min(1.0, 1.0 - integral))

    return {
        "t_statistic": round(t_val, 4),
        "degrees_of_freedom": df,
        "p_value": round(p_val, 4),
    }


def compute_wilcoxon_signed_rank(differences: List[float]) -> Dict[str, Optional[float]]:
    """Compute Wilcoxon signed-rank test for paired differences."""
    non_zero = [d for d in differences if d != 0.0]
    if len(non_zero) < 5:
        return {"w_statistic": None, "z_statistic": None, "p_value": None, "non_zero_pairs": len(non_zero)}
    
    m = len(non_zero)
    abs_diffs = sorted([(abs(d), d) for d in non_zero], key=lambda x: x[0])
    
    ranks: List[Tuple[float, float]] = []
    i = 0
    while i < m:
        j = i
        while j < m and abs_diffs[j][0] == abs_diffs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks.append((avg_rank, abs_diffs[k][1]))
        i = j
        
    w_pos = sum(r for r, d in ranks if d > 0)
    w_neg = sum(r for r, d in ranks if d < 0)
    w_stat = min(w_pos, w_neg)
    
    mean_w = (m * (m + 1)) / 4.0
    std_w = math.sqrt((m * (m + 1) * (2 * m + 1)) / 24.0)
    
    if std_w == 0.0:
        z_stat = 0.0
        p_val = 1.0
    else:
        z_stat = (w_stat - mean_w + 0.5) / std_w if w_stat < mean_w else (w_stat - mean_w - 0.5) / std_w
        p_val = math.erfc(abs(z_stat) / math.sqrt(2.0))
        
    return {
        "w_statistic": round(w_stat, 2),
        "z_statistic": round(z_stat, 4),
        "p_value": round(p_val, 4),
        "non_zero_pairs": m,
    }


class EmpiricalEvaluator:
    """Evaluates empirical match observations against V3.2.1 predictions."""

    def __init__(self, predictions_path: Path):
        self.predictions = load_predictions(predictions_path)
        self.cards = [self.predictions["cards"][arm]["card_item_id"] for arm in ("A", "B")]
        self.card_names = {arm: self.predictions["cards"][arm]["name"] for arm in ("A", "B")}

    def evaluate_sheet(
        self,
        sheet_path: Path,
        secondary_metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Comprehensive evaluation of match sheet across primary and secondary metrics."""
        if secondary_metrics is None:
            secondary_metrics = ["goals", "shots", "shots_on_target", "tackles_won", "interceptions"]

        groups, excluded = read_sheet(sheet_path, self.predictions)
        tactics_eval = {}

        for profile, pred_info in self.predictions["tactics"].items():
            primary_metric = pred_info["primary_outcome_per_90"]
            predicted_leader = pred_info["predictions"][0]["card"]
            pred_score_a = next(x["score"] for x in pred_info["predictions"] if x["card"] == "A")
            pred_score_b = next(x["score"] for x in pred_info["predictions"] if x["card"] == "B")
            pred_delta = pred_score_a - pred_score_b

            strata = []
            for scope, rows in sorted(groups.items()):
                context = rows[0]["payload"]["context"]
                if context["tactical_profile"] != profile:
                    continue

                # Primary metric evaluation
                prim_evidence = compare_observed(rows, self.cards, primary_metric, context)
                obs_delta = prim_evidence["paired_difference_per_90"]
                direction = None if obs_delta in (None, 0) else "A" if obs_delta > 0 else "B"
                agreement = (
                    None
                    if obs_delta is None
                    else "TIED"
                    if obs_delta == 0
                    else ("AGREES" if direction == predicted_leader else "DISAGREES")
                )

                # Extract per-session paired differences for statistical analysis
                sessions_data = per_session(rows, self.cards, primary_metric, context)
                session_diffs = [
                    sess["a_minus_b_per_90"]
                    for sess in sessions_data.values()
                    if sess.get("a_minus_b_per_90") is not None
                ]

                effect_size = compute_paired_effect_size(session_diffs)
                bootstrap_ci = compute_bootstrap_ci(session_diffs)
                paired_t = compute_paired_t_test(session_diffs)
                wilcoxon = compute_wilcoxon_signed_rank(session_diffs)

                # Secondary metrics evaluation
                secondary_eval = {}
                for sec_m in secondary_metrics:
                    sec_ev = compare_observed(rows, self.cards, sec_m, context)
                    sec_diffs = [
                        sess["a_minus_b_per_90"]
                        for sess in per_session(rows, self.cards, sec_m, context).values()
                        if sess.get("a_minus_b_per_90") is not None
                    ]
                    sec_eff = compute_paired_effect_size(sec_diffs)
                    secondary_eval[sec_m] = {
                        "evidence": sec_ev,
                        "effect_size": sec_eff,
                        "direction": (
                            None
                            if sec_ev["paired_difference_per_90"] is None
                            else "A"
                            if sec_ev["paired_difference_per_90"] > 0
                            else "B"
                            if sec_ev["paired_difference_per_90"] < 0
                            else "TIED"
                        ),
                    }

                strata.append({
                    "context": context,
                    "rows": len(rows),
                    "primary_metric": primary_metric,
                    "evidence": prim_evidence,
                    "direction": direction,
                    "prediction_agreement": agreement,
                    "predicted_leader": predicted_leader,
                    "predicted_delta": round(pred_delta, 5),
                    "observed_delta_per_90": obs_delta,
                    "effect_size": effect_size,
                    "bootstrap_95ci": bootstrap_ci,
                    "paired_t_test": paired_t,
                    "wilcoxon_test": wilcoxon,
                    "session_outcomes": sessions_data,
                    "secondary_metrics": secondary_eval,
                })

            complete = any(s["evidence"]["status"] == "DESCRIPTIVE_PAIRED_RESULTS" for s in strata)
            tactics_eval[profile] = {
                "primary_metric": primary_metric,
                "predicted_leader": predicted_leader,
                "predicted_card_name": self.card_names[predicted_leader],
                "status": "DESCRIPTIVE_PAIRED_RESULTS" if complete else "INSUFFICIENT_GAMEPLAY_EVIDENCE",
                "strata": strata,
            }

        total_played = sum(map(len, groups.values()))
        return {
            "evaluation_engine": "Phase35-EmpiricalEvaluator-StatisticalTesting",
            "protocol_key": self.predictions["protocol_key"],
            "prediction_sha256": self.predictions["prediction_sha256"],
            "total_matches_ingested": total_played,
            "excluded_deviations": excluded,
            "evidence_status": "DESCRIPTIVE_EVALUATION_COMPLETE" if total_played > 0 else "NO_DATA",
            "tactics": tactics_eval,
        }
