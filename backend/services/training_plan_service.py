"""Phase 40J -> Phase 42H: Adaptive Decision-Linked Training Academy & Calibrated BKT.

Supports:
1. All 8 tactical challenge categories mapped to EA FC gameplay situations.
2. Direct linking of Phase 41 pre-action Decision Windows (`hide_outcome_by_default=True`)
   via zero-hindsight `DecisionScenarioService` conversion.
3. Bounded BKT posterior updates strictly separated from live match Skill Rating,
   plus empirical Brier calibration checks over real attempt history.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import (
    DecisionOption,
    EvidenceClipRef,
    ExperimentalBKTState,
    GamerDNAProfile,
    RecurringMistakePattern,
    TrainingExercise,
    TrainingPlan,
)

TRAINING_CATEGORIES: List[str] = [
    "CB_SWITCHING_DISCIPLINE",
    "TRANSITION_REACTION",
    "PASSING_SELECTION",
    "REST_DEFENSE",
    "PRESSING_TIMING",
    "FINISHING_SHOT_SELECTION",
    "WING_OVERLOAD_VS_SWITCH",
    "CONSERVATIVE_BALL_RETENTION",
]

_DRILL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "UNNECESSARY_CB_DISPLACEMENT": {
        "category": "CB_SWITCHING_DISCIPLINE",
        "difficulty": "INTERMEDIATE",
        "skill": "defensive_discipline",
        "title": "Hold Backline Line & Screen with CDM First",
        "scenario": "Opponent progresses toward top of Zone 8. Two central pivots are still recovering; CB faces 1v1 runner.",
        "options": [
            ("HOLD_LINE_CDM", "Right-stick switch to CDM/CM to screen passing lane; leave AI CB holding zone", "HOLD_SHAPE", True, "Preserves rest-defense compact shape and blocks central cutback channel."),
            ("JOCKEY_CONTAIN", "Step back horizontally with L2/LT jockey toward penalty arc while waiting for pivot", "HOLD_SHAPE", True, "Buys recovery time without vacating Zone 14 pocket."),
            ("STEP_OUT_CB", "Drag CB 8m forward toward touchline/midfield ball carrier immediately", "ENGAGE_PRESS", False, "Creates an immediate one-pass gap behind the stepping CB into Goal Zone."),
        ],
        "reasoning": "Following EA FC manual defending mechanics, stepping early with a CB concedes central space cleanly to one-touch through passes.",
        "outcome": "Observed CB displacement yielded central channel opening behind line.",
        "drill": "Skill Games — Defending Positioning + 2v2 Jockey containment without switching to CB until ball enters box.",
    },
    "EXPOSED_CENTRAL_CHANNEL": {
        "category": "TRANSITION_REACTION",
        "difficulty": "INTERMEDIATE",
        "skill": "pivot_screening",
        "title": "Close Zone 8 Passing Pocket in Transition",
        "scenario": "Possession lost near final third; opponent CAM receives free between lines with ST pinning CBs.",
        "options": [
            ("CUT_LANE_PIVOT", "Sprint holding pivot linearly toward D-arc passing corridor before engaging ball", "HOLD_SHAPE", True, "Cuts the vertical spine pass first (lane protection over chasing ball back)."),
            ("SECOND_MAN_CONTAIN", "Track central runner manually while delaying fullback push-up", "HOLD_SHAPE", True, "Prevents isolated 1v1 central ball into striker feet."),
            ("DOUBLE_PRESS_BALL", "Rush both CMs toward ball carrier along sideline", "ENGAGE_PRESS", False, "Leaves Zone 8 completely empty for a simple diagonal switch inside."),
        ],
        "reasoning": "Protecting the central spine forces opponent attacks wider into lower-xT touchline zones.",
        "outcome": "Central corridor lacked a pivot anchor on turnover.",
        "drill": "Practice Arena — 11v11 Counter-Transition defense starting with single pivot protecting Zone 8.",
    },
    "RISKY_PASSING_DECISION": {
        "category": "PASSING_SELECTION",
        "difficulty": "FUNDAMENTAL",
        "skill": "progression_selection",
        "title": "Temporal Occlusion Scan: Bypass Blocked Central Trap",
        "scenario": "Ball carrier faces 2 central pressers (< 2.5m lane clearance); weak-side winger & deep pivot remain open.",
        "options": [
            ("WIDE_OUTLET", "Play firm driven pass out to wide half-space / touchline outlet", "SWITCH_PLAY", True, "Escapes congested trap while keeping team rest-defense intact."),
            ("RECYCLE_PIVOT", "Bounce back one-touch to Holding CDM to reset passing angle", "RECYCLE_POSSESSION", True, "Eliminates high-cost central turnover immediately ahead of your backline."),
            ("FORCE_CENTRAL", "Attempt tight vertical pass directly between two midfielders", "THROUGH_BALL", False, "High interception risk directly triggering an opponent counter-attack."),
        ],
        "reasoning": "Temporal occlusion highlights scanning away-side outlets half a second before press arrival.",
        "outcome": "Forced central corridor pass lost possession under pressure.",
        "drill": "Practice Arena — Two-touch triangle circulation forcing switch after 2 passes in central third.",
    },
    "COUNTER_ATTACK_VULNERABILITY": {
        "category": "REST_DEFENSE",
        "difficulty": "ADVANCED",
        "skill": "rest_defense",
        "title": "Rest-Defense Shape Check Prior to Final-Third Risk",
        "scenario": "Only 2 defenders sit behind the ball while attacking fullback overlaps near opponent box.",
        "options": [
            ("HIGH_PROB_RETAIN", "Maintain ball security / shoot cleanly out-of-play or recycle toward defensive FB", "RECYCLE_POSSESSION", True, "Avoids dead-zone turnover before rest defense reaches 3+ covers."),
            ("CROSS_WIDE_FINISH", "Deliver high-percentage finish/corner attempt cleanly to end phase", "SHOOT", True, "Prevents live transition interception from central pocket."),
            ("DRIBBLE_CONGESTED", "Dribble straight into 3-man central trap while both FBs are high", "PASS_OPTION", False, "Direct transition trigger exposing back two CBs."),
        ],
        "reasoning": "Wait for 3+ rest-defense structure (2 CBs + 1 Holding pivot/FB) before taking high-variance central risks.",
        "outcome": "Turnover caught both fullbacks ahead of ball.",
        "drill": "Tactical check: verify one Fullback on Fullback (Defend) or one Holding CDM (Stay Back) before final-third dribbles.",
    },
    "ISOLATED_STRIKER": {
        "category": "WING_OVERLOAD_VS_SWITCH",
        "difficulty": "INTERMEDIATE",
        "skill": "width_switching",
        "title": "Break Wing Overload Trap vs Switch to Weak Side",
        "scenario": "Overload on right touchline stalls against 3 defenders; ST & far winger hold weak-side half-space.",
        "options": [
            ("TRIGGER_THIRD_MAN", "Trigger L1/LB forward CAM/CM run and hold 1.5s before vertical/switch pass", "PASS_OPTION", True, "Establishes lay-off support triangle within 14m before switch."),
            ("SWITCH_WIDE_RUN", "Cross-field switch to weak-side Inside Forward exploiting 1v1 margin", "SWITCH_PLAY", True, "Opens central isolation space via width stretching."),
            ("HOOF_ISOLATED_ST", "Force low-percentage lob into 1v3 defender pocket immediately", "THROUGH_BALL", False, "Predictable aerial loss without second-ball support nearby."),
        ],
        "reasoning": "Switching out of a touchline trap requires either weak-side runner timing or a central bounce angle first.",
        "outcome": "Overload force isolated striker >25m from closest support.",
        "drill": "Skill Games — Attacking Scenarios + Practice Arena focusing on weak-side L1/RB switch combos.",
    },
    "POOR_PRESSING_TIMING": {
        "category": "PRESSING_TIMING",
        "difficulty": "ADVANCED",
        "skill": "pressing_discipline",
        "title": "Press Trigger Restraint vs Pass-Trap Commitment",
        "scenario": "Opponent CB turns face-up in deep build-up with a free fullback outlet; your winger is 6m away.",
        "options": [
            ("SHADOW_COVER_DELAY", "Curve run to block fullback angle while holding midfield compact line", "HOLD_SHAPE", True, "Forces sideways circulation until team press line catches up."),
            ("TRIGGER_AT_TOUCH", "Wait for heavy back-foot touch before committing RB/R1 teammate press", "HOLD_SHAPE", True, "Synchronizes ball pressure with central lane lock."),
            ("SPRINT_BLIND_CONTAIN", "Hold sprint straight at CB without checking midfield pass shadow", "ENGAGE_PRESS", False, "Gets bypassed by simple one-two breaking the first pressing line."),
        ],
        "reasoning": "Single-player sprinting without shadow-covering passing lanes weakens compact pressing structure.",
        "outcome": "Late solo press opened direct vertical line-breaking pass.",
        "drill": "Practice Arena — Cut-inside shadow press drill without committing lunge tackles outside final third.",
    },
    "LOW_XG_SHOT_SELECTION": {
        "category": "FINISHING_SHOT_SELECTION",
        "difficulty": "INTERMEDIATE",
        "skill": "finishing_selection",
        "title": "Extra Square Pass vs Blocked Long-Range Shot",
        "scenario": "Inside-right edge of box (20m, tight angle, 2 blockers in shot cone); far-post runner arrives inside 6-yard line.",
        "options": [
            ("SQUARE_EXTRA_PASS", "Deliver controlled low ground pass across penalty spot to arriving runner", "PASS_OPTION", True, "Upgrades obstructed low-angle attempt into open central tap-in corridor."),
            ("BALL_ROLL_ANGLE", "Side-step away from nearest blocker before precision finesse finish", "SHOOT", True, "Clears defender block cone while keeping rest defense balanced."),
            ("FORCE_BLOCKED_SHOT", "Strike immediate power shot straight into two squared CB blockers", "SHOOT", False, "High block probability triggering opponent fast-break clearance."),
        ],
        "reasoning": "Shot utility depends heavily on defender block cones inside the penalty arc; extra square passes raise conversion odds.",
        "outcome": "Obstructed early strike deflected into opponent counter.",
        "drill": "Skill Games — Box Cutback & Extra-Pass decision drill before finishing.",
    },
    "CLOCK_MANAGEMENT_TURNOVER": {
        "category": "CONSERVATIVE_BALL_RETENTION",
        "difficulty": "FUNDAMENTAL",
        "skill": "ball_retention",
        "title": "Protect 1-Goal Lead in Final 10 Minutes Without Cheap Loss",
        "scenario": "83rd minute leading +1; opponent switches to Constant Pressure; safe wingback & deep GK angles open.",
        "options": [
            ("SHIELD_AND_SWITCH", "Use L2/LT shield + lateral switch to deep wingback into empty flank", "SWITCH_PLAY", True, "Burns press stamina cleanly while advancing into low-danger flank."),
            ("RECYCLE_DEEP_GK", "Play calm back-pass to keeper to reset wide passing triangle", "RECYCLE_POSSESSION", True, "Bypasses man-marking press with maximum geometric width."),
            ("GREEDY_THROUGH_BALL", "Attempt high-risk first-time through ball into crowded central channel", "THROUGH_BALL", False, "Gives opponent immediate transition equalizer window with disorganized defense."),
        ],
        "reasoning": "Preserving ball security under late high press protects structural lead value over marginal xT gains.",
        "outcome": "Unforced late-game vertical pass conceded transition attack.",
        "drill": "Practice Arena — Keep-ball vs high press maintaining >85% pass safety for 3 game minutes.",
    },
}

_WINDOW_TYPE_TO_CATEGORY: Dict[str, tuple[str, str]] = {
    "PASS_SELECTION": ("PASSING_SELECTION", "progression_selection"),
    "PRESS_TIMING": ("PRESSING_TIMING", "pressing_discipline"),
    "DEFENSIVE_SWITCH": ("CB_SWITCHING_DISCIPLINE", "defensive_discipline"),
    "TRANSITION_REACTION": ("TRANSITION_REACTION", "pivot_screening"),
    "SHOT_SELECTION": ("FINISHING_SHOT_SELECTION", "finishing_selection"),
}


def bkt_update(state: ExperimentalBKTState, is_correct: bool) -> ExperimentalBKTState:
    """Calibrated Bayesian Knowledge Tracing posterior update (bounded slip/guess, practice-only)."""
    p_l = max(0.01, min(0.99, state.p_mastery))
    p_slip = max(0.03, min(0.25, state.p_slip))
    p_guess = max(0.05, min(0.35, state.p_guess))
    p_transit = max(0.05, min(0.30, state.p_transit))

    if is_correct:
        num = p_l * (1.0 - p_slip)
        den = num + (1.0 - p_l) * p_guess
    else:
        num = p_l * p_slip
        den = num + (1.0 - p_l) * (1.0 - p_guess)
    p_given_obs = num / max(1e-6, den)
    posterior = p_given_obs + (1.0 - p_given_obs) * p_transit
    posterior = round(max(0.02, min(0.98, posterior)), 4)

    return ExperimentalBKTState(
        skill_code=state.skill_code,
        p_mastery=posterior,
        p_init=state.p_init,
        p_transit=p_transit,
        p_slip=p_slip,
        p_guess=p_guess,
        attempts_count=state.attempts_count + 1,
        correct_count=state.correct_count + (1 if is_correct else 0),
        practice_only=True,
        status="EXPERIMENTAL_UNVALIDATED_MASTERY",
    )


def evaluate_bkt_calibration(attempt_logs: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Computes empirical Brier score & predicted vs observed accuracy on recorded drill attempts."""
    logs = attempt_logs or []
    scored = [
        a for a in logs
        if a.get("prior_p") is not None and a.get("is_optimal_or_defensible") is not None
    ]
    if not scored:
        return {
            "sample_count": 0,
            "brier_score": None,
            "mean_predicted_prob": None,
            "observed_accuracy": None,
            "calibration_status": "UNVALIDATED_NO_ATTEMPTS",
        }
    n = len(scored)
    brier = sum((float(a["prior_p"]) - (1.0 if a["is_optimal_or_defensible"] else 0.0)) ** 2 for a in scored) / n
    mean_pred = sum(float(a["prior_p"]) for a in scored) / n
    obs_acc = sum(1.0 if a["is_optimal_or_defensible"] else 0.0 for a in scored) / n
    return {
        "sample_count": n,
        "brier_score": round(brier, 4),
        "mean_predicted_prob": round(mean_pred, 4),
        "observed_accuracy": round(obs_acc, 4),
        "calibration_status": "CALIBRATED_PRACTICE_ONLY" if n >= 5 else "PROVISIONAL_LOW_N",
    }


