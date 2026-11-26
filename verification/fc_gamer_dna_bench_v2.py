"""FC_GAMER_DNA_BENCH_V2 — Phase 44 Reproducible Research & Engineering Benchmark.

Evaluates 5 scientific pillars without fake pro profiles or data leakage:
A. Feature Correctness & Epistemic Separation (60 features, missing=None, synthetic excluded, Group G isolated)
B. Style Identity Separability & Split Stability (leak-free scaler fit on train split only)
C. Governed Similarity Ranking, OOD Abstention & Rights Revocation (controlled benchmark cohort + fail-closed gate)
D. Empirical Unsupervised Clustering Gate (insufficient n=10 vs validated n=40 silhouette/bootstrap stability)
E. Style-Aware Recommendation & Constraint Parity (frozen V3.2.1 untouched, MARKET_PRICE_UNAVAILABLE honest)
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from backend.domain.phase40_models import MatchIntelligenceRecord
from backend.domain.phase44_models import (
    ProStyleProfileVersion,
    ProfessionalGamerReference,
    ReferenceMatchRecord,
    ReferenceRightsRecord,
    RightsStatus,
    StyleSandboxRequest,
    UsagePurpose,
)
from backend.repositories.phase44_repository import Phase44Repository
from backend.services.gamer_dna_v2_engine import (
    FEATURE_CATALOG_V2,
    PROFICIENCY_FEATURE_IDS,
    STYLE_FEATURE_IDS,
    GamerDNAV2Engine,
    StyleArchetypeEngine,
)
from backend.services.professional_similarity_engine import ProfessionalGamerSimilarityEngine
from backend.services.reference_governance_service import (
    ProfessionalReferenceRepository,
    ReferenceRightsValidator,
)
from backend.services.style_squad_training_bridge import (
    PlayingStyleSandbox,
    StyleAwareRecommendationService,
)


_ARCHETYPE_PROTOS: Dict[str, Dict[str, float]] = {
    "Possession Architect": {
        "possession_share": 0.68, "pass_accuracy": 0.90, "pressing_intensity": 0.45,
        "defensive_compactness": 0.72, "defensive_transition_management": 0.74, "central_progression": 0.65,
        "short_pass_preference": 0.85, "long_pass_preference": 0.14, "backward_pass_frequency": 0.28,
        "lateral_circulation": 0.44, "direct_progression": 0.30, "build_up_speed": 0.34,
        "central_attacking_preference": 0.72, "wide_attacking_preference": 0.32, "through_ball_preference": 0.38,
        "counter_attacking_behaviour": 0.20, "attacking_transition_speed": 0.32, "risk_taking_preference": 0.28,
        "safer_alternative_preference": 0.80, "passing_network_density": 0.80,
    },
    "Direct Attacking Specialist": {
        "possession_share": 0.48, "pass_accuracy": 0.80, "pressing_intensity": 0.56,
        "defensive_compactness": 0.62, "defensive_transition_management": 0.60, "central_progression": 0.64,
        "short_pass_preference": 0.44, "long_pass_preference": 0.72, "backward_pass_frequency": 0.10,
        "lateral_circulation": 0.18, "direct_progression": 0.88, "build_up_speed": 0.84,
        "central_attacking_preference": 0.68, "wide_attacking_preference": 0.45, "through_ball_preference": 0.70,
        "counter_attacking_behaviour": 0.64, "attacking_transition_speed": 0.78, "risk_taking_preference": 0.74,
        "safer_alternative_preference": 0.35, "passing_network_density": 0.52,
    },
    "Counter-Attacking Specialist": {
        "possession_share": 0.39, "pass_accuracy": 0.79, "pressing_intensity": 0.36,
        "defensive_compactness": 0.80, "defensive_transition_management": 0.76, "central_progression": 0.50,
        "short_pass_preference": 0.48, "long_pass_preference": 0.66, "backward_pass_frequency": 0.12,
        "lateral_circulation": 0.22, "direct_progression": 0.76, "build_up_speed": 0.80,
        "central_attacking_preference": 0.52, "wide_attacking_preference": 0.62, "through_ball_preference": 0.72,
        "counter_attacking_behaviour": 0.88, "attacking_transition_speed": 0.88, "risk_taking_preference": 0.66,
        "safer_alternative_preference": 0.45, "defensive_line_depth": 0.34,
    },
    "High-Pressing Aggressor": {
        "possession_share": 0.58, "pass_accuracy": 0.82, "pressing_intensity": 0.90,
        "defensive_compactness": 0.64, "defensive_transition_management": 0.62, "central_progression": 0.66,
        "short_pass_preference": 0.64, "long_pass_preference": 0.35, "backward_pass_frequency": 0.14,
        "lateral_circulation": 0.28, "direct_progression": 0.68, "build_up_speed": 0.74,
        "central_attacking_preference": 0.64, "wide_attacking_preference": 0.54, "through_ball_preference": 0.60,
        "counter_attacking_behaviour": 0.52, "attacking_transition_speed": 0.68, "risk_taking_preference": 0.64,
        "defensive_line_depth": 0.85, "out_of_possession_block_height": 0.82, "defensive_contain_vs_step_preference": 0.24,
    },
    "Wing-Based Creator": {
        "possession_share": 0.56, "pass_accuracy": 0.84, "pressing_intensity": 0.55,
        "defensive_compactness": 0.68, "defensive_transition_management": 0.66, "central_progression": 0.40,
        "short_pass_preference": 0.62, "long_pass_preference": 0.54, "backward_pass_frequency": 0.20,
        "lateral_circulation": 0.42, "direct_progression": 0.55, "build_up_speed": 0.58,
        "central_attacking_preference": 0.32, "wide_attacking_preference": 0.88, "through_ball_preference": 0.42,
        "crossing_preference": 0.82, "attacking_width": 0.86, "in_possession_width_expansion": 0.78,
    },
}


def _synth_bench_match(
    user_id: str,
    match_id: str,
    proto: Dict[str, float],
    rng: np.random.Generator,
    idx: int,
    *,
    gv: str = "FC27",
) -> MatchIntelligenceRecord:
    fm: Dict[str, Any] = {}
    for k, v in proto.items():
        fm[k] = round(max(0.02, min(0.98, float(v + rng.normal(0.0, 0.025)))), 4)
    ts = (datetime.now(timezone.utc) - timedelta(days=10 - idx)).isoformat()
    return MatchIntelligenceRecord(
        match_id=match_id,
        user_id=user_id,
        provenance="BENCHMARK_CONTROLLED_FIXTURE",
        game_version=gv,  # type: ignore[arg-type]
        game_patch="PATCH_1.04",
        formation="4-2-3-1",
        tracking_coverage_pct=88.0,
        observation_quality="HIGH",
        feature_metrics=fm,
        opponent_context={"pressing_intensity": 0.55},
        created_at=ts,
    )


def run_benchmark(save_json: bool = True) -> Dict[str, Any]:
    rng = np.random.default_rng(44)
    engine = GamerDNAV2Engine()
    arch_engine = StyleArchetypeEngine()

    # Section A: Feature Correctness & Group G Isolation
    assert len(FEATURE_CATALOG_V2) == 60
    assert len(STYLE_FEATURE_IDS) == 53
    assert len(PROFICIENCY_FEATURE_IDS) == 7

    sparse_m = MatchIntelligenceRecord(
        match_id="BENCH-SPARSE-1",
        user_id="bench-u-sparse",
        provenance="USER_SUBMITTED_RECORD",
        game_version="FC27",
        feature_metrics={"possession_share": 0.61},
        tracking_coverage_pct=65.0,
        observation_quality="MODERATE",
    )
    synth_m = MatchIntelligenceRecord(
        match_id="BENCH-SYNTH-ONLY",
        user_id="bench-u-sparse",
        provenance="SYNTHETIC_FIXTURE",
        game_version="FC27",
        feature_metrics={"possession_share": 0.99, "pressing_intensity": 0.99},
        tracking_coverage_pct=95.0,
        observation_quality="HIGH",
    )
    sparse_prof = engine.build_profile("bench-u-sparse", [sparse_m, synth_m], game_version="FC27")
    assert sparse_prof.synthetic_excluded_count == 1
    assert sparse_prof.eligible_match_count == 1
    assert sparse_prof.style_features["crossing_preference"].raw_value is None
    assert sparse_prof.style_features["pressing_tendency"].raw_value is None  # Did not leak from SYNTHETIC_FIXTURE
    section_a = {
        "total_features": len(FEATURE_CATALOG_V2),
        "style_features": len(STYLE_FEATURE_IDS),
        "proficiency_features": len(PROFICIENCY_FEATURE_IDS),
        "missing_stays_null": sparse_prof.style_features["crossing_preference"].raw_value is None,
        "synthetic_excluded": sparse_prof.synthetic_excluded_count == 1,
        "group_g_isolated": all(v.is_proficiency_only for v in sparse_prof.proficiency_features.values()),
        "passed": True,
    }

    # Section B: Identity Separability & Leak-Free Split Scaler
    arch_names = list(_ARCHETYPE_PROTOS.keys())
    train_vecs: List[Dict[str, float | None]] = []
    cohort_profiles: List[tuple[str, Any]] = []
    correct_cls = 0
    split_cosines: List[float] = []

    for a_i, a_name in enumerate(arch_names):
        proto = _ARCHETYPE_PROTOS[a_name]
        for g_i in range(8):
            uid = f"bench-{a_i}-{g_i}"
            ms = [_synth_bench_match(uid, f"BM-{a_i}-{g_i}-{k}", proto, rng, k) for k in range(6)]
            p_half1 = engine.build_profile(uid, ms[:3], game_version="FC27")
            p_half2 = engine.build_profile(uid, ms[3:], game_version="FC27")
            if g_i < 4:
                train_vecs.append({k: v.raw_value for k, v in p_half1.style_features.items()})
            # Compare half1 vs half2 stability on observed shared features
            ks = [k for k in STYLE_FEATURE_IDS if p_half1.style_features[k].raw_value is not None and p_half2.style_features[k].raw_value is not None]
            v1 = np.asarray([p_half1.style_features[k].raw_value for k in ks], dtype=np.float64)
            v2 = np.asarray([p_half2.style_features[k].raw_value for k in ks], dtype=np.float64)
            cos = float(np.dot(v1, v2) / max(1e-8, np.linalg.norm(v1) * np.linalg.norm(v2)))
            split_cosines.append(cos)

            full_p = engine.build_profile(uid, ms, game_version="FC27")
            if full_p.archetype.primary_archetype == a_name:
                correct_cls += 1
            cohort_profiles.append((a_name, full_p))

    scaler_stats = engine.fit_robust_scaler_stats(train_vecs)
    test_scaled_p = engine.build_profile(
        "bench-eval", [_synth_bench_match("bench-eval", "BME-1", _ARCHETYPE_PROTOS["Possession Architect"], rng, 0)],
        fit_scaler_stats=scaler_stats, scaler_fit_split="TRAIN_PROFILES_ONLY",
    )
    top1_acc = correct_cls / len(cohort_profiles)
    mean_split_cos = sum(split_cosines) / len(split_cosines)
    section_b = {
        "gamers_evaluated": len(cohort_profiles),
        "archetype_top1_accuracy": round(top1_acc, 4),
        "mean_within_gamer_split_cosine": round(mean_split_cos, 4),
        "scaler_fit_split_tracked": test_scaled_p.scaler_fit_split,
        "passed": top1_acc >= 0.90 and mean_split_cos >= 0.95,
    }

    # Section C: Similarity Ranking, Fail-Closed Abstention & Revocation (controlled benchmark only)
    mem_repo = Phase44Repository(force_memory=True)
    ref_repo = ProfessionalReferenceRepository(mem_repo)
    sim_eng = ProfessionalGamerSimilarityEngine(ref_repo)

    # First verify seeded real registry (0 authorized) abstains strictly
    empty_pro_rep = sim_eng.compare(cohort_profiles[0][1])
    assert empty_pro_rep.abstained is True

    # Now authorize a controlled benchmark pool inside memory-only test repo
    bench_pro_profiles: List[ProStyleProfileVersion] = []
    for idx_a, a_name in enumerate(arch_names):
        rid = f"BENCH-PRO-{idx_a}"
        ref = ProfessionalGamerReference(
            reference_id=rid, public_alias=f"BenchPro-{a_name[:8]}", dataset_version="bench.v1",
            reference_match_count=5, evidence_quality="HIGH", profile_coverage=0.85,
            rights_status=RightsStatus.RESEARCH_ONLY,
        )
        rights = ReferenceRightsRecord(
            reference_id=rid, rights_status=RightsStatus.RESEARCH_ONLY,
            allow_local_research=True, allow_feature_extraction=True, verified_by="BENCH_HARNESS",
        )
        mem_repo.upsert_reference(ref, rights)
        canonical_pro_p = engine.build_profile(
            rid,
            [_synth_bench_match(rid, f"{rid}-SRC-{k}", _ARCHETYPE_PROTOS[a_name], rng, k) for k in range(3)],
            game_version="FC27",
        )
        canonical_style = {k: v.raw_value for k, v in canonical_pro_p.style_features.items() if v.raw_value is not None}
        for m_k in range(3):
            mem_repo.add_reference_match(
                ReferenceMatchRecord(
                    reference_id=rid, game_version="FC27", game_patch="PATCH_1.04",
                    coverage_pct=85.0,
                    feature_payload={"style_features": canonical_style, "distributions": canonical_pro_p.distributions},
                    provenance="BENCHMARK_RESEARCH_ONLY",
                )
            )
        built_pro = ref_repo.profile_builder.build_profile(rid, game_version="FC27", game_patch="PATCH_1.04")
        assert built_pro is not None
        bench_pro_profiles.append(built_pro)

    sim_hits = 0
    for expected_arch, g_prof in cohort_profiles:
        rep = sim_eng.compare(g_prof, top_n=3)
        if not rep.abstained and rep.matches and f"BenchPro-{expected_arch[:8]}" == rep.matches[0].public_alias:
            sim_hits += 1
    sim_top1_recall = sim_hits / len(cohort_profiles)

    # Verify FC26 firewall isolates FC27 pros
    fc26_user_p = engine.build_profile(
        "bench-fc26", [_synth_bench_match("bench-fc26", "B26-1", _ARCHETYPE_PROTOS["Possession Architect"], rng, 0, gv="FC26")],
        game_version="FC26",
    )
    fc26_rep = sim_eng.compare(fc26_user_p)
    assert fc26_rep.abstained is True

    # Verify revocation immediately removes candidate
    ref_repo.revoke_rights("BENCH-PRO-0", reason="Benchmark revocation test")
    post_revoke_list = ref_repo.list_eligible_pro_profiles(game_version="FC27")
    assert all(p.reference_id != "BENCH-PRO-0" for p in post_revoke_list)
    ok_after, _ = ReferenceRightsValidator.is_permitted(mem_repo.get_reference("BENCH-PRO-0").rights, UsagePurpose.LOCAL_RESEARCH)
    assert ok_after is False

    section_c = {
        "real_registry_zero_auth_abstained": empty_pro_rep.abstained,
        "controlled_pro_top1_recall": round(sim_top1_recall, 4),
        "edition_firewall_fc26_vs_fc27_abstained": fc26_rep.abstained,
        "revocation_immediate_invalidation": True,
        "passed": empty_pro_rep.abstained and sim_top1_recall >= 0.90 and fc26_rep.abstained,
    }

    # Section D: Unsupervised Empirical Clustering Gate
    mat_small = np.asarray([[float(p.style_features[f].raw_value or 0.5) for f in STYLE_FEATURE_IDS[:15]] for _, p in cohort_profiles[:10]])
    gate_small = arch_engine.evaluate_unsupervised_clusters(mat_small)
    mat_full = np.asarray([[float(p.style_features[f].raw_value or 0.5) for f in STYLE_FEATURE_IDS[:18]] for _, p in cohort_profiles])
    gate_full = arch_engine.evaluate_unsupervised_clusters(mat_full, k_range=(3, 4, 5))
    best_cluster = gate_full.get("best") or {}
    section_d = {
        "small_n10_gate_status": gate_small["status"],
        "full_n40_status": gate_full["status"],
        "best_algorithm": best_cluster.get("algorithm"),
        "best_k": best_cluster.get("k"),
        "silhouette_score": best_cluster.get("silhouette_score"),
        "bootstrap_stability": best_cluster.get("bootstrap_stability"),
        "passed": (
            gate_small["status"] == "INSUFFICIENT_PROFILES_FOR_EMPIRICAL_CLUSTERING"
            and gate_full["status"] == "VALIDATED_EMPIRICAL_CLUSTERING"
            and float(best_cluster.get("silhouette_score") or 0.0) >= 0.25
        ),
    }

    # Section E: Style-Aware Recommendation & Sandbox Constraint Parity
    rec_svc = StyleAwareRecommendationService()
    rec_support = rec_svc.recommend_players("bench-u-sparse", game_version="FC27", position="CM", mode="SUPPORT_NATURAL_STYLE", limit=4)
    sandbox = PlayingStyleSandbox().preview(
        "bench-u-sparse",
        StyleSandboxRequest(game_version="FC27", sandbox_mode="SUPPORT_NATURAL_POSSESSION", convert_to_experiment=False),
    )
    section_e = {
        "frozen_v321_weights_altered": rec_support["frozen_v321_weights_altered"],
        "market_price_status": rec_support["market_price_status"],
        "sandbox_constraints_verified": sandbox["hard_constraints_verified"],
        "sandbox_non_mutating": sandbox["non_mutating_preview"],
        "passed": (
            not rec_support["frozen_v321_weights_altered"]
            and rec_support["market_price_status"] == "MARKET_PRICE_UNAVAILABLE"
            and all(sandbox["hard_constraints_verified"].values())
        ),
    }

    report = {
        "benchmark": "FC_GAMER_DNA_BENCH_V2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_bench_only": True,
        "note": "Pro benchmark references in Section C are isolated memory-only synthetic vectors used exclusively to validate distance/ranking/revocation math; real pro registry remains empty & abstaining.",
        "sections": {
            "A_feature_correctness": section_a,
            "B_style_identity_separability": section_b,
            "C_similarity_and_governance": section_c,
            "D_unsupervised_clustering_gate": section_d,
            "E_style_squad_constraint_parity": section_e,
        },
        "all_sections_passed": all(s["passed"] for s in (section_a, section_b, section_c, section_d, section_e)),
    }
    if save_json:
        out_path = Path("artifacts/phase44/fc_gamer_dna_bench_v2_results.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    res = run_benchmark(save_json=True)
    print(json.dumps(res, indent=2))
    assert res["all_sections_passed"], "FC_GAMER_DNA_BENCH_V2 failed one or more gates!"
