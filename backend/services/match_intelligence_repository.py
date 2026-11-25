"""Phase 40B Service Facade for Persistent Match Intelligence, Comparison, and Privacy."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.phase40_models import (
    EvidenceClipRef,
    MatchIntelligenceRecord,
    MatchRecordCreate,
)
from backend.repositories.phase40_repository import Phase40Repository, get_phase40_repository


class MatchIntelligenceService:
    """Orchestrates persistent match analysis storage, comparison, and bridging from Phase 39 runs."""

    def __init__(self, repo: Optional[Phase40Repository] = None) -> None:
        self.repo = repo or get_phase40_repository()

    def record_match(self, user_id: str, payload: MatchRecordCreate) -> MatchIntelligenceRecord:
        return self.repo.save_match(user_id, payload)

    def ingest_from_video_analysis(
        self,
        user_id: str,
        *,
        video_id: str,
        game_version: str,
        game_patch: str,
        gameplay_mode: str,
        formation: str,
        tactical_profile: str,
        summary: Dict[str, Any],
        spatial_result: Dict[str, Any],
        coaching_result: Dict[str, Any],
        squad_slots: Optional[List[Dict[str, Any]]] = None,
        match_result: Optional[Dict[str, Any]] = None,
    ) -> MatchIntelligenceRecord:
        """Converts an already-computed Phase 39 analysis directly into a persistent match record."""
        frames = spatial_result.get("frames", [])
        coverage = float(summary.get("mean_coverage_pct") or summary.get("observation_coverage_pct") or 0.0)
        if coverage <= 0.0 and frames:
            coverage = sum(float(f.get("observation_coverage_pct", 0.0)) for f in frames) / len(frames)

        provenance = str(summary.get("provenance") or coaching_result.get("provenance") or "SYNTHETIC_FIXTURE")
        if provenance not in ("REAL_VIDEO_DECODED", "IMPORTED_MATCH_TRACE", "MANUAL_ANNOTATION", "SYNTHETIC_FIXTURE"):
            provenance = "SYNTHETIC_FIXTURE"

        obs_quality = "HIGH" if coverage >= 85.0 else ("MODERATE" if coverage >= 65.0 else ("LOW" if coverage >= 40.0 else "INSUFFICIENT"))
        diagnostics = coaching_result.get("diagnostics", [])

        clips: List[EvidenceClipRef] = []
        for d in diagnostics:
            clips.append(
                EvidenceClipRef(
                    match_id="",
                    video_id=video_id,
                    timestamp_start=float(d.get("timestamp_start", 0.0)),
                    timestamp_end=float(d.get("timestamp_end", 0.0)),
                    title=str(d.get("code", "TACTICAL_FINDING")).replace("_", " "),
                    diagnostic_code=d.get("code"),
                    provenance=provenance,
                    confidence=str(d.get("confidence_level", "MODERATE")),
                    deep_link=f"/research/gameplay-studio?video_id={video_id}&t={round(float(d.get('timestamp_start', 0.0)), 2)}&tab=RADAR_REPLAY",
                )
            )

        feature_metrics = self._extract_spatial_feature_metrics(frames, diagnostics)

        create_req = MatchRecordCreate(
            video_id=video_id,
            game_version="FC26" if str(game_version).upper() == "FC26" else "FC27",
            game_patch=game_patch or "PATCH_1.02",
            gameplay_mode=gameplay_mode or "COMPETITIVE_RIVALS",
            duration_seconds=float(summary.get("duration_seconds") or 0.0),
            formation=formation or "4-3-3",
            tactical_profile=tactical_profile or "BALANCED",
            tactical_instructions=summary.get("tactical_instructions", {}),
            squad_slots=squad_slots or [],
            match_result=match_result or {},
            provenance=provenance,  # type: ignore[arg-type]
            observation_quality=obs_quality,  # type: ignore[arg-type]
            tracking_coverage_pct=round(coverage, 1),
            telemetry_summary=summary,
            feature_metrics=feature_metrics,
            tactical_events=[],
            coaching_findings=diagnostics,
            evidence_clips=clips,
        )
        return self.repo.save_match(user_id, create_req)

    @staticmethod
    def _extract_spatial_feature_metrics(frames: List[Dict[str, Any]], diagnostics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarizes spatial frame snapshots into normalized match metrics."""
        if not frames:
            return {
                "possession_share": 0.50,
                "attacking_directness": 0.50,
                "passing_tempo": 0.50,
                "passing_risk": 0.45,
                "wing_utilization": 0.50,
                "central_progression": 0.50,
                "defensive_compactness": 0.55,
                "pressing_intensity": 0.50,
                "transition_opportunities": max(1, len(diagnostics)),
                "exposed_transitions": sum(1 for d in diagnostics if d.get("code") in ("COUNTER_ATTACK_VULNERABILITY", "EXPOSED_CENTRAL_CHANNEL")),
                "central_pass_opportunities": 8,
                "risky_central_passes": sum(1 for d in diagnostics if d.get("code") == "RISKY_PASSING_DECISION"),
                "sequence_clusters": 1,
            }

        usable = [f for f in frames if f.get("uncertainty_band") != "UNRELIABLE"] or frames
        home_poss = sum(1 for f in usable if f.get("possession_team") == "HOME")
        poss_share = home_poss / max(1, sum(1 for f in usable if f.get("possession_team") in ("HOME", "AWAY")))

        widths = [float(f.get("home_structure", {}).get("team_width_m", 44.0)) for f in usable]
        areas = [float(f.get("home_structure", {}).get("compactness_area_m2", 1800.0)) for f in usable]
        avg_width = sum(widths) / len(widths) if widths else 44.0
        avg_area = sum(areas) / len(areas) if areas else 1800.0

        compactness = max(0.05, min(0.98, 1.0 - max(0.0, avg_area - 1100.0) / 2200.0))
        wing_util = max(0.1, min(0.95, avg_width / 62.0))

        all_lanes = [lane for f in usable for lane in f.get("passing_lanes", [])]
        prog_lanes = sum(1 for ln in all_lanes if ln.get("is_progressive"))
        blocked_lanes = sum(1 for ln in all_lanes if ln.get("status") == "BLOCKED")
        total_lanes = max(1, len(all_lanes))

        # Approximate independent possession clusters (~every 10 seconds) to prevent frame autocorrelation inflation
        t_min = min(float(f.get("timestamp_sec", 0.0)) for f in usable)
        t_max = max(float(f.get("timestamp_sec", 0.0)) for f in usable)
        clusters = max(1, int((t_max - t_min) / 10.0) + 1)

        return {
            "possession_share": round(poss_share, 3),
            "attacking_directness": round(min(0.95, 0.3 + (prog_lanes / total_lanes) * 0.65), 3),
            "passing_tempo": round(min(0.95, 0.35 + (prog_lanes / total_lanes) * 0.45), 3),
            "passing_risk": round(min(0.95, 0.20 + (blocked_lanes / total_lanes) * 0.65), 3),
            "chance_creation": round(min(0.92, 0.45 + sum(1 for ln in all_lanes if ln.get("xt_gain", 0) > 0.015) / total_lanes * 0.45), 3),
            "wing_utilization": round(wing_util, 3),
            "central_progression": round(max(0.1, min(0.95, 0.68 - 0.15 * sum(1 for d in diagnostics if d.get("code") == "EXPOSED_CENTRAL_CHANNEL"))), 3),
            "dribbling_tendency": 0.48,
            "finishing_decisions": 0.55,
            "defensive_compactness": round(compactness, 3),
            "pressing_intensity": round(min(0.95, 0.42 + 0.14 * sum(1 for d in diagnostics if d.get("code") == "EXCESSIVE_PRESSING")), 3),
            "defensive_transition_management": round(max(0.15, 0.78 - 0.18 * sum(1 for d in diagnostics if d.get("code") == "COUNTER_ATTACK_VULNERABILITY")), 3),
            "tactical_discipline": round(max(0.15, 0.80 - 0.14 * sum(1 for d in diagnostics if d.get("code") == "UNNECESSARY_CB_DISPLACEMENT")), 3),
            "adaptability": 0.55,
            "decision_making_under_pressure": round(max(0.15, 0.72 - 0.14 * sum(1 for d in diagnostics if d.get("code") == "RISKY_PASSING_DECISION")), 3),
            "transition_opportunities": max(4, clusters * 2),
            "exposed_transitions": sum(1 for d in diagnostics if d.get("code") in ("COUNTER_ATTACK_VULNERABILITY", "EXPOSED_CENTRAL_CHANNEL")),
            "central_pass_opportunities": max(6, clusters * 3),
            "risky_central_passes": sum(1 for d in diagnostics if d.get("code") in ("RISKY_PASSING_DECISION", "INEFFICIENT_POSSESSION_PROGRESSION")),
            "sequence_clusters": clusters,
        }

    def compare_matches(self, user_id: str, match_id_a: str, match_id_b: str) -> Dict[str, Any]:
        """Compares two user-owned matches with explicit patch/formation comparability warnings."""
        a = self.repo.get_match(user_id, match_id_a)
        b = self.repo.get_match(user_id, match_id_b)

        warnings: List[str] = []
        if a.game_version != b.game_version:
            warnings.append(f"Edition mismatch: {a.game_version} vs {b.game_version} cannot be treated as direct progression.")
        if a.game_patch != b.game_patch:
            warnings.append(f"Patch change detected ({a.game_patch} -> {b.game_patch}); gameplay tuning differences may confound deltas.")
        if a.formation != b.formation:
            warnings.append(f"Formation changed ({a.formation} -> {b.formation}).")
        if a.gameplay_mode != b.gameplay_mode:
            warnings.append(f"Gameplay mode changed ({a.gameplay_mode} -> {b.gameplay_mode}).")
        if a.provenance == "SYNTHETIC_FIXTURE" or b.provenance == "SYNTHETIC_FIXTURE":
            warnings.append("Synthetic fixture comparison: valid for UI/method testing only, not real skill measurement.")

        keys = sorted(set(a.feature_metrics.keys()) | set(b.feature_metrics.keys()))
        deltas: Dict[str, Any] = {}
        for k in keys:
            va = a.feature_metrics.get(k)
            vb = b.feature_metrics.get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                deltas[k] = {"before": round(float(va), 3), "after": round(float(vb), 3), "delta": round(float(vb) - float(va), 3)}

        return {
            "match_a": {
                "match_id": a.match_id,
                "game_version": a.game_version,
                "game_patch": a.game_patch,
                "formation": a.formation,
                "findings_count": len(a.coaching_findings),
                "provenance": a.provenance,
            },
            "match_b": {
                "match_id": b.match_id,
                "game_version": b.game_version,
                "game_patch": b.game_patch,
                "formation": b.formation,
                "findings_count": len(b.coaching_findings),
                "provenance": b.provenance,
            },
            "findings_delta": len(b.coaching_findings) - len(a.coaching_findings),
            "metric_deltas": deltas,
            "comparability_warnings": warnings,
        }
