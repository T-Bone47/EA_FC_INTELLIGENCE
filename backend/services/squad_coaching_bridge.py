"""Phase 39 Stage 7: Squad Lab Coaching Integration Bridge.

Connects validated empirical coaching diagnostics and spatial telemetry to Squad Lab
and Player Discovery without modifying the frozen V3.2.1 recommendation weights.

Prioritizes:
  1. Gamer decision-making & positional discipline
  2. Tactical instructions (width, defensive line height, stay-back anchors)
  3. Formation structure adjustment
  4. Player role incompatibility
  5. Player capability profile (only when tactical adjustments cannot close the gap)
  6. Insufficient evidence (when provenance is SYNTHETIC_FIXTURE or coverage is low)
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.video_ingestion import DataProvenance
from backend.services.tactical_coaching_engine import DiagnosticCode


class CausalCategory(str, Enum):
    GAMER_DECISION_MAKING = "GAMER_DECISION_MAKING"
    TACTICAL_INSTRUCTIONS = "TACTICAL_INSTRUCTIONS"
    FORMATION_STRUCTURE = "FORMATION_STRUCTURE"
    PLAYER_ROLE_INCOMPATIBILITY = "PLAYER_ROLE_INCOMPATIBILITY"
    PLAYER_CAPABILITY_LIMITATION = "PLAYER_CAPABILITY_LIMITATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RequiredCapabilityProfile(BaseModel):
    target_position: str
    priority_attributes: Dict[str, int] = Field(default_factory=dict)  # e.g. {"interceptions": 84, "sprint_speed": 85}
    recommended_playstyles: List[str] = Field(default_factory=list)
    rationale: str
    intelligence_route: str
    discovery_route: str
    squad_lab_route: str


class CoachingAttributionItem(BaseModel):
    diagnostic_code: str
    primary_cause: CausalCategory
    secondary_causes: List[CausalCategory] = Field(default_factory=list)
    tactical_first_prescription: str
    tactical_instruction_changes: List[str] = Field(default_factory=list)
    formation_adjustment: Optional[str] = None
    capability_profile: Optional[RequiredCapabilityProfile] = None
    purchase_recommended: bool = False
    provenance_gated: bool = False


class SquadCoachingBridge:
    """Translates tactical diagnostics into ranked, non-commercial-first interventions."""

    _CAUSAL_MAP: Dict[str, Dict[str, Any]] = {
        DiagnosticCode.UNNECESSARY_CB_DISPLACEMENT.value: {
            "primary": CausalCategory.GAMER_DECISION_MAKING,
            "secondary": [CausalCategory.PLAYER_ROLE_INCOMPATIBILITY],
            "prescription": "Hold right-stick switching off the center-back early; screen with CDM first before engaging ball carrier.",
            "instructions": ["CDM: Cut Passing Lanes / Stay Back While Attacking", "CBs: Defender Balanced"],
            "formation": None,
            "pos": "CDM",
            "attrs": {"interceptions": 84, "defensive_awareness": 85, "stamina": 82},
            "playstyles": ["Intercept", "Anticipate"],
        },
        DiagnosticCode.EXPOSED_CENTRAL_CHANNEL.value: {
            "primary": CausalCategory.FORMATION_STRUCTURE,
            "secondary": [CausalCategory.TACTICAL_INSTRUCTIONS, CausalCategory.PLAYER_ROLE_INCOMPATIBILITY],
            "prescription": "Anchor one central midfielder exclusively inside Zone 8 before pressing wide.",
            "instructions": ["CDM/CM: Holding / Stay Back While Attacking", "Defensive Width: Narrow (< 45)"],
            "formation": "4-2-3-1 (Double Pivot) or 4-3-3 Holding",
            "pos": "CDM",
            "attrs": {"defensive_awareness": 86, "interceptions": 85, "reactions": 84},
            "playstyles": ["Intercept+", "Bruiser"],
        },
        DiagnosticCode.MIDFIELD_RECOVERY_FAILURE.value: {
            "primary": CausalCategory.TACTICAL_INSTRUCTIONS,
            "secondary": [CausalCategory.PLAYER_CAPABILITY_LIMITATION],
            "prescription": "Compress vertical distance between defense and midfield lines below 15m.",
            "instructions": ["Build-Up: Balanced", "Defensive Approach: Balanced (Height 55–62)"],
            "formation": "4-4-1-1 or 4-2-3-1",
            "pos": "CM",
            "attrs": {"stamina": 86, "acceleration": 82, "interceptions": 82},
            "playstyles": ["Relentless", "Intercept"],
        },
        DiagnosticCode.POOR_DEFENSIVE_COMPACTNESS.value: {
            "primary": CausalCategory.TACTICAL_INSTRUCTIONS,
            "secondary": [CausalCategory.GAMER_DECISION_MAKING],
            "prescription": "Reduce horizontal stretching out of possession; pull weak-side winger inward.",
            "instructions": ["Wide Midfielders: Defensive Support / Inside Track"],
            "formation": "4-4-2 Compact Block",
            "pos": "CDM",
            "attrs": {"defensive_awareness": 83, "agility": 80},
            "playstyles": ["Anticipate"],
        },
        DiagnosticCode.EXCESSIVE_PRESSING.value: {
            "primary": CausalCategory.GAMER_DECISION_MAKING,
            "secondary": [CausalCategory.TACTICAL_INSTRUCTIONS],
            "prescription": "Avoid committing 3+ pressers ahead of the ball unless rest defense holds 3+ covers.",
            "instructions": ["Defensive Approach: Balanced (Avoid Constant Pressure)", "One FB: Stay Back"],
            "formation": None,
            "pos": None,
            "attrs": {},
            "playstyles": [],
        },
        DiagnosticCode.RISKY_PASSING_DECISION.value: {
            "primary": CausalCategory.GAMER_DECISION_MAKING,
            "secondary": [],
            "prescription": "Release into the open wide/half-space outlet instead of forcing through central congestion.",
            "instructions": [],
            "formation": None,
            "pos": None,
            "attrs": {},
            "playstyles": [],
        },
        DiagnosticCode.MISSED_PASSING_OPPORTUNITY.value: {
            "primary": CausalCategory.GAMER_DECISION_MAKING,
            "secondary": [CausalCategory.PLAYER_CAPABILITY_LIMITATION],
            "prescription": "Scan advanced half-space runners early; play first-time progressive pass before press arrives.",
            "instructions": ["CAM/CM: Playmaker / Forward Runs"],
            "formation": None,
            "pos": "CAM",
            "attrs": {"vision": 86, "short_passing": 86, "long_passing": 82},
            "playstyles": ["Incisive Pass"],
        },
        DiagnosticCode.INEFFECTIVE_ATTACKING_WIDTH.value: {
            "primary": CausalCategory.TACTICAL_INSTRUCTIONS,
            "secondary": [CausalCategory.FORMATION_STRUCTURE],
            "prescription": "Keep at least one winger or attacking wingback on the touchline to stretch opponent backline.",
            "instructions": ["LW/RW: Winger / Touchline Width"],
            "formation": "4-3-3 Attack or 3-4-2-1",
            "pos": "RW",
            "attrs": {"sprint_speed": 88, "crossing": 82, "dribbling": 85},
            "playstyles": ["Rapid", "Whipped Pass"],
        },
        DiagnosticCode.ISOLATED_STRIKER.value: {
            "primary": CausalCategory.FORMATION_STRUCTURE,
            "secondary": [CausalCategory.TACTICAL_INSTRUCTIONS],
            "prescription": "Bring an interior CM or Shadow Striker CAM within 15m beneath the lead forward.",
            "instructions": ["CAM: Shadow Striker", "Build-Up: Short Passing / Balanced"],
            "formation": "4-2-3-1 Narrow or 4-3-3 Attack",
            "pos": "CAM",
            "attrs": {"positioning": 84, "short_passing": 84, "dribbling": 84},
            "playstyles": ["Incisive Pass", "Technical"],
        },
        DiagnosticCode.OVERLAPPING_PLAYER_ROLES.value: {
            "primary": CausalCategory.PLAYER_ROLE_INCOMPATIBILITY,
            "secondary": [CausalCategory.TACTICAL_INSTRUCTIONS],
            "prescription": "Separate adjacent interior roles (pair Inside Forward + Wingback Width, not dual Playmakers in same pocket).",
            "instructions": ["One CM: Box-to-Box", "Other CM/CAM: Playmaker Half-Space"],
            "formation": None,
            "pos": None,
            "attrs": {},
            "playstyles": [],
        },
        DiagnosticCode.COUNTER_ATTACK_VULNERABILITY.value: {
            "primary": CausalCategory.TACTICAL_INSTRUCTIONS,
            "secondary": [CausalCategory.PLAYER_CAPABILITY_LIMITATION],
            "prescription": "Lock a balanced rest-defense trio (2 CB + 1 FB or CDM) before overlapping both flanks.",
            "instructions": ["RB or LB: Fullback Defend", "CDM: Deep-Lying Playmaker Defend"],
            "formation": None,
            "pos": "RB",
            "attrs": {"sprint_speed": 88, "interceptions": 82, "stamina": 85},
            "playstyles": ["Quick Step", "Intercept"],
        },
        DiagnosticCode.INEFFICIENT_POSSESSION_PROGRESSION.value: {
            "primary": CausalCategory.GAMER_DECISION_MAKING,
            "secondary": [CausalCategory.TACTICAL_INSTRUCTIONS],
            "prescription": "Trigger directional runs (L1/LB) or manual diagonal wall passes when opponent shifts laterally.",
            "instructions": ["ST: Advanced Forward", "Winger: Inside Forward"],
            "formation": None,
            "pos": None,
            "attrs": {},
            "playstyles": [],
        },
    }

    def build_coaching_plan(
        self,
        video_id: str,
        diagnostics: List[Dict[str, Any]],
        game_version: str = "FC27",
    ) -> Dict[str, Any]:
        if not diagnostics:
            return {
                "video_id": video_id,
                "status": CausalCategory.INSUFFICIENT_EVIDENCE.value,
                "attributions": [],
                "tactical_priority_summary": [
                    "No sustained tactical failures met evidence thresholds. Upload or decode a longer active match clip."
                ],
                "capability_profiles": [],
                "frozen_v321_untouched": True,
            }

        provenance = diagnostics[0].get("provenance", DataProvenance.REAL_VIDEO_DECODED.value)
        is_synthetic = provenance == DataProvenance.SYNTHETIC_FIXTURE.value

        attributions: List[CoachingAttributionItem] = []
        profiles: List[RequiredCapabilityProfile] = []
        seen_positions = set()

        for diag in diagnostics:
            code = diag.get("code", "")
            spec = self._CAUSAL_MAP.get(code)
            if not spec:
                continue

            conf = diag.get("confidence_level", "LOW")
            # Gate: insufficient real evidence never prescribes purchases
            if is_synthetic or conf == "LOW":
                primary = CausalCategory.INSUFFICIENT_EVIDENCE if is_synthetic else spec["primary"]
                attributions.append(CoachingAttributionItem(
                    diagnostic_code=code,
                    primary_cause=primary,
                    secondary_causes=spec["secondary"],
                    tactical_first_prescription=spec["prescription"],
                    tactical_instruction_changes=spec["instructions"],
                    formation_adjustment=spec["formation"],
                    capability_profile=None,
                    purchase_recommended=False,
                    provenance_gated=is_synthetic,
                ))
                continue

            # Validated real/annotated evidence: still tactical/decision first; emit capability profile as optional upgrade fit
            profile: Optional[RequiredCapabilityProfile] = None
            pos = spec.get("pos")
            if pos and spec.get("attrs") and pos not in seen_positions and diag.get("severity") in ("HIGH", "MEDIUM"):
                seen_positions.add(pos)
                profile = RequiredCapabilityProfile(
                    target_position=pos,
                    priority_attributes=spec["attrs"],
                    recommended_playstyles=spec["playstyles"],
                    rationale=f"Secondary squad fit check for {code}: target traits complement tactical fixes above.",
                    intelligence_route=f"/intelligence?position={pos}",
                    discovery_route=f"/search?position={pos}",
                    squad_lab_route="/cards/squad-lab",
                )
                profiles.append(profile)

            attributions.append(CoachingAttributionItem(
                diagnostic_code=code,
                primary_cause=spec["primary"],
                secondary_causes=spec["secondary"],
                tactical_first_prescription=spec["prescription"],
                tactical_instruction_changes=spec["instructions"],
                formation_adjustment=spec["formation"],
                capability_profile=profile,
                purchase_recommended=False,  # Tactical adjustments are always prioritized before purchases
                provenance_gated=False,
            ))

        priority_summary = [
            f"[{a.primary_cause.value}] {a.tactical_first_prescription}"
            for a in attributions[:4]
        ]

        return {
            "video_id": video_id,
            "game_version": game_version,
            "provenance": provenance,
            "status": "PROVENANCE_GATED_ILLUSTRATION" if is_synthetic else "EVIDENCE_GROUNDED_PLAN",
            "attributions": [a.model_dump() for a in attributions],
            "tactical_priority_summary": priority_summary,
            "capability_profiles": [p.model_dump() for p in profiles],
            "frozen_v321_untouched": True,
        }
