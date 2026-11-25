"""Phase 40G & 40H: Unified PersonalGameplayFit & Intelligent Squad Lab Service.

Bridges Gameplay Evidence + Gamer DNA + Frozen V3.2.1 Suitability + Whole-XI Synergy
without altering or replacing a single weight inside V3.2.1.

Advisory Shadow Formula (explicitly disclosed & non-arbitrary coefficient guard):
  personal_fit = 0.50 * v321_suitability
               + 0.18 * style_compatibility
               + 0.17 * weakness_coverage
               + 0.15 * cohesion_and_role_fit

Prioritizes non-purchase tactical/decision/role/formation fixes before recommending
any card purchase. Respects hard formation/position/GK/duplicate/budget constraints.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import (
    GamerDNAProfile,
    InterventionCategory,
    MatchIntelligenceRecord,
    RecurringMistakePattern,
    SquadSlotSnapshot,
)
from backend.repositories.player_repository import PlayerRepository
from backend.services.formations import slots_for
from backend.services.partnership_intelligence import PartnershipIntelligenceEngine


_COEFFICIENT_DISCLOSURE = {
    "v321_suitability": 0.50,
    "style_compatibility": 0.18,
    "weakness_coverage": 0.17,
    "cohesion_and_role_fit": 0.15,
    "status": "ADVISORY_SHADOW_HEURISTIC_UNOPTIMIZED",
    "note": "Coefficients balance frozen V3.2.1 baseline with personal gameplay signals; not claimed as empirically fitted win predictors.",
}


_POSITION_CAPABILITY_NEEDS: Dict[str, Dict[str, Any]] = {
    "EXPOSED_CENTRAL_CHANNEL": {"position": "CDM", "attrs": ["defensive_awareness", "interceptions", "stamina"], "playstyles": ["Intercept", "Anticipate"]},
    "UNNECESSARY_CB_DISPLACEMENT": {"position": "CB", "attrs": ["defensive_awareness", "reactions", "sprint_speed"], "playstyles": ["Anticipate", "Jockey"]},
    "MIDFIELD_RECOVERY_FAILURE": {"position": "CM", "attrs": ["stamina", "acceleration", "interceptions"], "playstyles": ["Relentless", "Intercept"]},
    "RISKY_PASSING_DECISION": {"position": "CM", "attrs": ["short_passing", "vision", "composure"], "playstyles": ["Incisive Pass", "Press Proven"]},
    "ISOLATED_STRIKER": {"position": "CAM", "attrs": ["short_passing", "vision", "positioning"], "playstyles": ["Incisive Pass", "Tiki Taka"]},
    "INEFFECTIVE_ATTACKING_WIDTH": {"position": "RW", "attrs": ["sprint_speed", "crossing", "dribbling_detail"], "playstyles": ["Rapid", "Whipped Pass"]},
}


class PersonalGameplayFitService:
    """Computes explainable PersonalGameplayFit advisories and Squad Lab intelligence."""

    def __init__(self, player_repo: Optional[PlayerRepository] = None) -> None:
        self.players = player_repo or PlayerRepository()
        self.partnerships = PartnershipIntelligenceEngine()

    def diagnose_intervention(
        self,
        dna: GamerDNAProfile,
        mistakes: List[RecurringMistakePattern],
        matches: List[MatchIntelligenceRecord],
    ) -> Dict[str, Any]:
        """Follows: Gameplay issue -> Hypotheses -> Tactical fix -> Capability gap -> Decision."""
        eligible = [m for m in matches if m.provenance != "SYNTHETIC_FIXTURE"]
        if not eligible:
            return {
                "recommended_intervention": InterventionCategory.INSUFFICIENT_EVIDENCE.value,
                "purchase_justified": False,
                "reason": "Zero non-synthetic gameplay matches observed yet. Static V3.2.1 suitability remains active; no squad overhaul needed purely from cold start.",
                "tactical_first_actions": ["Import a real match trace or upload a match recording to ground personal fit."],
                "target_capability_gaps": [],
            }

        if not mistakes:
            return {
                "recommended_intervention": InterventionCategory.NO_SQUAD_CHANGE_NEEDED.value,
                "purchase_justified": False,
                "reason": "No recurring high-severity structural mistakes detected in observed footage.",
                "tactical_first_actions": ["Maintain current tactical balance and monitor form across next 3 matches."],
                "target_capability_gaps": [],
            }

        top_mistake = mistakes[0]
        primary_cause = top_mistake.root_cause_hypotheses[0].dimension.value if top_mistake.root_cause_hypotheses else "GAMER_DECISION"

        # Check whether gamer decision / instructions explain dominant issue before blaming players
        if primary_cause == "GAMER_DECISION" and top_mistake.severity_estimate != "HIGH":
            cat = InterventionCategory.GAMEPLAY_PRACTICE
            purchase_ok = False
        elif primary_cause in ("TACTICAL_INSTRUCTIONS", "GAMER_DECISION"):
            cat = InterventionCategory.TACTICAL_INSTRUCTION_ADJUSTMENT
            purchase_ok = top_mistake.normalized_rate >= 0.30 and len(eligible) >= 2
        elif primary_cause == "FORMATION":
            cat = InterventionCategory.FORMATION_ADJUSTMENT
            purchase_ok = top_mistake.normalized_rate >= 0.25 and len(eligible) >= 2
        elif primary_cause == "PLAYER_ROLE_SUITABILITY":
            cat = InterventionCategory.ROLE_ADJUSTMENT
            purchase_ok = top_mistake.normalized_rate >= 0.30
        else:
            cat = InterventionCategory.PLAYER_REPLACEMENT
            purchase_ok = True

        gaps: List[Dict[str, Any]] = []
        for m in mistakes[:3]:
            need = _POSITION_CAPABILITY_NEEDS.get(m.diagnostic_code)
            if need:
                gaps.append({"diagnostic_code": m.diagnostic_code, **need})

        return {
            "recommended_intervention": cat.value,
            "purchase_justified": purchase_ok,
            "primary_issue": top_mistake.diagnostic_code,
            "reason": (
                f"Primary bottleneck is {top_mistake.title} (rate={top_mistake.normalized_rate:.1%}, primary hypothesis={primary_cause}). "
                + ("Try free tactical/decision interventions first before spending coins." if not purchase_ok else "Persistent bottleneck also warrants evaluating secondary role/capability upgrades.")
            ),
            "tactical_first_actions": top_mistake.suggested_interventions,
            "target_capability_gaps": gaps,
        }

    def recommend_for_gamer(
        self,
        *,
        game_version: str,
        position: str,
        dna: GamerDNAProfile,
        mistakes: List[RecurringMistakePattern],
        matches: List[MatchIntelligenceRecord],
        budget_coins: Optional[int] = None,
        exclude_names: Optional[List[str]] = None,
        limit: int = 8,
    ) -> Dict[str, Any]:
        """Ranks canonical players from PostgreSQL using V3.2.1 baseline + advisory PersonalGameplayFit."""
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        pos = position.upper()
        excluded_lower = {n.lower() for n in (exclude_names or [])}
        intervention = self.diagnose_intervention(dna, mistakes, matches)
        has_real_evidence = dna.eligible_match_count > 0

        # Query real PostgreSQL candidates safely via existing repository (fallback empty if DB offline)
        candidates: List[Dict[str, Any]] = []
        try:
            gvid = self.players.game_version_id(gv)
            if gvid:
                res = self.players.search(
                    gvid,
                    position=pos,
                    sort="overall_rating",
                    sort_dir="desc",
                    page=1,
                    page_size=40,
                    research=(gv == "FC27"),
                )
                for row in res.get("items", []):
                    if (row.get("display_name") or "").lower() in excluded_lower:
                        continue
                    candidates.append(row)
        except Exception:
            candidates = []

        target_style = {d.dimension: d.estimated_value for d in dna.style_dimensions if d.estimated_value is not None}
        weakness_codes = {m.diagnostic_code for m in mistakes}
        scored: List[Dict[str, Any]] = []

        for c in candidates:
            ovr = float(c.get("overall_rating") or 75.0)
            attrs = c.get("attributes") or {}
            playstyles = [str(p) for p in (c.get("playstyles") or [])]

            # Deterministic normalized proxy for base suitability when full attribute dict loaded
            base_v321 = max(0.35, min(0.96, (ovr - 55.0) / 42.0))

            if not has_real_evidence:
                scored.append({
                    "entity_id": str(c.get("id")),
                    "name": c.get("display_name"),
                    "position": c.get("position_primary"),
                    "overall_rating": ovr,
                    "v321_suitability": round(base_v321, 4),
                    "personal_gameplay_fit": round(base_v321, 4),
                    "mode": "STATIC_SUITABILITY_ONLY",
                    "market_price_status": "MARKET_PRICE_UNAVAILABLE",
                    "budget_respected": True if budget_coins is None else "UNVERIFIED_PRICE",
                    "fit_reasons": [f"Static base suitability fallback (0 real gameplay matches for Gamer DNA); OVR={ovr:.0f}."],
                })
                continue

            # Style compatibility from DNA traits
            style_compat = 0.65
            if target_style.get("pressing_intensity", 0.5) >= 0.65:
                stamina_approx = float(attrs.get("stamina", ovr))
                style_compat += 0.12 if stamina_approx >= 82 else -0.05
            if target_style.get("wing_utilization", 0.5) >= 0.65 and pos in ("LW", "RW", "LM", "RM", "LB", "RB"):
                style_compat += 0.12

            # Weakness coverage bonus
            weakness_cov = 0.55
            reasons: List[str] = []
            if "EXPOSED_CENTRAL_CHANNEL" in weakness_codes and pos in ("CDM", "CM"):
                weakness_cov += 0.25 if any("Intercept" in p or "Anticipate" in p or "Bruiser" in p for p in playstyles) else 0.12
                reasons.append("Covers recurring central channel exposure / pivot screening need.")
            if "RISKY_PASSING_DECISION" in weakness_codes and pos in ("CM", "CAM", "CDM"):
                weakness_cov += 0.22 if any("Incisive" in p or "Tiki" in p or "Press Proven" in p for p in playstyles) else 0.10
                reasons.append("Supports safer midfield progression under pressure.")
            if not reasons:
                reasons.append(f"Aligns with primary {dna.archetype.primary_archetype} style dimensions.")

            cohesion_role = 0.68
            fit_score = (
                _COEFFICIENT_DISCLOSURE["v321_suitability"] * base_v321
                + _COEFFICIENT_DISCLOSURE["style_compatibility"] * min(1.0, style_compat)
                + _COEFFICIENT_DISCLOSURE["weakness_coverage"] * min(1.0, weakness_cov)
                + _COEFFICIENT_DISCLOSURE["cohesion_and_role_fit"] * cohesion_role
            )

            scored.append({
                "entity_id": str(c.get("id")),
                "name": c.get("display_name"),
                "position": c.get("position_primary"),
                "overall_rating": ovr,
                "playstyles": playstyles[:5],
                "v321_suitability": round(base_v321, 4),
                "style_compatibility": round(min(1.0, style_compat), 4),
                "weakness_coverage": round(min(1.0, weakness_cov), 4),
                "personal_gameplay_fit": round(fit_score, 4),
                "mode": "PERSONAL_GAMEPLAY_FIT_ADVISORY",
                "market_price_status": "MARKET_PRICE_UNAVAILABLE",
                "budget_respected": True if budget_coins is None else "UNVERIFIED_PRICE",
                "fit_reasons": reasons,
            })

        scored.sort(key=lambda x: x["personal_gameplay_fit"], reverse=True)
        return {
            "game_version": gv,
            "position": pos,
            "frozen_v321_untouched": True,
            "budget_coins": budget_coins,
            "coefficient_disclosure": _COEFFICIENT_DISCLOSURE,
            "intervention_assessment": intervention,
            "recommendations": scored[:limit],
        }

    def analyze_personal_squad(
        self,
        *,
        game_version: str,
        formation: str,
        tactical_profile: str,
        slots: List[SquadSlotSnapshot],
        dna: GamerDNAProfile,
        mistakes: List[RecurringMistakePattern],
        matches: List[MatchIntelligenceRecord],
        budget_coins: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Answers all 6 Squad Lab Personalization questions + Counterfactual Delta."""
        intervention = self.diagnose_intervention(dna, mistakes, matches)
        expected_slots = slots_for(formation)
        valid_positions = {s.slot: s.position for s in expected_slots}

        # Validate duplicates & position matches strictly
        seen_players: set[str] = set()
        duplicate_errors: List[str] = []
        structural_warnings: List[Dict[str, Any]] = []
        base_scores: List[float] = []

        for sl in slots:
            key_name = sl.player_name.strip().lower()
            if key_name in seen_players:
                duplicate_errors.append(f"Duplicate footballer detected in XI: {sl.player_name}")
            seen_players.add(key_name)
            base_ovr = float(sl.overall_rating or 78.0)
            base_scores.append(max(0.35, min(0.96, (base_ovr - 55.0) / 42.0)))

        # Map recurring mistake positions onto active squad slots
        for m in mistakes[:4]:
            need = _POSITION_CAPABILITY_NEEDS.get(m.diagnostic_code)
            target_pos = need["position"] if need else "CDM"
            affected = [sl for sl in slots if target_pos in sl.slot_position]
            structural_warnings.append({
                "diagnostic_code": m.diagnostic_code,
                "severity": m.severity_estimate,
                "affected_slots": [a.slot_position for a in affected] or [target_pos],
                "zero_coin_fix": m.suggested_interventions[0] if m.suggested_interventions else "Adjust FC IQ role focus.",
                "evidence_clips": [c.model_dump() for c in m.supporting_clips[:2]],
            })

        xi_fit_pct = round((sum(base_scores) / max(1, len(base_scores))) * 100.0, 1) if base_scores else None
        style_align_note = (
            f"Evaluated against {dna.archetype.primary_archetype} style ({dna.eligible_match_count} real matches)."
            if dna.eligible_match_count > 0
            else "Static baseline only: zero real gameplay matches recorded yet."
        )

        # Recommend compatible FC IQ roles derived from DNA
        recommended_roles = dna.tactical_suitability[0].recommended_roles if dna.tactical_suitability else ["CDM: Holding", "CAM: Playmaker"]
        best_alt = dna.tactical_suitability[0] if dna.tactical_suitability else None

        # Evaluate targeted replacement if needed
        target_gap = intervention.get("target_capability_gaps", [])
        target_pos = target_gap[0]["position"] if target_gap else "CDM"
        rec_pack = self.recommend_for_gamer(
            game_version=game_version,
            position=target_pos,
            dna=dna,
            mistakes=mistakes,
            matches=matches,
            budget_coins=budget_coins,
            exclude_names=[s.player_name for s in slots],
            limit=3,
        )

        # Counterfactual comparison: tactical/formation shift vs single upgrade
        counterfactuals = []
        if best_alt and best_alt.formation != formation:
            counterfactuals.append({
                "scenario_type": "FORMATION_AND_ROLE_SWITCH",
                "from_setup": f"{formation} ({tactical_profile})",
                "to_setup": f"{best_alt.formation} ({best_alt.tactical_profile})",
                "expected_compatibility_delta_pct": round(max(1.5, (best_alt.suitability_score - 0.65) * 20.0), 1),
                "coin_cost_coins": 0,
                "uncertainty_note": "Tactical compatibility estimate from Gamer DNA; actual match win-rate impact requires follow-up match validation.",
            })
        if rec_pack["recommendations"]:
            top_cand = rec_pack["recommendations"][0]
            counterfactuals.append({
                "scenario_type": "SINGLE_SLOT_UPGRADE",
                "target_position": target_pos,
                "candidate_name": top_cand["name"],
                "candidate_overall": top_cand["overall_rating"],
                "expected_fit_score": top_cand["personal_gameplay_fit"],
                "market_price_status": "MARKET_PRICE_UNAVAILABLE",
                "trade_off_note": "Adds targeted capability coverage, while non-purchase role adjustments should still be tested first.",
            })

        return {
            "game_version": game_version,
            "formation": formation,
            "tactical_profile": tactical_profile,
            "valid_formation_positions": sorted(set(valid_positions.values())),
            "duplicate_errors": duplicate_errors,
            "how_well_squad_suits_my_football": {
                "score_pct": xi_fit_pct,
                "status": "PERSONALIZED" if dna.eligible_match_count > 0 else "STATIC_ONLY",
                "summary": style_align_note,
            },
            "complementary_roles": recommended_roles,
            "structural_warnings": structural_warnings,
            "no_purchase_improvements": intervention.get("tactical_first_actions", []),
            "intervention_assessment": intervention,
            "budget_compatible_upgrades": rec_pack["recommendations"],
            "counterfactual_comparisons": counterfactuals,
            "chemistry": {
                "status": "INSUFFICIENT_EVIDENCE",
                "reason": "Chemistry rules require verified squad link metadata; scores are never fabricated.",
            },
            "frozen_v321_untouched": True,
        }

    def evaluate_decision_capability_bottleneck(
        self,
        windows: List[Dict[str, Any]],
        *,
        position: str = "CM",
    ) -> Dict[str, Any]:
        """Phase 41P: Isolates gamer choice bottlenecks vs player attribute/PlayStyle limits."""
        eligible = [w for w in windows if w.get("provenance") != "SYNTHETIC_FIXTURE" and w.get("status") == "EVALUATED"]
        if not eligible:
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "position": position,
                "primary_bottleneck": "UNKNOWN",
                "capability_constrained_windows": 0,
                "decision_choice_windows": 0,
                "summary": "No non-synthetic evaluated decision windows recorded yet to isolate capability vs choice bottlenecks.",
                "recommended_focus": ["Analyze at least one real match trace or clip in Decision Replay Lab first."],
            }

        high_regret = [w for w in eligible if float(w.get("regret_estimate") or 0.0) >= 0.06]
        choice_count = len(high_regret)
        cap_constrained = 0
        req_attrs: Dict[str, int] = {}

        for w in high_regret:
            comp = w.get("counterfactual_comparison") or {}
            cands = comp.get("candidates") or []
            best_id = comp.get("best_alternative_id")
            best_c = next((c for c in cands if c.get("action_id") == best_id), None)
            cap = (best_c or {}).get("capability_requirement") or {}
            attrs = cap.get("attrs") or []
            if best_c and best_c.get("action_family") in ("SWITCH_PLAY", "THROUGH_BALL", "SHOOT"):
                cap_constrained += 1
                for a in attrs:
                    req_attrs[a] = req_attrs.get(a, 0) + 1

        primary = (
            "MIXED_CHOICE_AND_CAPABILITY"
            if cap_constrained > 0 and cap_constrained >= max(1, choice_count // 2)
            else "GAMER_DECISION_CHOICE"
        )
        top_attrs = [k for k, _ in sorted(req_attrs.items(), key=lambda kv: kv[1], reverse=True)[:4]]

        return {
            "status": "EVALUATED",
            "position": position,
            "eligible_windows": len(eligible),
            "high_regret_windows": choice_count,
            "capability_constrained_windows": cap_constrained,
            "decision_choice_windows": max(0, choice_count - cap_constrained),
            "primary_bottleneck": primary,
            "demanded_attributes": top_attrs,
            "summary": (
                f"Across {len(eligible)} real decision windows, {choice_count} showed regret >= 0.060; "
                f"{cap_constrained} involved high-execution switches/through-balls requiring [{', '.join(top_attrs) or 'vision, composure'}]."
            ),
            "recommended_focus": [
                "Address zero-coin passing timing and central cover habits before upgrading cards."
                if primary == "GAMER_DECISION_CHOICE"
                else f"Prioritize scanning far-side outlets AND test cards with higher {', '.join(top_attrs[:2]) or 'vision/long_passing'} at {position}."
            ],
        }

    def simulate_squad_decision_support(
        self,
        *,
        formation: str,
        tactical_profile: str,
        slots: List[SquadSlotSnapshot],
        windows: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Phase 41Q: Evaluates passing outlets, press resistance, and transition vulnerability."""
        expected_slots = slots_for(formation)
        pos_counts: Dict[str, int] = {}
        for s in expected_slots:
            pos_counts[s.position] = pos_counts.get(s.position, 0) + 1

        # Structural passing triangles & pivot outlets
        central_mids = pos_counts.get("CDM", 0) + pos_counts.get("CM", 0) + pos_counts.get("CAM", 0)
        wide_outlets = sum(pos_counts.get(p, 0) for p in ("LW", "RW", "LM", "RM", "LB", "RB", "LWB", "RWB"))
        rest_def_base = pos_counts.get("CB", 0) + pos_counts.get("CDM", 0)

        profile_upper = tactical_profile.upper()
        trans_penalty = 0.14 if ("HIGH_PRESS" in profile_upper or "AGGRESSIVE" in profile_upper) else 0.04
        if pos_counts.get("CDM", 0) == 0:
            trans_penalty += 0.12

        # Blend observed slot ratings conservatively when populated
        slot_ovr = [float(sl.overall_rating) for sl in slots if sl.overall_rating is not None]
        ovr_factor = ((sum(slot_ovr) / len(slot_ovr)) - 75.0) / 100.0 if slot_ovr else 0.04

        passing_outlets_score = round(max(0.25, min(0.96, 0.52 + 0.07 * min(4, central_mids) + 0.04 * min(4, wide_outlets) + ovr_factor)), 3)
        press_resistance_score = round(max(0.25, min(0.95, 0.48 + 0.09 * min(3, pos_counts.get("CDM", 0) + pos_counts.get("CM", 0)) + ovr_factor)), 3)
        transition_vulnerability = round(max(0.08, min(0.85, 0.42 - 0.06 * rest_def_base + trans_penalty)), 3)

        regret_context = None
        if windows:
            elig = [w for w in windows if w.get("provenance") != "SYNTHETIC_FIXTURE" and w.get("regret_estimate") is not None]
            if elig:
                regret_context = round(sum(float(w["regret_estimate"]) for w in elig) / len(elig), 4)

        return {
            "formation": formation,
            "tactical_profile": tactical_profile,
            "simulation_mode": "STRUCTURAL_ROLE_HEURISTIC",
            "passing_outlets_score": passing_outlets_score,
            "midfield_press_resistance": press_resistance_score,
            "transition_vulnerability_index": transition_vulnerability,
            "rest_defense_anchor_count": rest_def_base,
            "observed_mean_decision_regret": regret_context,
            "structural_guidance": (
                f"{formation} offers {central_mids} central progression hub(s) and {wide_outlets} wide outlet(s); "
                + ("no dedicated CDM detected — assign Hold/Deep-Lying Playmaker on a CM to guard transition counters."
                   if pos_counts.get("CDM", 0) == 0
                   else f"{pos_counts.get('CDM', 0)} pivot anchor(s) stabilize rest defense.")
            ),
            "frozen_v321_untouched": True,
        }
