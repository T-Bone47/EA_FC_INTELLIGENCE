"""Phase 44I: Elite Skill-Gap & Execution-Differential Intelligence Engine.

Strictly preserves the epistemic separation rule:
- Style similarity (Groups A-F) answers WHO plays like whom tactically/behaviorally.
- Elite Skill Gap (Group G Technical Execution + Decision IQ) answers WHERE execution
  precision or decision quality diverges from benchmarks — NEVER conflated into style distance
  and NEVER framed as guaranteed rank or win-rate gains.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from backend.domain.phase44_models import (
    EliteSkillGapItem,
    EliteSkillGapReport,
    GamerStyleVectorV2,
    ProStyleProfileVersion,
)


# Internal proficiency benchmarks when authorized pro reference execution profiles are unavailable.
_INTERNAL_TARGETS: Dict[str, Tuple[float, bool, str, str]] = {
    "pass_success_rate": (
        0.84,
        False,
        "PASSING_SELECTION — High-tempo pass accuracy & press-resistance under tight spacing",
        "Add a short-outlet triangle CM/CDM and curb 1st-time blind passes away from body angle.",
    ),
    "possession_loss_rate": (
        0.22,
        True,  # lower is better
        "CONSERVATIVE_BALL_RETENTION — Shielding, safe recycling & press avoidance",
        "Lower build-up risk against high presses by anchoring a deeper Stay-Back pivot.",
    ),
    "shooting_execution_quality": (
        0.58,
        False,
        "FINISHING_SHOT_SELECTION — High-xG box entry angles & extra square passes",
        "Use Extra-Pass or Ball-Roll angle creation before releasing power shots inside congested box.",
    ),
    "defensive_recovery_success": (
        0.72,
        False,
        "PRESSING_TIMING — Goal-side recovery & shadow-cover pressing discipline",
        "Avoid stepping CBs aggressively beyond midfield line; switch to CM/CDM to track cutbacks.",
    ),
    "decision_regret_inverse": (
        0.76,
        False,
        "PASSING_SELECTION — Pre-action visual scanning & lower counterfactual decision regret",
        "Run 2-3 Decision Replay Lab reviews targeting highest-regret transitions after matches.",
    ),
    "execution_consistency": (
        0.74,
        False,
        "BALL_RETENTION — Reducing variance across match states & late-game fatigue",
        "Pre-configure a Balanced Defensive preset for minutes 70-90 when holding a 1-goal margin.",
    ),
    "opportunity_conversion_rate": (
        0.64,
        False,
        "TRANSITION_REACTION — Capitalizing cleanly on final-third overloads & half-space entries",
        "Assign Inside Forward / Playmaker roles to accelerate third-man arrivals into Zone 14.",
    ),
}


class EliteSkillGapEngine:
    """Computes strictly separated Group G execution strengths and priority improvement gaps."""

    def analyze(
        self,
        user_profile: GamerStyleVectorV2,
        *,
        reference_pro: Optional[ProStyleProfileVersion] = None,
    ) -> EliteSkillGapReport:
        gv = user_profile.game_version
        use_pro = bool(
            reference_pro is not None
            and not reference_pro.is_invalidated
            and reference_pro.rights_status.value in ("RIGHTS_VERIFIED", "RESEARCH_ONLY")
            and reference_pro.game_version == gv
            and reference_pro.proficiency_values
        )
        scope = (
            f"AUTHORIZED_PRO:{reference_pro.public_alias}"
            if use_pro and reference_pro is not None
            else "INTERNAL_EXECUTION_TARGET_BENCHMARK"
        )

        strengths: List[EliteSkillGapItem] = []
        gaps: List[EliteSkillGapItem] = []
        insufficient: List[EliteSkillGapItem] = []

        for dim, (fallback_target, lower_is_better, train_obj, tact_adj) in _INTERNAL_TARGETS.items():
            obs = user_profile.proficiency_features.get(dim)
            user_val = obs.raw_value if obs else None

            if use_pro and reference_pro is not None and isinstance(reference_pro.proficiency_values.get(dim), (int, float)):
                target_val = float(reference_pro.proficiency_values[dim])
                item_scope = scope
            else:
                target_val = fallback_target
                item_scope = "INTERNAL_EXECUTION_TARGET_BENCHMARK"

            if user_val is None or user_profile.eligible_match_count == 0:
                insufficient.append(
                    EliteSkillGapItem(
                        dimension=dim,
                        user_value=None,
                        reference_benchmark_value=round(target_val, 4),
                        skill_gap_estimate=None,
                        status="INSUFFICIENT_EVIDENCE",
                        confidence=0.0,
                        reference_scope=item_scope,
                        suggested_training_objective=train_obj,
                        suggested_tactical_adjustment=tact_adj,
                    )
                )
                continue

            # Positive gap_estimate = amount trailing benchmark (> 0 means weakness gap; < 0 means user exceeds benchmark)
            raw_gap = (user_val - target_val) if lower_is_better else (target_val - user_val)
            gap_est = round(raw_gap, 4)
            conf = round(max(0.15, min(0.95, 1.0 - float(obs.uncertainty or 0.15))), 3) if obs else 0.35

            if raw_gap <= -0.04:
                status = "STRENGTH"
            elif raw_gap >= 0.05:
                status = "GAP_PRIORITY"
            else:
                status = "PARITY"

            item = EliteSkillGapItem(
                dimension=dim,
                user_value=round(user_val, 4),
                reference_benchmark_value=round(target_val, 4),
                skill_gap_estimate=gap_est,
                status=status,  # type: ignore[arg-type]
                confidence=conf,
                reference_scope=item_scope,
                supporting_evidence=list(obs.evidence_references[:5]) if obs else [],
                suggested_training_objective=train_obj,
                suggested_tactical_adjustment=tact_adj,
            )
            if status == "GAP_PRIORITY":
                gaps.append(item)
            else:
                strengths.append(item)

        strengths.sort(key=lambda x: (x.skill_gap_estimate if x.skill_gap_estimate is not None else 0.0))
        gaps.sort(key=lambda x: -(x.skill_gap_estimate if x.skill_gap_estimate is not None else 0.0))

        caveats = [
            "Group G execution proficiency is strictly isolated from Groups A-F playing style similarity.",
            "Closing an execution or decision gap indicates technical skill progress in observed telemetry; it never guarantees competitive rank or match outcomes.",
        ]
        if not use_pro:
            caveats.append(
                "No rights-verified pro execution benchmark is active for this comparison; targets reflect internal analytical proficiency bands."
            )

        return EliteSkillGapReport(
            user_id=user_profile.user_id,
            game_version=gv,
            reference_scope=scope,
            reference_population_verified=use_pro,
            strengths=strengths + insufficient,
            gaps=gaps,
            caveats=caveats,
        )
