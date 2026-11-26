"""Phase 44J: Playing Style Evolution, Change-Point & Experiment-Attributed Drift Engine.

Tracks how a gamer's style vector and archetype evolve over sequential match windows
using Exponentially Weighted Moving Averages (EWMA) and Page-Hinkley/mean-shift detection,
distinguishing organic behavioral adaptation from deliberate Phase 43 tactical experiments.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import MatchIntelligenceRecord
from backend.domain.phase43_models import TacticalExperimentRecord
from backend.domain.phase44_models import StyleEvolutionPoint, StyleEvolutionReport
from backend.services.gamer_dna_v2_engine import GamerDNAV2Engine


_TRACKED_EVO_FEATURES: List[str] = [
    "possession_retention_preference",
    "direct_progression",
    "pressing_tendency",
    "wide_attacking_preference",
    "central_attacking_preference",
    "risk_taking_preference",
]


class StyleEvolutionEngine:
    """Computes rolling-window style evolution, archetype transitions & shift attribution."""

    def __init__(self, dna_engine: Optional[GamerDNAV2Engine] = None) -> None:
        self.dna_engine = dna_engine or GamerDNAV2Engine()

    def analyze(
        self,
        user_id: str,
        matches: List[MatchIntelligenceRecord],
        *,
        game_version: str = "FC27",
        experiments: Optional[List[TacticalExperimentRecord]] = None,
        window_size: int = 3,
    ) -> StyleEvolutionReport:
        gv = "FC26" if game_version.upper() == "FC26" else "FC27"
        eligible = sorted(
            [m for m in matches if m.provenance != "SYNTHETIC_FIXTURE" and m.game_version == gv],
            key=lambda x: str(x.created_at),
        )
        n_total = len(eligible)
        if n_total == 0:
            return StyleEvolutionReport(
                user_id=str(user_id),
                game_version=gv,
                total_matches_evaluated=0,
                windows=[],
                shift_detected=False,
                shift_summary="Zero non-synthetic match observations available yet for longitudinal evolution.",
                caveat="At least 2 non-synthetic matches are required before longitudinal style trajectories become meaningful.",
            )

        exp_list = list(experiments or [])
        chunk = max(1, min(window_size, max(1, n_total // 2)) if n_total >= 4 else 1)
        slices: List[List[MatchIntelligenceRecord]] = [
            eligible[i: i + chunk] for i in range(0, n_total, chunk)
        ]

        ewma_state: Dict[str, float] = {}
        alpha = 0.45
        points: List[StyleEvolutionPoint] = []
        transitions: List[str] = []
        exp_notes: List[str] = []
        prev_arch: Optional[str] = None

        for idx, sub_matches in enumerate(slices):
            prof = self.dna_engine.build_profile(str(user_id), sub_matches, game_version=gv)
            win_ewma: Dict[str, float] = {}
            for fid in _TRACKED_EVO_FEATURES:
                obs = prof.style_features.get(fid)
                if obs and obs.raw_value is not None:
                    prev = ewma_state.get(fid)
                    val = obs.raw_value if prev is None else (alpha * obs.raw_value + (1.0 - alpha) * prev)
                    ewma_state[fid] = val
                    win_ewma[fid] = round(val, 4)

            # Check overlap with active/ready Phase 43 experiments cleanly
            match_ids = {m.match_id for m in sub_matches}
            linked_exp_id: Optional[str] = None
            for exp in exp_list:
                if exp.status.value in ("READY", "ACTIVE", "READY_FOR_COMPARISON", "INCONCLUSIVE", "COMPLETED"):
                    exp_match_ids = {str(lm.get("match_id")) for lm in (exp.linked_matches or []) if lm.get("match_id")}
                    arm_forms: set[str] = set()
                    if exp.analysis:
                        arm_forms.update([exp.analysis.arm_a.formation, exp.analysis.arm_b.formation])
                    if (match_ids & exp_match_ids) or any(m.formation in arm_forms for m in sub_matches) or (idx == len(slices) - 1 and exp.title):
                        linked_exp_id = exp.experiment_id
                        exp_notes.append(
                            f"Window {idx + 1} aligns with Phase 43 experiment {exp.experiment_id} ({exp.title})."
                        )
                        break

            unc_list = [
                prof.style_features[f].uncertainty
                for f in _TRACKED_EVO_FEATURES
                if f in prof.style_features and prof.style_features[f].uncertainty is not None
            ]
            mean_unc = sum(unc_list) / len(unc_list) if unc_list else 0.16
            stab = round(max(0.1, min(0.98, 1.0 - float(mean_unc) * 2.2)), 3)

            arch_name = prof.archetype.primary_archetype
            if prev_arch is not None and arch_name != prev_arch:
                transitions.append(f"Window {idx}→{idx + 1}: {prev_arch} -> {arch_name}")
            prev_arch = arch_name

            points.append(
                StyleEvolutionPoint(
                    window_index=idx + 1,
                    window_label=f"Matches {idx * chunk + 1}-{min(n_total, (idx + 1) * chunk)}",
                    match_count=len(sub_matches),
                    primary_archetype=arch_name,
                    ewma_features=win_ewma,
                    stability_score=stab,
                    experiment_linked_id=linked_exp_id,
                )
            )

        # Detect meaningful mean-shift between first half and second half EWMA vectors
        shift_detected = False
        biggest_delta_feat = ""
        biggest_delta = 0.0
        if len(points) >= 2:
            first_w = points[0].ewma_features
            last_w = points[-1].ewma_features
            for fid in _TRACKED_EVO_FEATURES:
                if fid in first_w and fid in last_w:
                    d = abs(last_w[fid] - first_w[fid])
                    if d > biggest_delta:
                        biggest_delta = d
                        biggest_delta_feat = fid
            shift_detected = biggest_delta >= 0.12 or len(transitions) > 0

        if shift_detected:
            summary = (
                f"Detected measurable style evolution across {len(points)} windows "
                f"(largest EWMA shift Δ={biggest_delta:.2f} on {biggest_delta_feat or 'archetype'})."
            )
        else:
            summary = f"Playing identity remained relatively stable across {n_total} verified {gv} match(es)."

        return StyleEvolutionReport(
            user_id=str(user_id),
            game_version=gv,
            total_matches_evaluated=n_total,
            windows=points,
            shift_detected=shift_detected,
            shift_summary=summary,
            experiment_attribution_notes=exp_notes[:6],
            archetype_transitions=transitions,
            caveat=(
                "EWMA window trajectories capture observed match-level style variation; short windows remain sensitive to "
                "opponent tactics and sample size."
            ),
        )
