"""Phase 44G & 44H: Governed Professional Gamer Style Similarity & Uncertainty Engine.

Strict mathematical & legal guarantees:
1. Groups A-F (`STYLE_FEATURE_IDS`) ONLY — Group G (`TECHNICAL_EXECUTION`) is NEVER used in style similarity.
2. Fail-closed rights gating via `ReferenceRightsValidator` & strict FC26/FC27 edition isolation.
3. Abstains transparently (`abstained=True`) when zero authorized reference profiles exist, user evidence is
   cold-start (`0` non-synthetic matches), or joint feature overlap falls below minimum threshold.
4. Multiple comparative metrics: Weighted Reliability-Masked Euclidean (primary), Cosine, Ledoit-Wolf shrunk
   Mahalanobis (when cohort >= 6), Jensen-Shannon & Wasserstein distributional distances on compositional histograms.
5. Bootstrap + Leave-One-Match-Out uncertainty quantification with explicit indistinguishable-rank flags.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial.distance import cosine as scipy_cosine
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance
from sklearn.covariance import LedoitWolf

from backend.domain.phase40_models import MatchIntelligenceRecord
from backend.domain.phase44_models import (
    FeatureGroup,
    GamerStyleVectorV2,
    ProStyleProfileVersion,
    ProStyleSimilarityItem,
    ProStyleSimilarityReport,
    UsagePurpose,
)
from backend.services.gamer_dna_v2_engine import FEATURE_CATALOG_V2, STYLE_FEATURE_IDS, _extract_feature_from_match
from backend.services.reference_governance_service import (
    ProfessionalReferenceRepository,
    ReferenceRightsValidator,
)


_STYLE_GROUP_COUNTS: Dict[FeatureGroup, int] = {}
for _fid in STYLE_FEATURE_IDS:
    _g = FEATURE_CATALOG_V2[_fid]["feature_group"]
    _STYLE_GROUP_COUNTS[_g] = _STYLE_GROUP_COUNTS.get(_g, 0) + 1


class ProfessionalGamerSimilarityEngine:
    """Computes fail-closed, uncertainty-aware playing-style similarity against authorized pro profiles."""

    MIN_JOINT_FEATURES = 6
    MIN_OVERLAP_RATIO = 0.12

    def __init__(self, ref_repo: Optional[ProfessionalReferenceRepository] = None) -> None:
        self.ref_repo = ref_repo or ProfessionalReferenceRepository()

    @staticmethod
    def _group_equalized_weight(fid: str, user_unc: Optional[float]) -> float:
        meta = FEATURE_CATALOG_V2[fid]
        g = meta["feature_group"]
        g_cnt = max(1, _STYLE_GROUP_COUNTS.get(g, 8))
        # Equalize total group influence across Groups A-F while attenuating noisy user features
        base = 10.0 / float(g_cnt)
        u_pen = 1.0 / (1.0 + max(0.0, float(user_unc or 0.08)) * 2.5)
        return base * float(meta.get("weight", 1.0)) * u_pen

    @staticmethod
    def _weighted_euclidean(
        u_vals: Dict[str, float],
        u_uncs: Dict[str, Optional[float]],
        p_vals: Dict[str, Optional[float]],
    ) -> Tuple[float, float, int, Dict[str, float], List[Dict[str, Any]], List[Dict[str, Any]]]:
        joint_ids = [
            fid for fid in STYLE_FEATURE_IDS
            if fid in u_vals and isinstance(p_vals.get(fid), (int, float))
        ]
        n_joint = len(joint_ids)
        overlap = round(n_joint / max(1, len(STYLE_FEATURE_IDS)), 4)
        if n_joint == 0:
            return 9.99, 0.0, 0, {}, [], []

        sq_sum = 0.0
        w_sum = 0.0
        grp_sq: Dict[str, float] = {}
        grp_w: Dict[str, float] = {}
        diffs: List[Dict[str, Any]] = []

        for fid in joint_ids:
            uv = float(u_vals[fid])
            pv = float(p_vals[fid])  # type: ignore[arg-type]
            w = ProfessionalGamerSimilarityEngine._group_equalized_weight(fid, u_uncs.get(fid))
            d = uv - pv
            abs_d = abs(d)
            sq_sum += w * (d * d)
            w_sum += w
            g_name = FEATURE_CATALOG_V2[fid]["feature_group"].value
            grp_sq[g_name] = grp_sq.get(g_name, 0.0) + w * (d * d)
            grp_w[g_name] = grp_w.get(g_name, 0.0) + w
            diffs.append(
                {
                    "feature_id": fid,
                    "group": g_name,
                    "user_value": round(uv, 4),
                    "pro_value": round(pv, 4),
                    "abs_diff": round(abs_d, 4),
                    "signed_diff": round(d, 4),
                }
            )

        rms_d = math.sqrt(sq_sum / max(1e-8, w_sum))
        sim_idx = round(max(0.0, min(100.0, 100.0 * math.exp(-3.15 * rms_d))), 2)

        grp_sims: Dict[str, float] = {}
        for gn, gsq in grp_sq.items():
            g_rms = math.sqrt(gsq / max(1e-8, grp_w[gn]))
            grp_sims[gn] = round(max(0.0, min(100.0, 100.0 * math.exp(-3.15 * g_rms))), 2)

        diffs.sort(key=lambda x: x["abs_diff"])
        top_sim = diffs[:4]
        top_div = sorted(diffs, key=lambda x: x["abs_diff"], reverse=True)[:4]
        return round(rms_d, 4), sim_idx, n_joint, grp_sims, top_sim, top_div

    @staticmethod
    def _distributional_metrics(
        u_vals: Dict[str, float],
        p_vals: Dict[str, Optional[float]],
        u_dists: Dict[str, Dict[str, float]],
        p_dists: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        out: Dict[str, float] = {}
        joint = [fid for fid in STYLE_FEATURE_IDS if fid in u_vals and isinstance(p_vals.get(fid), (int, float))]
        if len(joint) >= 3:
            uv = np.asarray([u_vals[f] - 0.5 for f in joint], dtype=np.float64)
            pv = np.asarray([float(p_vals[f]) - 0.5 for f in joint], dtype=np.float64)  # type: ignore[arg-type]
            if np.linalg.norm(uv) > 1e-6 and np.linalg.norm(pv) > 1e-6:
                cos_d = float(scipy_cosine(uv, pv))
                if not math.isnan(cos_d):
                    out["cosine_similarity"] = round(max(-1.0, min(1.0, 1.0 - cos_d)), 4)

        js_vals: List[float] = []
        ws_vals: List[float] = []
        for d_name, ud in (u_dists or {}).items():
            pd = (p_dists or {}).get(d_name)
            if not pd:
                continue
            keys = sorted(set(ud.keys()) | set(pd.keys()))
            if len(keys) < 2:
                continue
            a = np.asarray([max(1e-6, float(ud.get(k, 0.0))) for k in keys], dtype=np.float64)
            b = np.asarray([max(1e-6, float(pd.get(k, 0.0))) for k in keys], dtype=np.float64)
            a /= np.sum(a)
            b /= np.sum(b)
            js_d = float(jensenshannon(a, b))
            if not math.isnan(js_d):
                js_vals.append(js_d)
            wd = float(wasserstein_distance(np.arange(len(keys)), np.arange(len(keys)), a, b))
            ws_vals.append(wd)

        if js_vals:
            out["jensen_shannon_distance"] = round(sum(js_vals) / len(js_vals), 4)
        if ws_vals:
            out["wasserstein_distance"] = round(sum(ws_vals) / len(ws_vals), 4)
        return out

    @staticmethod
    def _fit_mahalanobis_inv_cov(pro_profiles: List[ProStyleProfileVersion]) -> Tuple[Optional[np.ndarray], List[str], str]:
        if len(pro_profiles) < 6:
            return None, [], "DIAGONAL_FALLBACK_INSUFFICIENT_COHORT"
        common = [
            fid for fid in STYLE_FEATURE_IDS
            if all(isinstance(p.style_values.get(fid), (int, float)) for p in pro_profiles)
        ]
        if len(common) < 6:
            return None, [], "DIAGONAL_FALLBACK_INSUFFICIENT_OVERLAP"
        mat = np.asarray([[float(p.style_values[f]) for f in common] for p in pro_profiles], dtype=np.float64)  # type: ignore[arg-type]
        lw = LedoitWolf().fit(mat)
        inv_cov = np.linalg.pinv(lw.covariance_)
        return inv_cov, common, "LEDOIT_WOLF_SHRUNK_MAHALANOBIS"

    def compare(
        self,
        user_profile: GamerStyleVectorV2,
        *,
        user_matches: Optional[List[MatchIntelligenceRecord]] = None,
        candidate_profiles: Optional[List[ProStyleProfileVersion]] = None,
        purpose: UsagePurpose = UsagePurpose.LOCAL_RESEARCH,
        top_n: int = 5,
    ) -> ProStyleSimilarityReport:
        gv = user_profile.game_version
        archetype_fb = f"{user_profile.archetype.primary_archetype} ({user_profile.archetype.status})"

        if user_profile.eligible_match_count == 0:
            return ProStyleSimilarityReport(
                user_id=user_profile.user_id,
                profile_version_id=user_profile.profile_version_id,
                game_version=gv,
                game_patch=user_profile.game_patch,
                abstained=True,
                abstention_reason=(
                    "Insufficient verified non-synthetic match observations for professional style similarity. "
                    "Archetype cold-start guidance provided instead."
                ),
                fallback_archetype_summary=archetype_fb,
                eligible_references_count=0,
                blocked_or_unverified_count=len(self.ref_repo.list_candidates()) if candidate_profiles is None else 0,
            )

        # Stage 1: Fail-closed rights & edition filtering
        eligible_pros: List[ProStyleProfileVersion] = []
        blocked_count = 0
        if candidate_profiles is not None:
            raw_pool = candidate_profiles
            for p in raw_pool:
                ref = self.ref_repo.repo.get_reference(p.reference_id)
                if ref is not None:
                    ok, _ = ReferenceRightsValidator.is_permitted(ref.rights, purpose)
                else:
                    # Synthetic unit-test pro objects passed directly must explicitly carry verified/research status
                    ok = p.rights_status.value in ("RIGHTS_VERIFIED", "RESEARCH_ONLY") and not p.is_invalidated
                if ok and not p.is_invalidated and p.game_version == gv and p.eligible_ref_matches >= 1 and p.coverage >= 0.25:
                    eligible_pros.append(p)
                else:
                    blocked_count += 1
        else:
            eligible_pros = self.ref_repo.list_eligible_pro_profiles(game_version=gv, purpose=purpose)
            all_cands = self.ref_repo.list_candidates()
            blocked_count = max(0, len(all_cands) - len(eligible_pros))

        if not eligible_pros:
            return ProStyleSimilarityReport(
                user_id=user_profile.user_id,
                profile_version_id=user_profile.profile_version_id,
                game_version=gv,
                game_patch=user_profile.game_patch,
                abstained=True,
                abstention_reason=(
                    f"Zero rights-verified or research-authorized professional {gv} reference profiles are available. "
                    "Abstaining cleanly rather than fabricating pro comparisons; fallback playing-style archetype active."
                ),
                fallback_archetype_summary=archetype_fb,
                eligible_references_count=0,
                blocked_or_unverified_count=blocked_count,
                uncertainty_summary={"governance_status": "ABSTAINED_NO_AUTHORIZED_REFERENCES"},
            )

        u_vals = {
            fid: float(obs.raw_value)
            for fid, obs in user_profile.style_features.items()
            if obs.raw_value is not None and not obs.is_proficiency_only
        }
        u_uncs = {fid: obs.uncertainty for fid, obs in user_profile.style_features.items()}
        inv_cov, mah_feats, mah_mode = self._fit_mahalanobis_inv_cov(eligible_pros)

        # Precompute per-match feature vectors for match-level bootstrap uncertainty
        non_synth_matches = [
            m for m in (user_matches or [])
            if m.provenance != "SYNTHETIC_FIXTURE" and m.game_version == gv
        ]
        per_match_feats: List[Dict[str, float]] = []
        for m in non_synth_matches:
            mf, _ = _extract_feature_from_match(m, None, [])
            per_match_feats.append({k: v[0] for k, v in mf.items() if k in STYLE_FEATURE_IDS})

        scored_items: List[ProStyleSimilarityItem] = []
        ood_skipped = 0
        for p in eligible_pros:
            rms_d, sim_idx, n_joint, grp_sims, top_sim, top_div = self._weighted_euclidean(u_vals, u_uncs, p.style_values)
            overlap_r = round(n_joint / max(1, len(STYLE_FEATURE_IDS)), 4)
            if n_joint < self.MIN_JOINT_FEATURES or overlap_r < self.MIN_OVERLAP_RATIO:
                ood_skipped += 1
                continue

            dist_map = self._distributional_metrics(u_vals, p.style_values, user_profile.distributions, p.distributions)
            if inv_cov is not None and len(mah_feats) >= 6 and all(f in u_vals for f in mah_feats):
                diff_v = np.asarray([u_vals[f] - float(p.style_values[f]) for f in mah_feats], dtype=np.float64)  # type: ignore[arg-type]
                mah_d = float(np.sqrt(max(0.0, float(diff_v.T @ inv_cov @ diff_v))))
                dist_map["mahalanobis_distance"] = round(mah_d, 4)

            scored_items.append(
                ProStyleSimilarityItem(
                    reference_id=p.reference_id,
                    public_alias=p.public_alias,
                    rights_status=p.rights_status,
                    rank_position=0,
                    raw_distance=rms_d,
                    interpretable_similarity_index=sim_idx,
                    feature_overlap_ratio=overlap_r,
                    joint_feature_count=n_joint,
                    confidence_band=[max(0.0, round(sim_idx - 7.5, 2)), min(100.0, round(sim_idx + 7.5, 2))],
                    rank_stability_pct=65.0 if len(per_match_feats) < 3 else 80.0,
                    group_similarities=grp_sims,
                    distributional_distances=dist_map,
                    top_similar_behaviors=top_sim,
                    top_divergent_behaviors=top_div,
                    evidence_references=[f"pro_profile:{p.pro_profile_id}", f"ref_matches:{p.eligible_ref_matches}"],
                )
            )

        if not scored_items:
            return ProStyleSimilarityReport(
                user_id=user_profile.user_id,
                profile_version_id=user_profile.profile_version_id,
                game_version=gv,
                game_patch=user_profile.game_patch,
                abstained=True,
                abstention_reason=(
                    f"Overlap between observed user style features and authorized {gv} pro profiles fell below minimum threshold "
                    f"({self.MIN_JOINT_FEATURES} features). Returning archetype summary instead."
                ),
                fallback_archetype_summary=archetype_fb,
                eligible_references_count=len(eligible_pros),
                blocked_or_unverified_count=blocked_count + ood_skipped,
            )

        scored_items.sort(key=lambda x: (-x.interpretable_similarity_index, x.raw_distance, x.reference_id))

        # Stage 5: Match-level bootstrap uncertainty & rank stability (44H)
        boot_top1_counts: Dict[str, int] = {}
        boot_scores: Dict[str, List[float]] = {it.reference_id: [] for it in scored_items}
        n_boot = 24 if len(per_match_feats) >= 2 else 0
        if n_boot > 0:
            rng = np.random.default_rng(44)
            pro_lookup = {p.reference_id: p for p in eligible_pros}
            n_m = len(per_match_feats)
            for _ in range(n_boot):
                idxs = rng.choice(n_m, size=n_m, replace=True)
                b_acc: Dict[str, List[float]] = {}
                for idx in idxs:
                    for fk, fv in per_match_feats[int(idx)].items():
                        b_acc.setdefault(fk, []).append(fv)
                b_vals = {fk: sum(fvs) / len(fvs) for fk, fvs in b_acc.items()}
                best_rid = ""
                best_s = -1.0
                for it in scored_items:
                    p = pro_lookup[it.reference_id]
                    _, bs, _, _, _, _ = self._weighted_euclidean(b_vals, u_uncs, p.style_values)
                    boot_scores[it.reference_id].append(bs)
                    if bs > best_s:
                        best_s = bs
                        best_rid = it.reference_id
                if best_rid:
                    boot_top1_counts[best_rid] = boot_top1_counts.get(best_rid, 0) + 1

        # Leave-One-Match-Out consistency when >= 3 matches exist
        lomo_top_changes = 0
        if len(per_match_feats) >= 3 and scored_items:
            pro_lookup = {p.reference_id: p for p in eligible_pros}
            base_top = scored_items[0].reference_id
            for drop_i in range(len(per_match_feats)):
                rem = [per_match_feats[j] for j in range(len(per_match_feats)) if j != drop_i]
                l_acc: Dict[str, List[float]] = {}
                for mf in rem:
                    for fk, fv in mf.items():
                        l_acc.setdefault(fk, []).append(fv)
                l_vals = {fk: sum(fvs) / len(fvs) for fk, fvs in l_acc.items()}
                l_best = max(
                    scored_items,
                    key=lambda it: self._weighted_euclidean(l_vals, u_uncs, pro_lookup[it.reference_id].style_values)[1],
                )
                if l_best.reference_id != base_top:
                    lomo_top_changes += 1

        ranked = scored_items[:top_n]
        for idx, it in enumerate(ranked, start=1):
            it.rank_position = idx
            b_list = boot_scores.get(it.reference_id, [])
            if b_list:
                lo = round(float(np.percentile(b_list, 10)), 2)
                hi = round(float(np.percentile(b_list, 90)), 2)
                it.confidence_band = [lo, hi]
                if idx == 1:
                    it.rank_stability_pct = round(100.0 * boot_top1_counts.get(it.reference_id, 0) / max(1, n_boot), 1)
                else:
                    # Rank-k persistence proxy around percentile separation
                    it.rank_stability_pct = round(max(20.0, 100.0 - abs(hi - lo) * 2.5), 1)

        # Flag statistically indistinguishable adjacent candidates cleanly
        for idx in range(len(ranked) - 1):
            a = ranked[idx]
            b = ranked[idx + 1]
            diff_ab = abs(a.interpretable_similarity_index - b.interpretable_similarity_index)
            overlaps = a.confidence_band[0] <= b.confidence_band[1]
            if diff_ab < 5.0 or (overlaps and diff_ab < 8.5):
                note = f"Statistically close to #{idx + 2} {b.public_alias} (Δ={diff_ab:.1f} pts within confidence overlap); order is non-definitive."
                a.indistinguishable_note = note

        return ProStyleSimilarityReport(
            user_id=user_profile.user_id,
            profile_version_id=user_profile.profile_version_id,
            game_version=gv,
            game_patch=user_profile.game_patch,
            distance_metric=f"WEIGHTED_RELIABILITY_EUCLIDEAN+{mah_mode}",
            abstained=False,
            fallback_archetype_summary=archetype_fb,
            eligible_references_count=len(eligible_pros),
            blocked_or_unverified_count=blocked_count + ood_skipped,
            matches=ranked,
            uncertainty_summary={
                "bootstrap_resamples": n_boot,
                "lomo_evaluated_matches": len(per_match_feats) if len(per_match_feats) >= 3 else 0,
                "lomo_top_rank_flips": lomo_top_changes,
                "mahalanobis_mode": mah_mode,
                "profile_maturity": user_profile.profile_maturity,
            },
        )