def _action_type_from_family(family: str) -> str:
    fam = (family or "").upper()
    if "SWITCH" in fam:
        return "SWITCH_PLAY"
    if "RETAIN" in fam or "RECYCLE" in fam:
        return "RECYCLE_POSSESSION"
    if "THROUGH" in fam:
        return "THROUGH_BALL"
    if "SHOT" in fam or "FINISH" in fam:
        return "SHOOT"
    if "HOLD" in fam or "COVER" in fam or "CONTAIN" in fam:
        return "HOLD_SHAPE"
    if "PRESS" in fam:
        return "ENGAGE_PRESS"
    return "PASS_OPTION"


class TrainingPlanService:
    """Builds adaptive decision-linked & recurring-mistake practice plans across 8 EA FC skill categories."""

    def generate_plan(
        self,
        user_id: str,
        *,
        game_version: str = "FC27",
        mistakes: List[RecurringMistakePattern],
        dna: GamerDNAProfile,
        existing_bkt: Optional[Dict[str, ExperimentalBKTState]] = None,
        decision_windows: Optional[List[Dict[str, Any]]] = None,
        attempt_logs: Optional[List[Dict[str, Any]]] = None,
    ) -> TrainingPlan:
        bkt = dict(existing_bkt or {})
        exercises: List[TrainingExercise] = []
        objectives: List[str] = []
        categories_covered: List[str] = []
        linked_window_count = 0

        # Stage 1: Link real Phase 41 Decision Windows directly into blind-review challenges (hide_outcome_by_default=True)
        wins = [w for w in (decision_windows or []) if w.get("provenance") != "SYNTHETIC_FIXTURE"]
        wins.sort(key=lambda w: float(w.get("regret_estimate") or 0.0), reverse=True)
        for w in wins[:2]:
            cands = w.get("candidate_actions") or []
            comp = w.get("counterfactual_comparison") or {}
            best_id = comp.get("best_alternative_id")
            if not cands:
                continue
            dtype = str(w.get("decision_type") or "PASS_SELECTION")
            cat, skill_code = _WINDOW_TYPE_TO_CATEGORY.get(dtype, ("PASSING_SELECTION", "progression_selection"))
            bkt.setdefault(skill_code, ExperimentalBKTState(skill_code=skill_code))

            best_u = float(comp.get("best_alternative_utility") or 0.0)
            opts: List[DecisionOption] = []
            def_ids: List[str] = []
            for c in cands[:4]:
                aid = str(c.get("action_id") or "")
                vb = c.get("value_breakdown") or {}
                u = float(vb.get("risk_adjusted_utility") or 0.0)
                is_def = (aid == best_id) or (abs(best_u - u) <= 0.045)
                if is_def:
                    def_ids.append(aid)
                opts.append(
                    DecisionOption(
                        option_id=aid,
                        action_label=str(c.get("label") or aid),
                        action_type=_action_type_from_family(str(c.get("action_family") or "")),
                        heuristic_q_value=round(u, 3),
                        is_observed_choice=bool(c.get("is_observed_choice")),
                        is_defensible=is_def,
                        reasoning=f"Pre-action utility {u:+.3f} (regret {max(0.0, best_u - u):.3f}).",
                    )
                )
            if not def_ids and opts:
                def_ids.append(opts[0].option_id)
                opts[0].is_defensible = True

            ts = float(w.get("action_timestamp_sec") or 0.0)
            wid = str(w.get("window_id") or "WIN")
            reg = float(w.get("regret_estimate") or 0.0)
            diff = "ADVANCED" if reg >= 0.12 else ("INTERMEDIATE" if reg >= 0.05 else "FUNDAMENTAL")

            exercises.append(
                TrainingExercise(
                    exercise_id=f"EX-WIN-{wid[:8]}",
                    title=f"Decision Freeze ({dtype.replace('_', ' ').title()} @ {ts:.1f}s)",
                    category=cat,
                    difficulty=diff,
                    skill_code=skill_code,
                    diagnostic_code=dtype,
                    linked_window_id=wid,
                    hide_outcome_by_default=True,
                    source_clip=EvidenceClipRef(
                        match_id=str(w.get("match_id") or "MATCH"),
                        video_id=w.get("video_id"),
                        timestamp_start=max(0.0, round(ts - 1.2, 2)),
                        timestamp_end=round(ts + 0.8, 2),
                        title=f"Decision Freeze: {dtype.replace('_', ' ').title()}",
                        diagnostic_code=dtype,
                        provenance=str(w.get("provenance") or "USER_SUBMITTED_RECORD"),
                        deep_link=f"/research/decision-lab?match_id={w.get('match_id') or ''}&window_id={wid}",
                    ),
                    freeze_timestamp_sec=max(0.0, round(ts - 0.5, 2)),
                    scenario_summary=(
                        f"Match {w.get('match_id')} at {ts:.1f}s: choose the highest risk/reward pre-action option "
                        f"before knowing the outcome ({len(opts)} candidate actions)."
                    ),
                    options=opts,
                    defensible_option_ids=def_ids,
                    tactical_reasoning=(
                        f"Pre-action evaluation identified {comp.get('best_alternative_label') or 'top option'} "
                        f"with estimated regret delta {reg:.3f}."
                    ),
                    original_outcome="Outcome hidden during blind review until you submit an answer.",
                    in_game_drill="Practice Arena: recreate this exact spatial picture and trigger support run/pass early.",
                )
            )
            linked_window_count += 1
            if cat not in categories_covered:
                categories_covered.append(cat)

        # Stage 2: Ranked recurring mistakes
        ranked_codes: List[tuple[float, RecurringMistakePattern]] = []
        sev_mult = {"HIGH": 1.0, "MEDIUM": 0.72, "LOW": 0.45}
        conf_mult = {"HIGH": 1.0, "MODERATE": 0.85, "LOW": 0.60, "INSUFFICIENT_EVIDENCE": 0.40}
        for m in mistakes:
            s = sev_mult.get(m.severity_estimate, 0.5) * conf_mult.get(m.confidence_level, 0.6) * max(0.08, m.normalized_rate)
            ranked_codes.append((s, m))
        ranked_codes.sort(key=lambda x: x[0], reverse=True)

        seen_skills: set[str] = {ex.skill_code for ex in exercises}
        for _, m in ranked_codes[:4]:
            tpl = _DRILL_TEMPLATES.get(m.diagnostic_code)
            if not tpl:
                if "PRESS" in m.diagnostic_code:
                    tpl = _DRILL_TEMPLATES["POOR_PRESSING_TIMING"]
                elif "COMPACT" in m.diagnostic_code:
                    tpl = _DRILL_TEMPLATES["EXPOSED_CENTRAL_CHANNEL"]
                elif "SHOT" in m.diagnostic_code or "FINISH" in m.diagnostic_code:
                    tpl = _DRILL_TEMPLATES["LOW_XG_SHOT_SELECTION"]
                elif "PASS" in m.diagnostic_code or "POSSESSION" in m.diagnostic_code:
                    tpl = _DRILL_TEMPLATES["RISKY_PASSING_DECISION"]
                elif "WIDTH" in m.diagnostic_code or "OVERLAP" in m.diagnostic_code:
                    tpl = _DRILL_TEMPLATES["ISOLATED_STRIKER"]
                else:
                    tpl = _DRILL_TEMPLATES["COUNTER_ATTACK_VULNERABILITY"]

            skill = tpl["skill"]
            bkt.setdefault(skill, ExperimentalBKTState(skill_code=skill))
            clip: Optional[EvidenceClipRef] = m.supporting_clips[0] if m.supporting_clips else None
            freeze_ts = max(0.0, round((clip.timestamp_start if clip else 12.0) - 0.8, 2))
            opts = []
            defensible_ids = []
            for oid, lbl, atype, is_def, why in tpl["options"]:
                if is_def:
                    defensible_ids.append(oid)
                opts.append(
                    DecisionOption(
                        option_id=oid,
                        action_label=lbl,
                        action_type=atype,
                        is_defensible=is_def,
                        heuristic_q_value=0.72 if is_def else 0.18,
                        reasoning=why,
                    )
                )

            exercises.append(
                TrainingExercise(
                    exercise_id=f"EX-{m.diagnostic_code[:8]}-{len(exercises) + 1}",
                    title=tpl["title"],
                    category=tpl["category"],
                    difficulty=tpl["difficulty"],
                    skill_code=skill,
                    diagnostic_code=m.diagnostic_code,
                    hide_outcome_by_default=True,
                    source_clip=clip,
                    freeze_timestamp_sec=freeze_ts,
                    scenario_summary=tpl["scenario"],
                    options=opts,
                    defensible_option_ids=defensible_ids,
                    tactical_reasoning=tpl["reasoning"],
                    original_outcome=(
                        f"{m.total_occurrences} occurrence(s) across {m.total_opportunities} observable opportunities "
                        f"(rate={m.normalized_rate:.1%})."
                    ),
                    in_game_drill=tpl["drill"],
                )
            )
            if tpl["category"] not in categories_covered:
                categories_covered.append(tpl["category"])
            if skill not in seen_skills:
                seen_skills.add(skill)
                objectives.append(
                    f"Focus next match on {tpl['title']} (target reducing {m.diagnostic_code.replace('_', ' ')} rate below {max(0.05, m.normalized_rate * 0.6):.0%})."
                )

        # Stage 3: Ensure breadth across EA FC tactical categories when exercises < 4 (cold-start or narrow sample)
        fallback_order = [
            "RISKY_PASSING_DECISION",
            "UNNECESSARY_CB_DISPLACEMENT",
            "POOR_PRESSING_TIMING",
            "LOW_XG_SHOT_SELECTION",
            "CLOCK_MANAGEMENT_TURNOVER",
            "COUNTER_ATTACK_VULNERABILITY",
        ]
        for code in fallback_order:
            if len(exercises) >= 4:
                break
            tpl = _DRILL_TEMPLATES[code]
            if tpl["category"] in categories_covered:
                continue
            bkt.setdefault(tpl["skill"], ExperimentalBKTState(skill_code=tpl["skill"]))
            exercises.append(
                TrainingExercise(
                    exercise_id=f"EX-BASELINE-{len(exercises) + 1}",
                    title=tpl["title"],
                    category=tpl["category"],
                    difficulty=tpl["difficulty"],
                    skill_code=tpl["skill"],
                    diagnostic_code=code if mistakes else "COLD_START_BASELINE",
                    hide_outcome_by_default=True,
                    source_clip=None,
                    freeze_timestamp_sec=0.0,
                    scenario_summary=tpl["scenario"] + (" (Baseline drill pending more match footage)." if not mistakes else ""),
                    options=[
                        DecisionOption(
                            option_id=oid,
                            action_label=lbl,
                            action_type=atype,
                            is_defensible=is_def,
                            heuristic_q_value=0.72 if is_def else 0.18,
                            reasoning=why,
                        )
                        for oid, lbl, atype, is_def, why in tpl["options"]
                    ],
                    defensible_option_ids=[o[0] for o in tpl["options"] if o[3]],
                    tactical_reasoning=tpl["reasoning"],
                    original_outcome="Baseline tactical recognition drill (import match telemetry for clip-specific outcomes).",
                    in_game_drill=tpl["drill"],
                )
            )
            categories_covered.append(tpl["category"])

        if not objectives:
            objectives.append("Import a real match recording or tracking trace to personalize training objectives to your exact recurring mistakes.")
        if dna.improvement_potential:
            objectives.append(f"Primary Gamer DNA growth priority: {dna.improvement_potential[0].recommended_focus}")

        return TrainingPlan(
            user_id=user_id,
            game_version="FC26" if game_version.upper() == "FC26" else "FC27",
            next_match_objectives=objectives[:4],
            categories_covered=categories_covered,
            decision_windows_linked=linked_window_count,
            bkt_calibration=evaluate_bkt_calibration(attempt_logs),
            exercises=exercises[:6],
            bkt_states=bkt,
        )
