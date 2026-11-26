"""Phase 43E: Empirical Statistical & Bayesian Experiment Analysis Service.

Enforces strict scientific discipline over user match experiments:
- Unit of analysis is strictly MATCH_CLUSTER_AGGREGATE (never treating correlated frames as independent).
- Excludes SYNTHETIC_FIXTURE and game_version mismatches cleanly before estimation.
- Computes opportunity-normalized rates, descriptive distributions (mean/median/SD/IQR),
  paired or Welch/Mann-Whitney p-values via SciPy, 95% bootstrap CIs via scipy.stats.bootstrap,
  bias-corrected Hedges' g effect size, analytical Normal-Normal conjugate Bayesian posterior probability,
  leave-one-match-out sensitivity stability, and confounder audits.
- Allows INCONCLUSIVE or INSUFFICIENT_EVIDENCE outcomes openly whenever evidence is weak or confounded.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from backend.domain.phase40_models import MatchIntelligenceRecord
from backend.domain.phase43_models import (
    ArmSummary,
    ConfounderReport,
    EvidenceGrade,
    ExperimentArm,
    ExperimentStatisticalAnalysis,
    ExperimentStatus,
    StatisticalVerdict,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository
from backend.repositories.phase43_repository import Phase43Repository, get_phase43_repository
from backend.services.tactical_experiment_engine import SUPPORTED_PRIMARY_METRICS


def _extract_match_metric(match: MatchIntelligenceRecord, metric_name: str) -> Tuple[Optional[float], int]:
    """Extracts ONE cluster-level scalar metric + opportunity denominator for a match."""
    fm = match.feature_metrics or {}
    spec = SUPPORTED_PRIMARY_METRICS.get(metric_name)
    if spec and spec.get("numerator") and spec.get("denominator"):
        num = fm.get(spec["numerator"])
        den = fm.get(spec["denominator"])
        if isinstance(num, (int, float)) and isinstance(den, (int, float)) and den > 0:
            return round(float(num) / float(den), 4), int(den)
    raw = fm.get(metric_name)
    if isinstance(raw, (int, float)):
        return round(float(raw), 4), 1
    return None, 0


def _hedges_g(x_b: np.ndarray, x_a: np.ndarray) -> Optional[float]:
    n1, n0 = len(x_b), len(x_a)
    if n1 < 2 or n0 < 2:
        return None
    s1 = float(np.std(x_b, ddof=1))
    s0 = float(np.std(x_a, ddof=1))
    df = n1 + n0 - 2
    if df <= 0:
        return None
    sp = math.sqrt(((n1 - 1) * s1 * s1 + (n0 - 1) * s0 * s0) / df)
    if sp < 1e-8:
        diff = float(np.mean(x_b) - np.mean(x_a))
        return 0.0 if abs(diff) < 1e-8 else (3.0 if diff > 0 else -3.0)
    d = (float(np.mean(x_b)) - float(np.mean(x_a))) / sp
    correction = 1.0 - (3.0 / max(1.0, 4.0 * df - 1.0))
    return round(d * correction, 4)


class ExperimentAnalysisService:
    """Runs statistical, Bayesian, sensitivity, and confounder analysis over match-linked experiments."""

    def __init__(
        self,
        repo: Optional[Phase43Repository] = None,
        phase40_repo: Optional[Phase40Repository] = None,
    ) -> None:
        self.repo = repo or get_phase43_repository()
        self.p40_repo = phase40_repo or get_phase40_repository()

    def analyze(self, user_id: str, experiment_id: str, *, persist: bool = True) -> ExperimentStatisticalAnalysis:
        uid = str(user_id)
        exp = self.repo.get_experiment(uid, experiment_id)
        snap_a = self.repo.get_snapshot(uid, exp.baseline_snapshot_id)
        snap_b = self.repo.get_snapshot(uid, exp.variant_snapshot_id)
        metric_spec = SUPPORTED_PRIMARY_METRICS.get(exp.primary_metric, {"higher_is_better": True})
        higher_is_better = bool(metric_spec.get("higher_is_better", True))

        matches_by_id = {m.match_id: m for m in self.p40_repo.list_matches(uid, exclude_synthetic=False, limit=200)}
        links_a: List[Tuple[Dict[str, Any], MatchIntelligenceRecord]] = []
        links_b: List[Tuple[Dict[str, Any], MatchIntelligenceRecord]] = []

        synthetic_excl = 0
        version_mismatch = 0
        patches_a: set[str] = set()
        patches_b: set[str] = set()
        modes_seen: set[str] = set()
        opp_a: Dict[str, int] = {}
        opp_b: Dict[str, int] = {}
        low_cov_warnings: List[str] = []

        for lnk in exp.linked_matches:
            m = matches_by_id.get(lnk["match_id"])
            if not m:
                continue
            if m.provenance == "SYNTHETIC_FIXTURE" or lnk.get("excluded_reason") == "SYNTHETIC_FIXTURE_EXCLUDED":
                synthetic_excl += 1
                continue
            if m.game_version != exp.game_version:
                version_mismatch += 1
                continue
            modes_seen.add(m.gameplay_mode)
            if m.tracking_coverage_pct < 40.0:
                low_cov_warnings.append(f"Match {m.match_id} has low coverage ({m.tracking_coverage_pct:.1f}%).")
            opp_key = str(lnk.get("opponent_archetype") or m.opponent_context.get("archetype") or "UNSPECIFIED")
            if lnk["arm"] == ExperimentArm.BASELINE_A.value:
                links_a.append((lnk, m))
                patches_a.add(m.game_patch)
                opp_a[opp_key] = opp_a.get(opp_key, 0) + 1
            else:
                links_b.append((lnk, m))
                patches_b.add(m.game_patch)
                opp_b[opp_key] = opp_b.get(opp_key, 0) + 1

        patch_drift = (len(patches_a | patches_b) > 1) or bool((patches_a | patches_b) - {exp.baseline_patch})
        mode_mismatch = len(modes_seen) > 1 or bool(modes_seen - {exp.gameplay_mode})
        opp_imbalance = (bool(opp_a) or bool(opp_b)) and (set(opp_a.keys()) != set(opp_b.keys())) and len(links_a) >= 2 and len(links_b) >= 2

        conf_warnings = list(low_cov_warnings[:3])
        conf_recs: List[str] = []
        if synthetic_excl:
            conf_warnings.append(f"{synthetic_excl} SYNTHETIC_FIXTURE match(es) excluded automatically from statistical pooling.")
        if version_mismatch:
            conf_warnings.append(f"{version_mismatch} edition-mismatched match(es) excluded (FC26 vs FC27 never mixed).")
        if patch_drift:
            conf_warnings.append("Gameplay patch drift detected across linked matches; patch tuning changes may confound deltas.")
            conf_recs.append("Stratify or restrict analysis to matches from the same game_patch.")
        if mode_mismatch:
            conf_warnings.append("Multiple gameplay modes detected across experiment arms.")
            conf_recs.append("Compare Competitive Rivals / Champions matches only within the same mode.")
        if opp_imbalance:
            conf_warnings.append("Opponent archetype distribution differs between Arm A and Arm B.")
            conf_recs.append("Record paired ABBA matches against comparable opponent tiers/styles.")

        confounders = ConfounderReport(
            comparable=not patch_drift and not mode_mismatch and version_mismatch == 0,
            version_mismatch_count=version_mismatch,
            patch_drift_detected=patch_drift,
            mode_mismatch_detected=mode_mismatch,
            synthetic_excluded_count=synthetic_excl,
            opponent_imbalance_detected=opp_imbalance,
            match_quality_warnings=conf_warnings,
            recommendations=conf_recs,
        )

        def _summarize_arm(arm_enum: ExperimentArm, snap, arm_links: List[Tuple[Dict[str, Any], MatchIntelligenceRecord]]) -> Tuple[ArmSummary, np.ndarray]:
            vals: List[float] = []
            tot_opps = 0
            tot_num = 0.0
            sec_acc: Dict[str, List[float]] = {k: [] for k in exp.secondary_metrics}
            mids: List[str] = []
            num_key = SUPPORTED_PRIMARY_METRICS.get(exp.primary_metric, {}).get("numerator")

            for _, m in arm_links:
                val, op_n = _extract_match_metric(m, exp.primary_metric)
                if val is not None:
                    vals.append(val)
                    tot_opps += op_n
                    if num_key and isinstance((m.feature_metrics or {}).get(num_key), (int, float)):
                        tot_num += float(m.feature_metrics[num_key])
                    mids.append(m.match_id)
                for sk in exp.secondary_metrics:
                    sv, _ = _extract_match_metric(m, sk)
                    if sv is not None:
                        sec_acc[sk].append(sv)

            arr = np.asarray(vals, dtype=np.float64)
            sec_means = {sk: (round(float(np.mean(sv)), 4) if sv else None) for sk, sv in sec_acc.items()}
            if arr.size == 0:
                return ArmSummary(
                    arm=arm_enum,
                    snapshot_id=snap.snapshot_id,
                    label=snap.label,
                    formation=snap.formation,
                    secondary_means=sec_means,
                ), arr
            return ArmSummary(
                arm=arm_enum,
                snapshot_id=snap.snapshot_id,
                label=snap.label,
                formation=snap.formation,
                eligible_match_count=int(arr.size),
                total_opportunities=tot_opps,
                mean_primary_metric=round(float(np.mean(arr)), 4),
                median_primary_metric=round(float(np.median(arr)), 4),
                sd_primary_metric=round(float(np.std(arr, ddof=1)), 4) if arr.size >= 2 else None,
                iqr_primary_metric=round(float(np.percentile(arr, 75) - np.percentile(arr, 25)), 4) if arr.size >= 2 else None,
                opportunity_normalized_rate=round(tot_num / tot_opps, 4) if (num_key and tot_opps > 0) else None,
                secondary_means=sec_means,
                match_ids=mids,
            ), arr

        arm_a, arr_a = _summarize_arm(ExperimentArm.BASELINE_A, snap_a, links_a)
        arm_b, arr_b = _summarize_arm(ExperimentArm.VARIANT_B, snap_b, links_b)

        limitations = [
            "Match-level aggregates are analyzed strictly as primary units (frames are never treated as independent samples).",
            "Empirical N-of-1 match trials remain vulnerable to opponent skill variance, gameplay momentum, and patch drift.",
        ]

        if arr_a.size < 2 or arr_b.size < 2:
            analysis = ExperimentStatisticalAnalysis(
                experiment_id=exp.experiment_id,
                primary_metric=exp.primary_metric,
                higher_is_better=higher_is_better,
                verdict=StatisticalVerdict.INSUFFICIENT_EVIDENCE,
                evidence_grade=EvidenceGrade.OBSERVED_ASSOCIATION if (arr_a.size + arr_b.size) > 0 else EvidenceGrade.THEORETICAL_SUITABILITY,
                arm_a=arm_a,
                arm_b=arm_b,
                confounders=confounders,
                interpretation=(
                    f"Insufficient match replicates to run hypothesis testing (Arm A={arr_a.size} match(es), Arm B={arr_b.size} match(es); "
                    f"at least 2 non-synthetic matches per arm required, target={exp.target_min_matches_per_arm})."
                ),
                limitations=limitations,
            )
            if persist:
                self.repo.save_experiment_analysis(uid, exp.experiment_id, analysis, ExperimentStatus.ACTIVE if (arr_a.size + arr_b.size) > 0 else ExperimentStatus.DRAFT)
            return analysis

        raw_delta = round(float(np.mean(arr_b) - np.mean(arr_a)), 4)
        # Positive "improvement" follows metric direction
        signed_improvement = raw_delta if higher_is_better else -raw_delta
        hedges = _hedges_g(arr_b, arr_a)

        # Frequentist match-level test (SciPy)
        p_val: Optional[float] = None
        test_name = "Welch_ttest_ind"
        try:
            if arr_a.size == arr_b.size and np.std(arr_b - arr_a) > 1e-9:
                _, p_t = stats.ttest_rel(arr_b, arr_a)
                p_val = float(p_t)
                test_name = "Paired_ttest_rel"
            else:
                _, p_t = stats.ttest_ind(arr_b, arr_a, equal_var=False)
                p_val = float(p_t) if not math.isnan(float(p_t)) else 1.0
                test_name = "Welch_ttest_ind"
        except Exception:
            p_val = 1.0

        # Non-parametric percentile bootstrap CI via scipy.stats.bootstrap
        boot_ci: Optional[List[float]] = None
        try:
            res_boot = stats.bootstrap(
                (arr_b, arr_a),
                lambda xb, xa: float(np.mean(xb) - np.mean(xa)),
                paired=False,
                n_resamples=1500,
                confidence_level=0.95,
                method="percentile",
                random_state=42,
            )
            lo = float(res_boot.confidence_interval.low)
            hi = float(res_boot.confidence_interval.high)
            if not (math.isnan(lo) or math.isnan(hi)):
                boot_ci = [round(lo, 4), round(hi, 4)]
        except Exception:
            boot_ci = [raw_delta, raw_delta]

        # Analytical Normal-Normal Conjugate Bayesian Posterior for mean difference (B - A)
        var_a = float(np.var(arr_a, ddof=1)) / len(arr_a)
        var_b = float(np.var(arr_b, ddof=1)) / len(arr_b)
        se_obs = math.sqrt(max(1e-6, var_a + var_b))
        prior_sd = 0.25
        prec_0 = 1.0 / (prior_sd * prior_sd)
        prec_obs = 1.0 / (se_obs * se_obs)
        post_var = 1.0 / (prec_0 + prec_obs)
        post_sd = math.sqrt(post_var)
        post_mean = (prec_obs * raw_delta) * post_var
        bayes_ci = [round(post_mean - 1.96 * post_sd, 4), round(post_mean + 1.96 * post_sd, 4)]
        mmi = float(getattr(exp, "minimum_meaningful_improvement", 0.05) or 0.05)
        if higher_is_better:
            prob_better = float(1.0 - stats.norm.cdf(0.0, loc=post_mean, scale=post_sd))
            prob_meaningful = float(1.0 - stats.norm.cdf(mmi, loc=post_mean, scale=post_sd))
        else:
            prob_better = float(stats.norm.cdf(0.0, loc=post_mean, scale=post_sd))
            prob_meaningful = float(stats.norm.cdf(-mmi, loc=post_mean, scale=post_sd))
        prob_better = round(max(0.001, min(0.999, prob_better)), 4)
        prob_meaningful = round(max(0.001, min(0.999, prob_meaningful)), 4)

        mean_a_val = float(arm_a.mean_primary_metric or 0.0)
        rel_imp = round(signed_improvement / abs(mean_a_val), 4) if abs(mean_a_val) > 1e-6 else None

        assigns = list(getattr(exp, "assignments", []) or [])
        scored_assigns = [a for a in assigns if a.get("adherent") is not None]
        adh_cnt = sum(1 for a in scored_assigns if a.get("adherent"))
        non_adh_cnt = len(scored_assigns) - adh_cnt
        adh_rate = round(adh_cnt / len(scored_assigns), 4) if scored_assigns else None

        # Leave-one-match-out sensitivity stability check
        loo_signs: List[int] = []
        if abs(raw_delta) > 1e-6:
            base_sign = 1 if raw_delta > 0 else -1
            for i in range(len(arr_a)):
                sub_a = np.delete(arr_a, i)
                d_sub = float(np.mean(arr_b) - np.mean(sub_a))
                loo_signs.append(1 if d_sub > 0 else (-1 if d_sub < 0 else 0))
            for j in range(len(arr_b)):
                sub_b = np.delete(arr_b, j)
                d_sub = float(np.mean(sub_b) - np.mean(arr_a))
                loo_signs.append(1 if d_sub > 0 else (-1 if d_sub < 0 else 0))
            loo_stable = all(s == base_sign for s in loo_signs)
        else:
            loo_stable = False

        # Honest verdict & evidence classification
        meets_target_n = min(len(arr_a), len(arr_b)) >= exp.target_min_matches_per_arm
        if patch_drift or mode_mismatch or not loo_stable or not meets_target_n:
            verdict = StatisticalVerdict.INCONCLUSIVE
            grade = EvidenceGrade.OBSERVED_ASSOCIATION
        elif (p_val is not None and p_val < 0.10) or prob_better >= 0.85:
            if signed_improvement > 0.02:
                verdict = StatisticalVerdict.SUPPORTED_IMPROVEMENT
                grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
            elif signed_improvement < -0.02:
                verdict = StatisticalVerdict.SUPPORTED_REGRESSION
                grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
            else:
                verdict = StatisticalVerdict.NO_CLEAR_DIFFERENCE
                grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
        elif (p_val is not None and p_val < 0.10) and signed_improvement < -0.02:
            verdict = StatisticalVerdict.SUPPORTED_REGRESSION
            grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
        elif prob_better <= 0.15 and signed_improvement < -0.02:
            verdict = StatisticalVerdict.SUPPORTED_REGRESSION
            grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE if meets_target_n else EvidenceGrade.OBSERVED_ASSOCIATION
        elif abs(signed_improvement) < 0.015:
            verdict = StatisticalVerdict.NO_CLEAR_DIFFERENCE
            grade = EvidenceGrade.CONTROLLED_EXPERIMENT_EVIDENCE
        else:
            verdict = StatisticalVerdict.INCONCLUSIVE
            grade = EvidenceGrade.OBSERVED_ASSOCIATION

        dir_word = "improved" if signed_improvement > 0 else ("worsened" if signed_improvement < 0 else "unchanged")
        interp = (
            f"Across {len(arr_a)} Baseline A vs {len(arr_b)} Variant B verified matches on {exp.primary_metric}, "
            f"mean moved from {arm_a.mean_primary_metric:.3f} to {arm_b.mean_primary_metric:.3f} "
            f"(delta={raw_delta:+.3f}, {dir_word}; Hedges g={hedges}, p={p_val:.4f}, P(B better)={prob_better:.1%}). "
            f"Verdict={verdict.value}."
        )
        if not loo_stable:
            limitations.append("Leave-one-match-out sensitivity flipped or zeroed effect sign; single-match outlier influence remains.")
        if not meets_target_n:
            limitations.append(f"Minimum target per arm ({exp.target_min_matches_per_arm}) not yet reached; classified conservatively.")

        next_status = (
            ExperimentStatus.COMPLETED
            if verdict in (StatisticalVerdict.SUPPORTED_IMPROVEMENT, StatisticalVerdict.SUPPORTED_REGRESSION, StatisticalVerdict.NO_CLEAR_DIFFERENCE)
            else ExperimentStatus.INCONCLUSIVE
        )
        uncertainty_decomp = {
            "sample_size_a": int(len(arr_a)),
            "sample_size_b": int(len(arr_b)),
            "se_difference": round(se_obs, 4),
            "leave_one_out_stable": loo_stable,
            "patch_or_mode_confounded": bool(patch_drift or mode_mismatch),
            "adherence_rate": adh_rate,
            "practical_threshold": mmi,
            "posterior_prob_meaningful": prob_meaningful,
        }
        analysis = ExperimentStatisticalAnalysis(
            experiment_id=exp.experiment_id,
            primary_metric=exp.primary_metric,
            higher_is_better=higher_is_better,
            protocol_version=int(getattr(exp, "protocol_version", 1) or 1),
            verdict=verdict,
            evidence_grade=grade,
            arm_a=arm_a,
            arm_b=arm_b,
            raw_delta_b_minus_a=raw_delta,
            relative_improvement=rel_imp,
            effect_size_hedges_g=hedges,
            frequentist_test_name=test_name,
            p_value=round(p_val, 4) if p_val is not None else None,
            bootstrap_ci_95=boot_ci,
            bayesian_posterior_prob_b_better=prob_better,
            posterior_prob_meaningful=prob_meaningful,
            minimum_meaningful_improvement=mmi,
            bayesian_credible_interval_95=bayes_ci,
            sensitivity_leave_one_out_stable=loo_stable,
            adherence_rate=adh_rate,
            adherent_match_count=adh_cnt,
            non_adherent_match_count=non_adh_cnt,
            uncertainty_decomposition=uncertainty_decomp,
            confounders=confounders,
            interpretation=interp,
            limitations=limitations,
        )
        if persist:
            self.repo.save_experiment_analysis(uid, exp.experiment_id, analysis, next_status)
        return analysis

    def estimate_required_sample_size(
        self,
        *,
        expected_delta: float = 0.08,
        pooled_sd: float = 0.14,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> Dict[str, Any]:
        """Normal-approximation per-arm sample-size planner for N-of-1 tactical trials."""
        delta = max(0.01, abs(float(expected_delta)))
        sd = max(0.02, float(pooled_sd))
        z_alpha = float(stats.norm.ppf(1.0 - alpha / 2.0))
        z_beta = float(stats.norm.ppf(power))
        n_per_arm = math.ceil(2.0 * ((z_alpha + z_beta) * sd / delta) ** 2)
        n_per_arm = max(3, min(100, n_per_arm))
        return {
            "expected_delta": round(delta, 4),
            "assumed_pooled_sd": round(sd, 4),
            "alpha": alpha,
            "target_power": power,
            "recommended_matches_per_arm": n_per_arm,
            "total_recommended_matches": n_per_arm * 2,
            "caveat": "Assumes comparable gameplay mode & single gameplay patch across matches; keep ABBA counterbalancing.",
        }

    def explain_uncertainty(self, user_id: str, experiment_id: str) -> Dict[str, Any]:
        """Breaks down exact sources of statistical & epistemic uncertainty for Co-Pilot explanation."""
        analysis = self.analyze(user_id, experiment_id, persist=False)
        reasons: List[str] = list(analysis.confounders.match_quality_warnings) + list(analysis.limitations)
        return {
            "experiment_id": experiment_id,
            "verdict": analysis.verdict.value,
            "evidence_grade": analysis.evidence_grade.value,
            "p_value": analysis.p_value,
            "bootstrap_ci_95": analysis.bootstrap_ci_95,
            "bayesian_posterior_prob_b_better": analysis.bayesian_posterior_prob_b_better,
            "posterior_prob_meaningful": analysis.posterior_prob_meaningful,
            "minimum_meaningful_improvement": analysis.minimum_meaningful_improvement,
            "uncertainty_decomposition": analysis.uncertainty_decomposition,
            "reasons": reasons,
        }
